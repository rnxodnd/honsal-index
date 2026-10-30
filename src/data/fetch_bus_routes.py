"""춘천 버스 노선별 경유 정류장 API(공공데이터포털 15060075) 수집

api.odcloud.kr 의 파일데이터 API를 페이지별로 끝까지 받아
data/raw/bus_routes_15060075.json 에 저장하고, 컬럼 이름과 샘플 행을 출력한다.

준비:
    .env 에 MOLIT_SERVICE_KEY=공공데이터포털_인증키 (실거래가와 같은 키)
    다른 키를 쓰려면 ODCLOUD_SERVICE_KEY=키 를 따로 넣으면 그 키를 우선 사용한다.

사용법 (프로젝트 폴더에서):
    python src/data/fetch_bus_routes.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "bus_routes_15060075.json"
URL = "https://api.odcloud.kr/api/15060075/v1/uddi:62b198b3-07fe-4a9e-b407-a51eec11694a"
PER_PAGE = 5000


def service_key() -> str:
    for name in ("ODCLOUD_SERVICE_KEY", "MOLIT_SERVICE_KEY"):
        key = os.getenv(name)
        if key:
            return key
    env = ROOT / ".env"
    if env.exists():
        values = {}
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
        for name in ("ODCLOUD_SERVICE_KEY", "MOLIT_SERVICE_KEY"):
            if values.get(name):
                return values[name]
    raise RuntimeError(".env 파일에 MOLIT_SERVICE_KEY=키 를 넣어주세요.")


def fetch_page(session: requests.Session, page: int, key: str) -> dict:
    params = {"page": page, "perPage": PER_PAGE, "serviceKey": key}
    for attempt in range(1, 4):
        try:
            response = session.get(URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            if attempt == 3:
                raise RuntimeError(f"{page}페이지 실패: {error}") from error
            time.sleep(2 * attempt)
    raise RuntimeError("unreachable")


def main() -> int:
    key = service_key()
    session = requests.Session()
    rows: list[dict] = []
    page = 1
    total = None
    while True:
        body = fetch_page(session, page, key)
        data = body.get("data") or []
        total = body.get("totalCount", total)
        rows.extend(data)
        print(f"  {page}페이지: {len(data):,}행 (누적 {len(rows):,} / 전체 {total})")
        # totalCount를 다 받거나 빈 페이지가 오면 끝
        if not data or (total is not None and len(rows) >= int(total)):
            break
        page += 1
        time.sleep(0.2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"totalCount": total, "data": rows}, ensure_ascii=False), encoding="utf-8")
    print(f"\n총 {len(rows):,}행 저장 → {OUT}")

    if rows:
        columns = list(rows[0].keys())
        print(f"\n컬럼 {len(columns)}개: {columns}")
        print("\n샘플 3행:")
        for row in rows[:3]:
            print(" ", json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
