"""국토교통부 실거래가 API(춘천시) 12개월치 수집

6종(아파트 전월세·매매, 연립다세대 전월세, 오피스텔 전월세·매매, 단독다가구 전월세)을
월별로 받아 data/raw/trades/ 에 JSON으로 저장한다.
응답의 totalCount가 한 페이지(numOfRows)를 넘으면 다음 페이지도 자동으로 받는다.

준비:
    .env 에 한 줄 추가 (GitHub에 올라가지 않음)
        MOLIT_SERVICE_KEY=공공데이터포털_인증키

사용법 (프로젝트 폴더에서):
    python src/data/fetch_trades.py
    python src/data/fetch_trades.py --start 202511 --end 202610

다음 단계:
    python src/data/geocode_trades.py   # 좌표·격자 ID 부여 → app/data/trades.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "trades"
BASE_URL = "https://apis.data.go.kr/1613000/"
LAWD_CD = "51110"  # 강원특별자치도 춘천시
NUM_OF_ROWS = 1000

# key: (API 경로, 화면 표시 이름, 거래 종류)
TRADE_TYPES = {
    "apt_rent": ("RTMSDataSvcAptRent/getRTMSDataSvcAptRent", "아파트 전월세", "rent"),
    "apt_trade": ("RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev", "아파트 매매", "trade"),
    "rh_rent": ("RTMSDataSvcRHRent/getRTMSDataSvcRHRent", "연립·다세대 전월세", "rent"),
    "offi_rent": ("RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent", "오피스텔 전월세", "rent"),
    "offi_trade": ("RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade", "오피스텔 매매", "trade"),
    "sh_rent": ("RTMSDataSvcSHRent/getRTMSDataSvcSHRent", "단독·다가구 전월세", "rent"),
}
OK_CODES = {"00", "000"}


def service_key() -> str:
    key = os.getenv("MOLIT_SERVICE_KEY")
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("MOLIT_SERVICE_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise RuntimeError(".env 파일에 MOLIT_SERVICE_KEY=키 를 넣어주세요.")
    return key


def month_range(start: str, end: str) -> list[str]:
    y, m = int(start[:4]), int(start[4:])
    ey, em = int(end[:4]), int(end[4:])
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def parse_page(text: str) -> tuple[int, list[dict]]:
    """XML 응답 → (totalCount, item 목록). 오류 코드면 예외."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise RuntimeError(f"XML이 아닌 응답: {text[:200]}") from error
    code = (root.findtext(".//resultCode") or root.findtext(".//returnReasonCode") or "").strip()
    if code not in OK_CODES:
        msg = root.findtext(".//resultMsg") or root.findtext(".//returnAuthMsg") or text[:200]
        raise RuntimeError(f"API 오류 {code}: {msg.strip()}")
    total = int((root.findtext(".//totalCount") or "0").strip() or 0)
    items = [
        {child.tag: (child.text or "").strip() for child in item}
        for item in root.iter("item")
    ]
    return total, items


def fetch_month(session: requests.Session, path: str, ym: str, key: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        params = {"LAWD_CD": LAWD_CD, "DEAL_YMD": ym, "pageNo": page,
                  "numOfRows": NUM_OF_ROWS, "serviceKey": key}
        for attempt in range(1, 4):
            try:
                response = session.get(BASE_URL + path, params=params, timeout=20)
                response.raise_for_status()
                total, items = parse_page(response.text)
                break
            except (requests.RequestException, RuntimeError) as error:
                if attempt == 3:
                    raise RuntimeError(f"{path} {ym} {page}페이지 실패: {error}") from error
                time.sleep(2 * attempt)
        rows.extend(items)
        # totalCount가 한 페이지를 넘으면 다음 페이지를 받는다.
        if not items or len(rows) >= total:
            return rows
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", default="202511", help="시작 연월 YYYYMM")
    parser.add_argument("--end", default="202610", help="끝 연월 YYYYMM")
    args = parser.parse_args()

    key = service_key()
    months = month_range(args.start, args.end)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    combined: list[dict] = []
    failures = []

    for type_key, (path, label, _kind) in TRADE_TYPES.items():
        for ym in months:
            try:
                rows = fetch_month(session, path, ym, key)
            except RuntimeError as error:
                failures.append(str(error))
                print(f"  ✗ {label} {ym}: {error}")
                continue
            for row in rows:
                row["_type"] = type_key
                row["_ym"] = ym
            (OUT_DIR / f"{type_key}_{ym}.json").write_text(
                json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            combined.extend(rows)
            print(f"  ✓ {label} {ym}: {len(rows):,}건")
            time.sleep(0.2)

    (OUT_DIR / "all.json").write_text(json.dumps(combined, ensure_ascii=False), encoding="utf-8")
    print(f"\n총 {len(combined):,}건 저장 → {OUT_DIR / 'all.json'}")
    if failures:
        print(f"실패 {len(failures)}건 — 다시 실행하면 전체를 새로 받습니다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
