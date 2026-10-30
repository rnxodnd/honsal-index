"""버스 노선별 경유 정류장 원본 → app/data/chuncheon_bus.json (화면용)

fetch_bus_routes.py 로 받은 data/raw/bus_routes_15060075.json 을
app/js/transport.js 가 읽는 형식(version 1: meta·stops·routes)으로 변환한다.
- 노선 ID 하나에 노선번호가 여러 개인 원본 오류는 표시를 보류하고 meta.withheldRoutes 에 기록한다.
- 정류장 이름·좌표가 행마다 다르면 가장 많이 나온 이름과 첫 좌표를 쓴다.

사용법 (프로젝트 폴더에서, 인터넷 불필요):
    python src/data/build_bus_json.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "bus_routes_15060075.json"
OUT = ROOT / "app" / "data" / "chuncheon_bus.json"


def main() -> int:
    if not RAW.exists():
        print(f"{RAW} 이 없습니다. 먼저 python src/data/fetch_bus_routes.py 를 실행하세요.")
        return 1
    rows = json.loads(RAW.read_text(encoding="utf-8"))["data"]

    by_route: dict[str, list[dict]] = defaultdict(list)
    stop_names: dict[str, Counter] = defaultdict(Counter)
    stop_coords: dict[str, tuple[float, float]] = {}
    for row in rows:
        route_id = str(row["노선"]).strip()
        stop_id = str(row["정류장"]).strip()
        by_route[route_id].append(row)
        stop_names[stop_id][str(row["정류장명"]).strip()] += 1
        if stop_id not in stop_coords:
            stop_coords[stop_id] = (round(float(row["위도"]), 6), round(float(row["경도"]), 6))

    stops = [
        {"id": sid, "name": stop_names[sid].most_common(1)[0][0],
         "lat": stop_coords[sid][0], "lng": stop_coords[sid][1]}
        for sid in sorted(stop_coords)
    ]
    stop_name = {s["id"]: s["name"] for s in stops}

    routes, withheld = [], []
    for route_id, visits in by_route.items():
        numbers = {str(v["노선번호"]).strip() for v in visits}
        if len(numbers) != 1:
            withheld.append({"id": route_id, "numbers": sorted(numbers)})
            continue
        visits = sorted(visits, key=lambda v: int(v["정류장순서"]))
        orders = [int(v["정류장순서"]) for v in visits]
        if len(orders) != len(set(orders)):
            withheld.append({"id": route_id, "numbers": sorted(numbers), "reason": "정류장 순서 중복"})
            continue
        routes.append({
            "id": route_id,
            "number": numbers.pop(),
            "dates": sorted({str(v["데이터기준일"]) for v in visits}),
            "stops": [{"id": str(v["정류장"]).strip(), "name": stop_name[str(v["정류장"]).strip()],
                       "order": int(v["정류장순서"])} for v in visits],
        })
    routes.sort(key=lambda r: (len(r["number"]), r["number"]))

    payload = {
        "version": 1,
        "meta": {
            "source": "강원특별자치도 춘천시 버스 노선별 경유 정류장 (공공데이터포털 15060075)",
            "dates": sorted({str(r["데이터기준일"]) for r in rows}),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "withheldRoutes": withheld,
            "counts": {"rows": len(rows), "routes": len(routes), "stops": len(stops)},
        },
        "stops": stops,
        "routes": routes,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"노선 {len(routes)}개 · 정류장 {len(stops):,}곳 · 보류 {len(withheld)}건")
    print(f"저장 → {OUT} ({OUT.stat().st_size / 1024:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
