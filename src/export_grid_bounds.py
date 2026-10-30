"""격자별 위경도 범위(네 모서리) 내보내기 — 프론트엔드·DB용

make_grid.py가 만든 grid_500m.geojson(위경도 폴리곤)에서 격자마다 네 모서리 좌표를 꺼내
CSV 한 장으로 저장한다. 인구 필터 결과(grid_500m_filtered.csv)가 있으면 거주 여부와 인구도 붙인다.

사용법 (honsal-index 폴더에서):
    python src/export_grid_bounds.py

결과:
    data/processed/grid_500m_bounds.csv
      grid_id            격자 PK
      adm_nm             행정동
      is_populated       1 = 사람 사는 격자(지도에 표시), 0 = 인구 없음(3×3 계산·시설 연결용으로만 보관)
      center_lat/lon     격자 중심
      sw_/se_/ne_/nw_    남서·남동·북동·북서 모서리 위경도 (지도에 사각형 그릴 때)
      min_/max_lat/lon   위경도 최소·최대 (빠른 범위 검색용)
      pop_1km, hh_1km, single_hh_1km  1km 격자 인구·가구·1인가구 (인구 없는 격자는 0)
"""
import csv
import json
from pathlib import Path

D = Path("data/processed")
SIZE = 500


def main():
    gj = json.load(open(D / f"grid_{SIZE}m.geojson", encoding="utf-8"))
    base = {r["grid_id"]: r for r in csv.DictReader(open(D / f"grid_{SIZE}m.csv", encoding="utf-8-sig"))}
    filt_path = D / f"grid_{SIZE}m_filtered.csv"
    filt = {r["grid_id"]: r for r in csv.DictReader(open(filt_path, encoding="utf-8-sig"))} if filt_path.exists() else {}

    rows = []
    for ft in gj["features"]:
        gid = ft["properties"]["grid_id"]
        geom = ft["geometry"]
        ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
        pts = ring[:4]  # 사각형 꼭짓점 4개 (lon, lat)
        # 모서리 구분: 위도 작은 두 점 = 남쪽, 그중 경도 작은 쪽 = 남서
        south = sorted(sorted(pts, key=lambda p: p[1])[:2], key=lambda p: p[0])
        north = sorted(sorted(pts, key=lambda p: p[1])[2:], key=lambda p: p[0])
        sw, se, nw, ne = south[0], south[1], north[0], north[1]
        b, f = base[gid], filt.get(gid)
        rows.append({
            "grid_id": gid,
            "adm_nm": b["adm_nm"],
            "is_populated": 1 if f else 0,
            "center_lat": b["lat"], "center_lon": b["lon"],
            "sw_lat": round(sw[1], 7), "sw_lon": round(sw[0], 7),
            "se_lat": round(se[1], 7), "se_lon": round(se[0], 7),
            "ne_lat": round(ne[1], 7), "ne_lon": round(ne[0], 7),
            "nw_lat": round(nw[1], 7), "nw_lon": round(nw[0], 7),
            "min_lat": round(min(p[1] for p in pts), 7), "max_lat": round(max(p[1] for p in pts), 7),
            "min_lon": round(min(p[0] for p in pts), 7), "max_lon": round(max(p[0] for p in pts), 7),
            "pop_1km": f["pop_1km"] if f else 0,
            "hh_1km": f["hh_1km"] if f else 0,
            "single_hh_1km": f["single_hh_1km"] if f else 0,
        })

    out = D / f"grid_{SIZE}m_bounds.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows):,}개 격자 (거주 {sum(r['is_populated'] for r in rows):,}개) → {out}")


if __name__ == "__main__":
    main()
