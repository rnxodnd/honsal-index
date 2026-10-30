"""사람이 사는 격자만 남기는 스크립트

make_grid.py로 만든 500m 격자에 SGIS 1km 격자 통계(인구·가구·1인가구)를 붙이고,
인구가 없는 격자와 춘천 경계에 살짝만 걸친 격자를 제거한다.

사용법 (honsal-index 폴더에서):
    python src/filter_grid.py

옵션:
    --size       격자 크기 (기본 500, make_grid.py와 같게)
    --min-pop    남길 최소 인구 (기본 1명, 상위 1km 격자 기준)
    --min-ratio  춘천 경계 안에 들어간 최소 비율 (기본 0.3)

결과 (data/processed/):
    grid_500m_filtered.csv      남은 격자 + 인구·가구·1인가구 (1km 기준)
    grid_500m_filtered.geojson  남은 격자 폴리곤 (지도용)
    grid_500m_filtered_preview.html  확인용 지도 (folium 있을 때)

참고:
    SGIS 무료 제공 격자 통계는 1km 단위다. 500m 격자는 자신이 속한 1km 격자의 값을 그대로 받는다.
    통계 파일에 없는 1km 격자 = 인구 0으로 본다.
"""
import argparse
import csv
import json
from pathlib import Path

SGIS_DIR = Path("data/raw/sgis_grid/국가데이터처_SGIS 격자 통계 및 경계/1. 통계")
OUT_DIR = Path("data/processed")

# 국가지점번호 100km 격자 문자 (EPSG:5179 기준)
X_LETTERS = "가나다라마바사"      # x 700,000m 부터 100km 간격
Y_LETTERS = "가나다라마바사아"    # y 1,300,000m 부터 100km 간격

STAT_FILES = {
    "pop": ("1. 2024년 격자 통계(인구)", "2024년_인구_{}_1K.csv", {"to_in_001": "pop_1km"}),
    "hh": ("2. 2024년 격자 통계(가구)", "2024년_가구_{}_1K.csv",
           {"to_ga_001": "hh_1km", "ga_sd_005": "single_hh_1km"}),
}


def km_code(x: float, y: float) -> str:
    """좌표가 속한 1km 격자 코드 (예: 라사2765)."""
    xi, yi = int(x // 1000), int(y // 1000)
    return X_LETTERS[(xi - 700) // 100] + Y_LETTERS[(yi - 1300) // 100] + f"{xi % 100:02d}{yi % 100:02d}"


def read_csv(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 읽을 수 없어요: {path}")


def load_stats(blocks: set[str]) -> dict[str, dict[str, int]]:
    """필요한 100km 블록의 1km 통계만 읽는다."""
    stats: dict[str, dict[str, int]] = {}
    for folder, pattern, items in STAT_FILES.values():
        for block in sorted(blocks):
            path = SGIS_DIR / folder / pattern.format(block)
            if not path.exists():
                print(f"  (없음) {path.name}")
                continue
            for r in read_csv(path):
                col = items.get(r["통계항목"])
                if col:
                    stats.setdefault(r["격자코드"], {})[col] = int(r["통계값"])
    return stats


def main():
    p = argparse.ArgumentParser(description="사람 사는 격자만 남기기")
    p.add_argument("--size", type=int, default=500)
    p.add_argument("--min-pop", type=int, default=1)
    p.add_argument("--min-ratio", type=float, default=0.3)
    args = p.parse_args()

    base = OUT_DIR / f"grid_{args.size}m"
    cells = read_csv(Path(f"{base}.csv"))

    for c in cells:
        c["km_code"] = km_code(float(c["x_center"]), float(c["y_center"]))
    stats = load_stats({c["km_code"][:2] for c in cells})

    kept, drop_pop, drop_ratio = [], 0, 0
    for c in cells:
        s = stats.get(c["km_code"], {})
        c["pop_1km"] = s.get("pop_1km", 0)
        c["hh_1km"] = s.get("hh_1km", 0)
        c["single_hh_1km"] = s.get("single_hh_1km", 0)
        if c["pop_1km"] < args.min_pop:
            drop_pop += 1
        elif float(c["in_city_ratio"]) < args.min_ratio:
            drop_ratio += 1
        else:
            kept.append(c)

    # CSV 저장
    out_csv = Path(f"{base}_filtered.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(kept[0].keys()))
        w.writeheader()
        w.writerows(kept)

    # GeoJSON 저장 (남은 격자만 + 통계 속성 추가)
    by_id = {c["grid_id"]: c for c in kept}
    with open(f"{base}.geojson", encoding="utf-8") as f:
        gj = json.load(f)
    feats = []
    for ft in gj["features"]:
        c = by_id.get(ft["properties"]["grid_id"])
        if c:
            ft["properties"].update({k: c[k] for k in ("km_code", "pop_1km", "hh_1km", "single_hh_1km")})
            feats.append(ft)
    gj["features"] = feats
    out_gj = Path(f"{base}_filtered.geojson")
    with open(out_gj, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False)

    print(f"전체 {len(cells):,}개 → 남은 격자 {len(kept):,}개")
    print(f"  인구 {args.min_pop}명 미만 제거: {drop_pop:,}개")
    print(f"  경계 걸침({args.min_ratio:.0%} 미만) 제거: {drop_ratio:,}개")
    print(f"저장: {out_csv} / {out_gj}")

    preview(gj, base)


def preview(gj: dict, base: Path) -> None:
    """확인용 지도 (folium이 있을 때만)."""
    try:
        import folium
    except ImportError:
        return
    feats = gj["features"]
    lats = [float(by["properties"]["lat"]) for by in feats]
    lons = [float(by["properties"]["lon"]) for by in feats]
    m = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)], zoom_start=11, tiles=None)
    esri = "https://server.arcgisonline.com/ArcGIS/rest/services/{}/MapServer/tile/{{z}}/{{y}}/{{x}}"
    folium.TileLayer(esri.format("World_Street_Map"), attr="Tiles © Esri", name="일반 지도",
                     max_native_zoom=13, max_zoom=19).add_to(m)
    folium.TileLayer(esri.format("World_Imagery"), attr="Tiles © Esri", name="위성 지도",
                     max_native_zoom=18, max_zoom=19).add_to(m)

    def color(pop: int) -> str:
        return "#1e3a8a" if pop >= 3000 else "#2563eb" if pop >= 500 else "#60a5fa" if pop >= 50 else "#bfdbfe"

    folium.GeoJson(
        gj, name="사람 사는 격자",
        style_function=lambda f: {"color": "#1e3a8a", "weight": 0.4,
                                  "fillColor": color(f["properties"]["pop_1km"]), "fillOpacity": 0.45},
        tooltip=folium.GeoJsonTooltip(fields=["grid_id", "adm_nm", "pop_1km", "single_hh_1km"],
                                      aliases=["격자", "행정동", "인구(1km)", "1인가구(1km)"]),
    ).add_to(m)
    folium.LayerControl().add_to(m)
    m.save(f"{base}_filtered_preview.html")
    print(f"지도: {base}_filtered_preview.html")


if __name__ == "__main__":
    main()
