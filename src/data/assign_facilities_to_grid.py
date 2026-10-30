"""시설 좌표에 500m 격자 ID를 붙이고 세부 유형별·주변 3×3 시설 수를 만듭니다.

후보 격자 밖의 시설도 보존합니다. 집계는 원본 시설 수이며 접근성 점수가 아닙니다.
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data/processed"
GRID_SIZE = 500
TYPE_COLUMNS = ["analysis_category", "analysis_subtype"]
COUNT_KEYS = ["grid_id", *TYPE_COLUMNS]
TO_METERS = Transformer.from_crs(4326, 5179, always_xy=True)


def grid_origins(ids: pd.Series) -> pd.DataFrame:
    parts = ids.astype("string").str.extract(r"^G500_(-?\d+)_(-?\d+)$")
    if parts.isna().any().any():
        raise ValueError("격자 ID는 G500_x0_y0 형식이어야 합니다.")
    origins = parts.astype("int64")
    origins.columns = ["x0", "y0"]
    if origins.mod(GRID_SIZE).ne(0).any().any():
        raise ValueError("격자 원점 좌표는 500m 배수여야 합니다.")
    return origins


def validate_grids(grids: pd.DataFrame) -> None:
    required = {"grid_id", "x_center", "y_center", "lon", "lat"}
    if not required.issubset(grids.columns) or grids.empty:
        raise ValueError("후보 격자 자료 또는 필수 컬럼이 없습니다.")
    if grids.grid_id.duplicated().any():
        raise ValueError("후보 격자 ID가 중복됩니다.")
    origins = grid_origins(grids.grid_id)
    values = grids[["x_center", "y_center", "lon", "lat"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("격자 중심점 좌표가 비었거나 유효하지 않습니다.")
    for axis in ("x", "y"):
        if not np.allclose(values[f"{axis}_center"], origins[f"{axis}0"] + GRID_SIZE / 2, atol=1e-6, rtol=0):
            raise ValueError("격자 중심점이 ID의 500m 격자와 일치하지 않습니다.")
    x, y = TO_METERS.transform(values.lon.to_numpy(), values.lat.to_numpy(), errcheck=True)
    # 기존 격자의 위경도는 소수점 여섯 자리입니다. 반올림 오차만 허용합니다.
    if not (np.allclose(x, values.x_center, atol=0.15, rtol=0)
            and np.allclose(y, values.y_center, atol=0.15, rtol=0)):
        raise ValueError("격자 위경도가 EPSG:5179 중심점과 일치하지 않습니다.")


def assign_facilities(
    facilities: pd.DataFrame, grids: pd.DataFrame, city_boundary=None,
) -> pd.DataFrame:
    """각 시설을 하나의 격자에 배정합니다. 후보 포함·행정경계 포함은 별도 표시합니다."""
    validate_grids(grids)
    required = {"facility_id", "lon", "lat", *TYPE_COLUMNS}
    if not required.issubset(facilities.columns) or facilities.empty:
        raise ValueError("시설 자료 또는 필수 컬럼이 없습니다.")
    for column in ["facility_id", *TYPE_COLUMNS]:
        values = facilities[column].astype("string")
        if values.isna().any() or values.str.strip().eq("").any():
            raise ValueError(f"시설 필수 값이 비어 있습니다: {column}")
    if facilities.facility_id.duplicated().any():
        raise ValueError("시설 ID가 중복됩니다.")
    coordinates = facilities[["lon", "lat"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(coordinates.to_numpy(dtype=float)).all():
        raise ValueError("좌표가 없거나 잘못된 시설이 있습니다. 누락 시설을 0개로 집계하지 않습니다.")
    if not (coordinates.lon.between(-180, 180) & coordinates.lat.between(-90, 90)).all():
        raise ValueError("시설 위경도가 범위를 벗어났습니다.")
    x, y = TO_METERS.transform(coordinates.lon.to_numpy(), coordinates.lat.to_numpy(), errcheck=True)
    origins = np.floor(np.column_stack([x, y]) / GRID_SIZE).astype("int64") * GRID_SIZE
    result = facilities.copy()
    result["grid_id"] = [f"G500_{gx}_{gy}" for gx, gy in origins]
    result["in_candidate_grid"] = result.grid_id.isin(grids.grid_id)
    if city_boundary is None:
        result["in_city_boundary"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    else:
        if city_boundary.is_empty or not city_boundary.is_valid:
            raise ValueError("춘천 행정경계가 비었거나 유효하지 않습니다.")
        points = gpd.GeoSeries(gpd.points_from_xy(coordinates.lon, coordinates.lat), crs=4326)
        result["in_city_boundary"] = points.covered_by(city_boundary).to_numpy()
    return result


def count_facilities(assigned: pd.DataFrame) -> pd.DataFrame:
    """모든 시설 점유 격자를 집계합니다. 후보 격자에 한정하지 않습니다."""
    if assigned.facility_id.duplicated().any():
        raise ValueError("시설 ID 중복으로 이중 집계될 수 있습니다.")
    return assigned.groupby(COUNT_KEYS, as_index=False).agg(facility_count=("facility_id", "size"))


def count_neighbors(counts: pd.DataFrame, grids: pd.DataFrame) -> pd.DataFrame:
    """후보 중심 격자마다 3×3 범위의 모든 세부 유형을 집계합니다."""
    validate_grids(grids)
    if counts.empty or counts.duplicated(COUNT_KEYS).any():
        raise ValueError("시설 집계가 비었거나 격자·세부 유형이 중복됩니다.")
    values = pd.to_numeric(counts.facility_count, errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all() or (values < 0).any() or values.mod(1).ne(0).any():
        raise ValueError("시설 개수는 0 이상의 정수여야 합니다.")
    source = counts.copy()
    source["facility_count"] = values.astype("int64")
    origins = grid_origins(source.grid_id)
    candidates = set(grids.grid_id)
    shifted = []
    for dy in (-GRID_SIZE, 0, GRID_SIZE):
        for dx in (-GRID_SIZE, 0, GRID_SIZE):
            block = source.copy()
            block["grid_id"] = "G500_" + (origins.x0 + dx).astype(str) + "_" + (origins.y0 + dy).astype(str)
            shifted.append(block.loc[block.grid_id.isin(candidates)])
    nearby = pd.concat(shifted, ignore_index=True).groupby(COUNT_KEYS, as_index=False).facility_count.sum()
    # 확보한 세부 유형만 확장합니다. 누락된 유형의 자료를 임의로 만들어내지 않습니다.
    types = source[TYPE_COLUMNS].drop_duplicates().sort_values(TYPE_COLUMNS)
    template = grids[["grid_id"]].merge(types, how="cross")
    result = template.merge(nearby, on=COUNT_KEYS, how="left", validate="one_to_one")
    result["facility_count"] = result.facility_count.fillna(0).astype("int64")
    return result.sort_values(COUNT_KEYS).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facilities", type=Path, default=DATA_DIR / "chuncheon_facilities_classified.csv")
    parser.add_argument("--grids", type=Path, default=DATA_DIR / "grid_500m_filtered.csv")
    parser.add_argument("--boundary", type=Path, default=PROJECT_DIR / "data/raw/chuncheon_dong.geojson")
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    facilities = pd.read_csv(args.facilities, encoding="utf-8-sig", dtype="string")
    grids = pd.read_csv(args.grids, encoding="utf-8-sig", dtype="string")
    boundary = gpd.read_file(args.boundary).to_crs(4326)
    assigned = assign_facilities(facilities, grids, boundary.geometry.union_all())
    counts = count_facilities(assigned)
    neighbors = count_neighbors(counts, grids)
    if counts.facility_count.sum() != len(facilities):
        raise ValueError("시설 수가 보존되지 않았습니다.")
    outputs = {
        "chuncheon_facilities_with_grid.csv": assigned,
        "grid_facility_counts.csv": counts,
        "grid_3x3_facility_counts.csv": neighbors,
    }
    # 모든 계산과 검증이 끝난 다음 파일을 저장합니다.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        frame.to_csv(args.output_dir / name, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {name} — {len(frame):,}행")
    print(f"시설 {len(assigned):,}개 / 시설이 있는 격자 {assigned.grid_id.nunique():,}개")
    print(f"후보 격자 안 {assigned.in_candidate_grid.sum():,}개 / 밖 {(~assigned.in_candidate_grid).sum():,}개")
    print(f"행정경계 밖 {(~assigned.in_city_boundary).sum():,}개 (원본 보존, 상태 표시)")
    print("3×3 범위는 1.5km 정사각형입니다. 시설 수는 도보 시간이나 0~100점이 아닙니다.")


if __name__ == "__main__":
    main()
