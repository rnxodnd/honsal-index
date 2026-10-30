"""시설 데이터에 격자 ID 붙이기

시설 CSV(lon, lat 컬럼 필요)를 읽어 각 시설이 속한 500m 격자 ID를 계산하고,
그 격자가 사람 사는 격자인지(is_populated)를 함께 붙여 한 파일로 저장한다.
격자 ID 규칙은 locate.py, 프론트 가이드(proj4)와 같다.

사용법 (honsal-index 폴더에서):
    python src/assign_grid.py
    python src/assign_grid.py --input data/processed/a.csv data/processed/b.csv

결과:
    data/processed/facilities_grid.csv
      (원래 시설 컬럼) + grid_id + is_populated
      grid_id       시설이 속한 격자 (좌표 없으면 빈칸)
      is_populated  1 = 사람 사는 격자, 0 = 인구 없는 격자, 빈칸 = 춘천 격자 밖

프론트에서 3×3 격자 9개 ID로 grid_id를 걸러 시설을 표시·점수 계산에 쓴다.
원본 시설 파일은 수정하지 않는다.
"""
import argparse
import csv
from pathlib import Path

from pyproj import Transformer

D = Path("data/processed")
SIZE = 500
DEFAULT_INPUT = [D / "chuncheon_medical_facilities.csv"]
OUT = D / "facilities_grid.csv"
_TO_M = Transformer.from_crs(4326, 5179, always_xy=True)


def grid_id(lon: float, lat: float) -> str:
    x, y = _TO_M.transform(lon, lat)
    return f"G{SIZE}_{int(x // SIZE) * SIZE}_{int(y // SIZE) * SIZE}"


def read_csv(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 읽을 수 없어요: {path}")


def main():
    p = argparse.ArgumentParser(description="시설 데이터에 격자 ID 붙이기")
    p.add_argument("--input", nargs="+", type=Path, default=DEFAULT_INPUT)
    args = p.parse_args()

    # 격자 목록: grid_id → 거주 여부
    bounds = {r["grid_id"]: r["is_populated"] for r in read_csv(D / f"grid_{SIZE}m_bounds.csv")}

    rows, seen, fields = [], set(), []
    for path in args.input:
        for r in read_csv(path):
            fid = r.get("facility_id")
            if fid and fid in seen:          # 여러 파일에 같은 시설이 있으면 한 번만
                continue
            seen.add(fid)
            try:
                gid = grid_id(float(r["lon"]), float(r["lat"]))
            except (KeyError, TypeError, ValueError):
                gid = ""
            r["grid_id"] = gid
            r["is_populated"] = bounds.get(gid, "") if gid else ""
            rows.append(r)
            for k in r:
                if k not in fields:
                    fields.append(k)

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    no_xy = sum(1 for r in rows if not r["grid_id"])
    outside = sum(1 for r in rows if r["grid_id"] and r["is_populated"] == "")
    empty = sum(1 for r in rows if r["is_populated"] == "0")
    print(f"시설 {len(rows):,}개 → {OUT}")
    print(f"  사람 사는 격자 안: {sum(1 for r in rows if r['is_populated'] == '1'):,}개")
    print(f"  인구 없는 격자 안: {empty:,}개")
    print(f"  춘천 격자 밖: {outside:,}개 / 좌표 없음: {no_xy:,}개")
    print(f"  시설이 있는 격자 수: {len({r['grid_id'] for r in rows if r['grid_id']}):,}개")


if __name__ == "__main__":
    main()
