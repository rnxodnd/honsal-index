"""선택한 세부 시설만 지도·항목 점수·개인화 총점에 반영하는 공통 함수.

거리/개수에서 0~100점으로 바꾸는 작업은 별도입니다. 이 모듈은 그 결과인
격자·세부유형별 점수를 선택·평균하며, 미확보 점수를 0으로 바꾸지 않습니다.
"""

import json
import math
from collections.abc import Mapping
from pathlib import Path

import pandas as pd


CATEGORIES = ("daily_life", "healthcare", "transport", "leisure_community")
CATEGORY_COLUMN = "analysis_category"
SUBTYPE_COLUMN = "analysis_subtype"
WEIGHTS_PATH = Path(__file__).resolve().parents[2] / "config" / "weights.json"


def _selection(selected: Mapping) -> dict[str, tuple[str, ...]]:
    if not isinstance(selected, Mapping) or set(selected) - set(CATEGORIES):
        raise ValueError("선택 항목은 생활시설·의료·교통·여가시설이어야 합니다.")
    result = {}
    for category in CATEGORIES:
        values = selected.get(category, [])
        if not isinstance(values, (list, tuple, set, frozenset)):
            raise ValueError("세부 시설 선택값은 문자열 목록이어야 합니다.")
        if any(not isinstance(value, str) or not value.strip() or value != value.strip() for value in values):
            raise ValueError("세부 시설 이름은 비어 있거나 앞뒤 공백이 있으면 안 됩니다.")
        result[category] = tuple(sorted(set(values)))
    if not any(result.values()):
        raise ValueError("분석할 시설을 하나 이상 선택하세요.")
    return result


def _check_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {sorted(missing)}")


def _validate_types(frame: pd.DataFrame) -> None:
    _check_columns(frame, [CATEGORY_COLUMN, SUBTYPE_COLUMN])
    if not frame[CATEGORY_COLUMN].isin(CATEGORIES).all():
        raise ValueError("미분류 시설 또는 분석 범위 밖의 항목이 있습니다.")
    for value in frame[SUBTYPE_COLUMN]:
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError("세부 시설 분류가 비어 있거나 올바르지 않습니다.")


def available_facility_types(facilities: pd.DataFrame) -> dict[str, list[str]]:
    """실제 정제 자료에 있는 세부유형을 화면 선택지로 제공합니다."""
    _validate_types(facilities)
    return {
        category: sorted(facilities.loc[
            facilities[CATEGORY_COLUMN].eq(category), SUBTYPE_COLUMN
        ].unique().tolist())
        for category in CATEGORIES
    }


def filter_facilities(facilities: pd.DataFrame, selected: Mapping) -> pd.DataFrame:
    """지도와 거리 계산에 사용할 시설만 선택합니다. 원본은 수정하지 않습니다."""
    selection = _selection(selected)
    options = available_facility_types(facilities)
    _check_columns(facilities, ["facility_id"])
    ids = facilities["facility_id"]
    if ids.isna().any() or ids.astype("string").str.strip().eq("").any() or ids.duplicated().any():
        raise ValueError("시설 식별자는 누락 없이 고유해야 합니다.")
    mask = pd.Series(False, index=facilities.index)
    for category, subtypes in selection.items():
        unknown = set(subtypes) - set(options[category])
        if unknown:
            raise ValueError(f"자료에서 확인되지 않은 시설 선택입니다: {category}: {sorted(unknown)}")
        mask |= facilities[CATEGORY_COLUMN].eq(category) & facilities[SUBTYPE_COLUMN].isin(subtypes)
    return facilities.loc[mask].copy()


def normalize_selected_weights(selected: Mapping, weights: Mapping | None = None) -> dict[str, float]:
    """세부유형을 선택한 항목만 남기고 가중치 합계를 1로 맞춥니다."""
    selection = _selection(selected)
    if weights is None:
        weights = json.loads(WEIGHTS_PATH.resolve().read_text(encoding="utf-8"))["weights"]
    if not isinstance(weights, Mapping) or set(weights) - set(CATEGORIES):
        raise ValueError("가중치 항목이 분석 범위와 다릅니다.")
    active = {}
    for category, subtypes in selection.items():
        if not subtypes:
            continue
        if category not in weights:
            raise ValueError(f"가중치가 없습니다: {category}")
        try:
            value = float(weights[category])
        except (TypeError, ValueError) as error:
            raise ValueError("가중치는 0 이상의 유한한 숫자여야 합니다.") from error
        if not math.isfinite(value) or value < 0:
            raise ValueError("가중치는 0 이상의 유한한 숫자여야 합니다.")
        active[category] = value
    total = math.fsum(active.values())
    if not total or not math.isfinite(total):
        raise ValueError("선택한 항목의 가중치 합계는 0보다 커야 합니다.")
    return {category: value / total for category, value in active.items()}


def calculate_preference_scores(type_scores: pd.DataFrame, selected: Mapping,
                                weights: Mapping | None = None) -> pd.DataFrame:
    """격자·세부유형별 0~100점에서 선택한 유형의 평균과 가중 총점을 구합니다.

    입력 컬럼: grid_id, analysis_category, analysis_subtype, score.
    선택한 유형이 누락된 격자는 총점/순위를 비워 둡니다. 시설이 없는 경우의
    0점은 입력 생성 단계에서 자료 범위를 확인한 후 명시해야 합니다.
    """
    selection = _selection(selected)
    normalized = normalize_selected_weights(selection, weights)
    _check_columns(type_scores, ["grid_id", CATEGORY_COLUMN, SUBTYPE_COLUMN, "score"])
    _validate_types(type_scores)
    keys = ["grid_id", CATEGORY_COLUMN, SUBTYPE_COLUMN]
    ids = type_scores["grid_id"]
    if ids.isna().any() or ids.astype("string").str.strip().eq("").any() or type_scores.duplicated(keys).any():
        raise ValueError("격자 ID 누락 또는 격자·세부유형 점수 중복이 있습니다.")
    if type_scores.empty:
        raise ValueError("계산할 격자별 점수가 없습니다.")

    pairs = [(category, subtype) for category in CATEGORIES for subtype in selection[category]]
    selected_index = pd.MultiIndex.from_tuples(pairs, names=[CATEGORY_COLUMN, SUBTYPE_COLUMN])
    row_types = pd.MultiIndex.from_frame(type_scores[[CATEGORY_COLUMN, SUBTYPE_COLUMN]])
    chosen = type_scores.loc[row_types.isin(selected_index)].copy()
    chosen["score"] = pd.to_numeric(chosen["score"], errors="raise")
    if not chosen["score"].dropna().between(0, 100).all():
        raise ValueError("세부 시설 점수는 0~100 범위여야 합니다.")

    grid_ids = pd.Index(type_scores["grid_id"].drop_duplicates(), name="grid_id")
    matrix = chosen.pivot(index="grid_id", columns=[CATEGORY_COLUMN, SUBTYPE_COLUMN], values="score")
    matrix = matrix.reindex(index=grid_ids, columns=selected_index)
    result = pd.DataFrame(index=grid_ids)
    contributions = []
    for category in CATEGORIES:
        if selection[category]:
            # 선택한 유형 하나라도 점수가 없으면 평균도 미확정입니다.
            result[f"{category}_score"] = matrix[category].mean(axis=1, skipna=False)
            if normalized[category] > 0:
                contributions.append(result[f"{category}_score"] * normalized[category])
        else:
            result[f"{category}_score"] = float("nan")
    result["total_score"] = pd.concat(contributions, axis=1).sum(axis=1, min_count=len(contributions))
    result["eligible_for_ranking"] = result["total_score"].notna()
    result["rank"] = result["total_score"].rank(method="min", ascending=False).astype("Int64")
    return result.reset_index()
