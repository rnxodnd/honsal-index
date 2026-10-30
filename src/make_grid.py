"""춘천시 격자 생성 스크립트

사용법 (honsal-index 폴더에서, 가상환경 켠 상태):
    python src/make_grid.py --boundary data/raw/행정동경계.geojson

옵션:
    --city   대상 시군 이름 (기본: 춘천시)
    --size   격자 크기, 미터 (기본: 500)

결과 (data/processed/):
    grid_500m.geojson       격자 폴리곤 (지도 색칠용, 위경도)
    grid_500m.csv           격자 중심점 좌표 (거리 계산용)
    grid_500m_preview.html  확인용 지도
"""
import argparse
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
from shapely.geometry import box

CRS_M = "EPSG:5179"   # 미터 단위 좌표계 (거리 계산용)
CRS_LL = "EPSG:4326"  # 위경도 (지도 표시용)
OUT_DIR = Path("data/processed")


def load_city(path: str, city: str) -> gpd.GeoDataFrame:
    """행정동 경계 파일에서 대상 시군의 행정동만 꺼낸다."""
    gdf = gpd.read_file(path)

    # 행정동 이름 컬럼 찾기 (보통 adm_nm: '강원특별자치도 춘천시 효자1동')
    text_cols = [c for c in gdf.columns if c != "geometry"]
    if "adm_nm" in gdf.columns:
        name_col = "adm_nm"
    else:
        name_col = next((c for c in text_cols if gdf[c].astype(str).str.contains(city).any()), None)
        if name_col is None:
            raise SystemExit(f"'{city}'가 들어간 이름 컬럼을 찾지 못했어요. 컬럼: {list(gdf.columns)}")

    area = gdf[gdf[name_col].astype(str).str.contains(city)].copy()
    if area.empty:
        raise SystemExit(f"경계 파일에 '{city}' 행정동이 없어요.")

    area["adm_nm"] = area[name_col].astype(str).str.split().str[-1]  # 마지막 단어 = 동 이름
    keep = ["adm_nm"] + (["adm_cd"] if "adm_cd" in area.columns else [])
    return area[keep + ["geometry"]].to_crs(CRS_M)


def make_grid(area: gpd.GeoDataFrame, size: int) -> gpd.GeoDataFrame:
    """시 경계를 덮는 정사각 격자를 만들고, 경계에 걸치는 격자만 남긴다."""
    city = area.union_all() if hasattr(area, "union_all") else area.unary_union

    # 격자 시작점을 size의 배수로 맞춤 (다른 격자 데이터와 맞추기 쉽게)
    minx, miny, maxx, maxy = area.total_bounds
    minx, miny = np.floor(minx / size) * size, np.floor(miny / size) * size
    maxx, maxy = np.ceil(maxx / size) * size, np.ceil(maxy / size) * size

    xs, ys = np.meshgrid(np.arange(minx, maxx, size), np.arange(miny, maxy, size))
    xs, ys = xs.ravel(), ys.ravel()

    cells = gpd.GeoDataFrame(
        {"x0": xs.astype(int), "y0": ys.astype(int)},
        geometry=[box(x, y, x + size, y + size) for x, y in zip(xs, ys)],
        crs=CRS_M,
    )
    cells = cells[cells.intersects(city)].copy()

    cells["grid_id"] = f"G{size}_" + cells["x0"].astype(str) + "_" + cells["y0"].astype(str)
    cells["in_city_ratio"] = (cells.intersection(city).area / size**2).round(3)  # 시 안에 들어간 비율
    return cells


def attach_dong(cells: gpd.GeoDataFrame, area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """격자 중심점이 속한(또는 가장 가까운) 행정동 이름을 붙인다."""
    cells = cells.reset_index(drop=True)
    cent = gpd.GeoDataFrame(cells[["grid_id"]].copy(), geometry=cells.centroid.values, crs=CRS_M)

    joined = gpd.sjoin_nearest(cent, area, how="left").drop_duplicates("grid_id")
    cols = [c for c in ["adm_nm", "adm_cd"] if c in joined.columns]
    cells = cells.merge(joined[["grid_id"] + cols], on="grid_id", how="left")

    cells["x_center"] = cent.geometry.x.values
    cells["y_center"] = cent.geometry.y.values
    cent_ll = cent.to_crs(CRS_LL)
    cells["lon"] = cent_ll.geometry.x.values.round(6)
    cells["lat"] = cent_ll.geometry.y.values.round(6)
    return cells


def save(cells: gpd.GeoDataFrame, size: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = OUT_DIR / f"grid_{size}m"
    cols = ["grid_id", "adm_nm"] + (["adm_cd"] if "adm_cd" in cells else []) + [
        "x_center", "y_center", "lon", "lat", "in_city_ratio"]

    grid_ll = cells[cols + ["geometry"]].to_crs(CRS_LL)
    grid_ll.to_file(f"{base}.geojson", driver="GeoJSON")
    cells[cols].to_csv(f"{base}.csv", index=False, encoding="utf-8-sig")

    m = folium.Map(location=[cells["lat"].mean(), cells["lon"].mean()], zoom_start=11, tiles=None)
    esri = "https://server.arcgisonline.com/ArcGIS/rest/services/{}/MapServer/tile/{{z}}/{{y}}/{{x}}"
    # 일반 지도: 한국은 고배율 타일이 없어 13단계까지만 받고 그 이상은 늘려서 표시
    folium.TileLayer(esri.format("World_Street_Map"), attr="Tiles © Esri", name="일반 지도",
                     max_native_zoom=13, max_zoom=19).add_to(m)
    # 위성 지도: 한국도 고배율 이미지가 있어 크게 확대해도 선명함
    folium.TileLayer(esri.format("World_Imagery"), attr="Tiles © Esri", name="위성 지도",
                     max_native_zoom=18, max_zoom=19).add_to(m)
    folium.GeoJson(
        grid_ll,
        name="격자",
        style_function=lambda f: {"color": "#2563eb", "weight": 0.5, "fillOpacity": 0.05},
        tooltip=folium.GeoJsonTooltip(fields=["grid_id", "adm_nm"], aliases=["격자", "행정동"]),
    ).add_to(m)
    folium.LayerControl().add_to(m)  # 오른쪽 위에서 지도 종류 선택
    m.save(f"{base}_preview.html")

    print(f"격자 {len(cells):,}개 생성 → {base}.geojson / .csv / _preview.html")
    print("행정동별 격자 수 (상위 10):")
    print(cells["adm_nm"].value_counts().head(10).to_string())


def main():
    p = argparse.ArgumentParser(description="시군 격자 생성")
    p.add_argument("--boundary", required=True, help="행정동 경계 GeoJSON/SHP 경로")
    p.add_argument("--city", default="춘천시")
    p.add_argument("--size", type=int, default=500)
    args = p.parse_args()

    area = load_city(args.boundary, args.city)
    cells = make_grid(area, args.size)
    cells = attach_dong(cells, area)
    save(cells, args.size)


if __name__ == "__main__":
    main()
