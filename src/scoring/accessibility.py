"""춘천 500m 격자의 선택 시설 접근성: 격자 중심 직선거리, 750m 선형 점수.

원본 분류 자료를 검증하고 서버 시작 시 격자를 배정합니다. 미리 생성한 집계
CSV에 의존하지 않으며, 후보 격자 밖 시설도 주변 3×3 검색에 포함합니다.
"""

import json
from collections.abc import Mapping
from numbers import Real
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point

from src.data.assign_facilities_to_grid import TO_METERS, assign_facilities
from src.locate import grid_id_from_lonlat, neighbors_3x3
from src.scoring.preferences import (
    CATEGORIES, available_facility_types, calculate_preference_scores,
    filter_facilities, normalize_selected_weights,
)


MAX_DISTANCE_M = 750.0
TO_LONLAT = Transformer.from_crs(5179, 4326, always_xy=True)
LABELS = {
    "daily_life": "생활 편의시설", "healthcare": "의료시설",
    "transport": "교통 편의시설", "leisure_community": "여가시설",
}
SCORING = {
    "method": "linear_nearest_distance", "max_distance_m": 750,
    "distance_basis": "grid_center_straight_line",
}


class AnalysisError(ValueError):
    """사용자 입력의 문제를 HTTP 계층이 일정한 오류 응답으로 변환합니다."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _text(value):
    """CSV의 빈 셀은 JSON null로 보냅니다."""
    return None if pd.isna(value) or str(value).strip() == "" else str(value)


def _rounded(value):
    return None if pd.isna(value) else round(float(value), 2)


class AccessibilityEngine:
    def __init__(self, facilities: pd.DataFrame, grids: pd.DataFrame,
                 boundary, weights: Mapping):
        if boundary is None or boundary.is_empty or not boundary.is_valid:
            raise ValueError("춘천 행정경계가 비었거나 유효하지 않습니다.")
        if "name" not in facilities.columns or facilities.name.isna().any():
            raise ValueError("시설 이름이 누락되었습니다.")
        if facilities.name.astype("string").str.strip().eq("").any():
            raise ValueError("시설 이름이 비어 있습니다.")
        # 좌표·ID·격자 중심의 검증을 통과해야만 '주변 시설 없음'을 0점으로 봅니다.
        self.facilities = assign_facilities(facilities, grids, boundary)
        self.facilities["lon"] = pd.to_numeric(self.facilities.lon)
        self.facilities["lat"] = pd.to_numeric(self.facilities.lat)
        x, y = TO_METERS.transform(
            self.facilities.lon.to_numpy(), self.facilities.lat.to_numpy(), errcheck=True,
        )
        self.facilities["_x"] = x
        self.facilities["_y"] = y
        self.available_types = available_facility_types(self.facilities)
        self.grids = grids.copy().set_index("grid_id", drop=False)
        for column in ("x_center", "y_center", "lon", "lat"):
            self.grids[column] = pd.to_numeric(self.grids[column])
        self.boundary = boundary
        self.weights = normalize_selected_weights(
            {category: ["검증용"] for category in CATEGORIES}, weights,
        )
        self.type_counts = self.facilities.groupby(
            ["analysis_category", "analysis_subtype"],
        ).size()

    @classmethod
    def from_project(cls, project_dir: Path):
        project_dir = Path(project_dir)
        processed = project_dir / "data" / "processed"
        facilities = pd.read_csv(
            processed / "chuncheon_facilities_classified.csv", encoding="utf-8-sig", dtype="string",
        )
        grids = pd.read_csv(
            processed / "grid_500m_filtered.csv", encoding="utf-8-sig", dtype="string",
        )
        boundaries = gpd.read_file(project_dir / "data" / "raw" / "chuncheon_dong.geojson")
        if boundaries.empty or boundaries.crs is None:
            raise ValueError("춘천 행정경계 또는 좌표계가 없습니다.")
        boundary = boundaries.to_crs(4326).geometry.union_all()
        weights = json.loads((project_dir / "config" / "weights.json").read_text(encoding="utf-8"))["weights"]
        return cls(facilities, grids, boundary, weights)

    def options(self) -> dict:
        return {
            "categories": [
                {
                    "key": category, "label": LABELS[category], "weight": self.weights[category],
                    "subtypes": [
                        {"name": subtype, "facility_count": int(self.type_counts.loc[(category, subtype)])}
                        for subtype in self.available_types[category]
                    ],
                }
                for category in CATEGORIES
            ],
            "scoring": dict(SCORING),
            "dataset": {"facility_count": len(self.facilities), "grid_count": len(self.grids)},
            "default_location": {"lon": 127.7298, "lat": 37.8813, "name": "춘천시청 인근"},
        }

    def analyze(self, lon, lat, selected, name=None) -> dict:
        # 먼저 범위를 비교하여 매우 큰 JSON 정수를 float로 변환하다 넘치지 않게 합니다.
        # NaN과 무한대도 아래의 범위 검사에서 거부됩니다.
        if (any(isinstance(value, bool) or not isinstance(value, Real) for value in (lon, lat))
                or not -180 <= lon <= 180 or not -90 <= lat <= 90):
            raise AnalysisError("invalid_coordinates", "경도와 위도를 유효한 숫자로 입력하세요.")
        lon, lat = float(lon), float(lat)
        if name is not None and not isinstance(name, str):
            raise AnalysisError("invalid_location_name", "위치 이름은 문자열이어야 합니다.")
        if not self.boundary.covers(Point(lon, lat)):
            raise AnalysisError("outside_city", "춘천시 안의 위치를 선택하세요.")
        grid_id = grid_id_from_lonlat(lon, lat)
        if grid_id not in self.grids.index:
            raise AnalysisError("outside_candidate_grid", "이 위치는 현재 분석 대상 격자에 포함되지 않습니다.")
        try:
            chosen = filter_facilities(self.facilities, selected)
            normalized = normalize_selected_weights(selected, self.weights)
        except (TypeError, ValueError) as error:
            raise AnalysisError("invalid_selection", str(error)) from error

        # 선택은 데이터에 실제 존재하는 항목만 남기고 중복을 제거합니다.
        selection = available_facility_types(chosen)
        grid = self.grids.loc[grid_id]
        center_x, center_y = float(grid.x_center), float(grid.y_center)
        neighbors = neighbors_3x3(grid_id)
        nearby = chosen.loc[chosen.grid_id.isin(neighbors)].copy()
        distances = np.hypot(nearby._x - center_x, nearby._y - center_y)
        # 좌표계 왕복 변환의 부동소수점 오차만 보정합니다(1 마이크로미터).
        distances = np.where(np.abs(distances - MAX_DISTANCE_M) < 1e-6, MAX_DISTANCE_M, distances)
        nearby["distance_m"] = np.where(np.abs(distances) < 1e-6, 0.0, distances)
        nearby = nearby.sort_values(["distance_m", "facility_id"])

        def facility_json(row):
            return {
                "facility_id": str(row.facility_id), "name": str(row["name"]),
                "category": str(row.analysis_category), "subtype": str(row.analysis_subtype),
                "lat": float(row.lat), "lon": float(row.lon),
                "address": _text(row.get("address")), "phone": _text(row.get("phone")),
                "distance_m": round(float(row.distance_m), 2),
                "in_city_boundary": bool(row.in_city_boundary),
            }

        types, score_rows = [], []
        for category in CATEGORIES:
            for subtype in selection[category]:
                matches = nearby.loc[
                    nearby.analysis_category.eq(category) & nearby.analysis_subtype.eq(subtype)
                ]
                nearest, score, status = None, 0.0, "no_facility_in_neighborhood"
                if not matches.empty:
                    first = matches.iloc[0]
                    distance = float(first.distance_m)
                    score = max(0.0, 100.0 * (1.0 - distance / MAX_DISTANCE_M))
                    # 정확히 750m도 0점입니다. 반경 내 개수는 경계점을 포함합니다.
                    status = "available" if distance < MAX_DISTANCE_M else "outside_scoring_radius"
                    nearest = {key: value for key, value in facility_json(first).items()
                               if key in ("facility_id", "name", "lat", "lon", "distance_m")}
                score_rows.append({"grid_id": grid_id, "analysis_category": category,
                                   "analysis_subtype": subtype, "score": score})
                types.append({
                    "category": category, "subtype": subtype, "score": round(score, 2),
                    "nearest": nearest, "count_3x3": len(matches),
                    "count_within_radius": int(matches.distance_m.le(MAX_DISTANCE_M).sum()),
                    "status": status,
                })

        # 내부 계산은 반올림 전 점수로 수행합니다.
        scores = calculate_preference_scores(pd.DataFrame(score_rows), selection, self.weights).iloc[0]
        west, south, east, north = TO_LONLAT.transform_bounds(
            center_x - 750, center_y - 750, center_x + 750, center_y + 750, densify_pts=21,
        )
        notices = [
            "거리는 검색 위치가 속한 500m 격자의 중심부터 잰 직선거리이며, 도보 거리나 시간이 아닙니다.",
            "주변 3×3 격자에서 선택 유형별 가장 가까운 시설을 찾고, 750m에서 0점이 되는 선형 점수를 계산합니다.",
            "각 항목은 선택 유형 점수의 평균입니다. 선택하지 않은 항목의 가중치는 나머지 항목에 비례하여 재분배됩니다.",
            "주변 시설 없음은 확보한 데이터 기준이며, 실제 시설의 부재를 보장하지 않습니다.",
        ]
        if not nearby.empty and not nearby.in_city_boundary.all():
            notices.append("원본 교통 자료 등에 포함된 춘천 행정경계 밖 시설도 생활권 안에 있으면 분석에 포함합니다.")
        return {
            "location": {"lon": lon, "lat": lat, "name": name},
            "grid": {"grid_id": grid_id, "adm_nm": _text(grid.get("adm_nm")),
                     "lon": float(grid.lon), "lat": float(grid.lat)},
            "neighborhood": {"grid_ids": neighbors, "bounds": {
                "south": float(south), "west": float(west), "north": float(north), "east": float(east),
            }},
            "scoring": dict(SCORING), "total_score": _rounded(scores.total_score),
            "categories": [
                {"key": category, "label": LABELS[category], "weight": normalized.get(category, 0.0),
                 "score": _rounded(scores[f"{category}_score"])}
                for category in CATEGORIES
            ],
            "types": types, "facilities": [facility_json(row) for _, row in nearby.iterrows()],
            "notices": notices,
        }
