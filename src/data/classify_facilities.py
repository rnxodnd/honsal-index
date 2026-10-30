"""의료·교통 통합 CSV에 사용자 선택용 분류를 추가합니다.

상권 담당자가 공통 분류를 붙인 CSV는 --commerce 경로로 추가할 수 있습니다.
원본 업종 코드를 실제로 확인하기 전에는 상호명으로 분류하지 않습니다.
"""

import argparse
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data" / "processed"
LABELS = {
    "daily_life": "생활시설", "healthcare": "의료",
    "transport": "교통", "leisure_community": "여가시설",
}
MEDICAL_TYPES = {
    "의원", "치과의원", "한의원", "보건진료소", "보건지소", "요양병원",
    "정신병원", "병원", "종합병원", "보건소", "한방병원",
}
RULES = {
    **{("medical", kind): ("healthcare", kind) for kind in MEDICAL_TYPES},
    ("pharmacy", "약국"): ("healthcare", "약국"),
    ("bus_stop", "버스정류장"): ("transport", "버스정류장"),
    ("rail_station", "철도역"): ("transport", "철도역"),
}
REQUIRED = ["facility_id", "name", "city", "lat", "lon", "source", "source_file", "source_url", "data_date"]


def read_facilities(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype="string")
    frame = frame.apply(lambda column: column.str.strip())
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {path.name}: {sorted(missing)}")
    frame["input_dataset"] = path.name
    return frame


def classify_existing(frame: pd.DataFrame) -> pd.DataFrame:
    """원본 category/facility_type/식별자를 보존하고 별도 분석 컬럼을 붙입니다."""
    if not {"category", "facility_type"}.issubset(frame.columns):
        raise ValueError("기존 자료에 category와 facility_type이 필요합니다.")
    result = frame.copy()
    pairs = list(zip(result["category"], result["facility_type"]))
    unknown = [pair for pair in pairs if pair not in RULES]
    if unknown:
        raise ValueError(f"분류 규칙을 확인해야 하는 시설이 있습니다: {unknown[:5]}")
    result["analysis_category"] = [RULES[pair][0] for pair in pairs]
    result["analysis_subtype"] = [RULES[pair][1] for pair in pairs]
    return result


def combine_classified(frames: list[pd.DataFrame]) -> pd.DataFrame:
    result = pd.concat(frames, ignore_index=True, sort=False)
    for column in [*REQUIRED, "analysis_category", "analysis_subtype"]:
        if column not in result:
            raise ValueError(f"필수 컬럼 누락: {column}")
        if column not in ("lat", "lon"):
            if result[column].isna().any() or result[column].astype("string").str.strip().eq("").any():
                raise ValueError(f"필수 값 누락: {column}")
    if result["facility_id"].duplicated().any():
        raise ValueError("시설 ID가 중복됩니다. 통합 파일과 개별 파일을 동시에 합치지 마세요.")
    if not result["city"].eq("춘천시").all():
        raise ValueError("춘천시 밖의 자료가 포함되어 있습니다.")
    if not result["analysis_category"].isin(LABELS).all():
        raise ValueError("분석 범위 밖의 항목 또는 미분류 시설이 있습니다.")

    for column, bounds in (("lat", (-90, 90)), ("lon", (-180, 180))):
        original = result[column].replace("", pd.NA)
        numeric = pd.to_numeric(original, errors="coerce")
        if (original.notna() & numeric.isna()).any() or not numeric.dropna().between(*bounds).all():
            raise ValueError(f"좌표를 확인하세요: {column}")
        result[column] = numeric
    result["has_coordinates"] = result["lat"].notna() & result["lon"].notna()
    if "has_itx" in result:
        raw = result["has_itx"].astype("string").str.lower().replace("", pd.NA)
        if not raw.dropna().isin(["true", "false"]).all():
            raise ValueError("has_itx는 True/False 또는 해당 없음이어야 합니다.")
        result["has_itx"] = raw.map({"true": True, "false": False}).astype("boolean")
    result["analysis_category_label"] = result["analysis_category"].map(LABELS)
    return result.sort_values(["analysis_category", "analysis_subtype", "facility_id"]).reset_index(drop=True)


def make_catalog(facilities: pd.DataFrame) -> pd.DataFrame:
    return facilities.groupby(
        ["analysis_category", "analysis_category_label", "analysis_subtype"], as_index=False,
    ).agg(facility_count=("facility_id", "size"), located_count=("has_coordinates", "sum"))


def make_status(facilities: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for category, label in LABELS.items():
        group = facilities.loc[facilities["analysis_category"].eq(category)]
        available = not group.empty
        rows.append({
            "analysis_category": category, "analysis_category_label": label,
            "status": "classified" if available else "awaiting_data",
            "status_label": "분류 완료" if available else "자료 준비 중",
            "facility_count": len(group) if available else pd.NA,
            "subtype_count": group["analysis_subtype"].nunique() if available else pd.NA,
            "located_count": group["has_coordinates"].sum() if available else pd.NA,
        })
    status = pd.DataFrame(rows)
    for column in ("facility_count", "subtype_count", "located_count"):
        status[column] = status[column].astype("Int64")
    return status


def build_classified(data_dir: Path = DATA_DIR, commerce: Path | None = None) -> pd.DataFrame:
    # 이미 합쳐진 두 파일만 읽어 의료·교통의 개별 파일이 다시 더해지는 것을 막습니다.
    frames = [classify_existing(read_facilities(data_dir / name)) for name in (
        "chuncheon_medical_facilities.csv", "chuncheon_transport_facilities.csv",
    )]
    if commerce is None:
        default_commerce = data_dir / "chuncheon_commerce_facilities.csv"
        if default_commerce.is_file():
            commerce = default_commerce
    if commerce is not None:
        shops = read_facilities(commerce)
        needed = {"analysis_category", "analysis_subtype", "source_business_code", "source_business_name"}
        if not needed.issubset(shops.columns):
            raise ValueError(f"상권 자료에 분류/원본 업종 컬럼이 필요합니다: {sorted(needed)}")
        if not shops["analysis_category"].isin(["daily_life", "leisure_community"]).all():
            raise ValueError("상권 자료는 생활시설·여가시설로 분류한 행만 추가하세요.")
        for column in needed:
            if shops[column].isna().any() or shops[column].eq("").any():
                raise ValueError(f"상권 자료의 값이 비어 있습니다: {column}")
        frames.append(shops)
    return combine_classified(frames)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commerce", type=Path, help="공통 형식 상권 CSV (생략 시 기본 상권 파일 자동 포함)")
    args = parser.parse_args()
    facilities = build_classified(commerce=args.commerce)
    outputs = {
        "chuncheon_facilities_classified.csv": facilities,
        "facility_type_catalog.csv": make_catalog(facilities),
        "facility_dataset_status.csv": make_status(facilities),
    }
    for filename, frame in outputs.items():
        frame.to_csv(DATA_DIR / filename, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {filename} — {len(frame):,}행")
    print(outputs["facility_dataset_status.csv"].to_string(index=False))


if __name__ == "__main__":
    main()
