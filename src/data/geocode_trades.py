"""실거래 데이터에 좌표·격자 ID 부여 → app/data/trades.json

fetch_trades.py 결과(data/raw/trades/all.json)를 읽어
"춘천시 법정동 지번"을 카카오 로컬 API로 좌표로 바꾸고 500m 격자 ID를 붙인다.
지번이 없는 거래(주로 단독·다가구)와 좌표를 못 찾은 거래는 법정동 단위로 따로 모은다.
같은 주소는 data/raw/trades/geocode_cache.json 에 저장해 다시 호출하지 않는다.

사용법 (프로젝트 폴더에서):
    python src/data/geocode_trades.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "data"))
from fetch_trades import TRADE_TYPES  # noqa: E402

RAW = ROOT / "data" / "raw" / "trades" / "all.json"
CACHE = ROOT / "data" / "raw" / "trades" / "geocode_cache.json"
OUT = ROOT / "app" / "data" / "trades.json"
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/{}.json"
GRID_SIZE = 500
# app/js/grid.js 와 같은 EPSG:5179 정의
_TO_M = Transformer.from_crs(
    "EPSG:4326",
    "+proj=tmerc +lat_0=38 +lon_0=127.5 +k=0.9996 +x_0=1000000 +y_0=2000000 "
    "+ellps=GRS80 +units=m +no_defs",
    always_xy=True,
)
# 춘천 주변을 벗어난 검색 결과는 버린다 (대략적 범위)
LAT_RANGE = (37.6, 38.2)
LON_RANGE = (127.4, 128.1)


def kakao_key() -> str:
    key = os.getenv("KAKAO_REST_KEY")
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("KAKAO_REST_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise RuntimeError(".env 파일에 KAKAO_REST_KEY=키 를 넣어주세요.")
    return key


def to_int(value: str | None) -> int | None:
    text = (value or "").replace(",", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return None


def to_float(value: str | None) -> float | None:
    text = (value or "").replace(",", "").strip()
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def in_chuncheon(lon: float, lat: float) -> bool:
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def grid_id(lon: float, lat: float) -> str:
    x, y = _TO_M.transform(lon, lat)
    return f"G500_{int(x // GRID_SIZE) * GRID_SIZE}_{int(y // GRID_SIZE) * GRID_SIZE}"


class Geocoder:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"KakaoAK {kakao_key()}"
        self.cache: dict[str, list[float] | None] = (
            json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {})
        self.calls = 0

    def _search(self, kind: str, query: str) -> list[float] | None:
        for attempt in range(1, 4):
            try:
                r = self.session.get(KAKAO_URL.format(kind), params={"query": query}, timeout=8)
                self.calls += 1
                if r.status_code == 429:
                    time.sleep(2 * attempt)
                    continue
                r.raise_for_status()
                for doc in r.json().get("documents", []):
                    lon, lat = float(doc["x"]), float(doc["y"])
                    if in_chuncheon(lon, lat):
                        return [lon, lat]
                return None
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(attempt)
        return None

    def lookup(self, dong: str, jibun: str, name: str) -> list[float] | None:
        cache_key = f"{dong}|{jibun}|{name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        point = self._search("address", f"강원특별자치도 춘천시 {dong} {jibun}")
        if point is None and name:
            point = self._search("keyword", f"춘천 {dong} {name}")
        self.cache[cache_key] = point
        if self.calls % 100 == 0:
            self.save()
        return point

    def save(self) -> None:
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")


def normalize(row: dict) -> dict | None:
    """원본 한 건 → 화면에 필요한 값만. 해제된 매매는 제외."""
    kind = TRADE_TYPES[row["_type"]][2]
    if kind == "trade" and (row.get("cdealType") or "").strip():
        return None  # 계약 해제 거래
    y, m, d = to_int(row.get("dealYear")), to_int(row.get("dealMonth")), to_int(row.get("dealDay"))
    if not (y and m and d):
        return None
    deal = {
        "type": row["_type"],
        "date": f"{y}-{m:02d}-{d:02d}",
        "dong": (row.get("umdNm") or "").strip(),
        "jibun": (row.get("jibun") or "").strip(),
        "name": (row.get("aptNm") or row.get("offiNm") or row.get("mhouseNm") or "").strip(),
        "area": to_float(row.get("excluUseAr") or row.get("totalFloorAr")),
    }
    if kind == "trade":
        deal["price"] = to_int(row.get("dealAmount"))
        if deal["price"] is None:
            return None
    else:
        deal["deposit"] = to_int(row.get("deposit"))
        deal["monthly"] = to_int(row.get("monthlyRent")) or 0
        if deal["deposit"] is None:
            return None
    return deal


def compact(deal: dict) -> list:
    """JSON 크기를 줄이기 위한 배열 형태. 순서는 meta.fields 참고."""
    if TRADE_TYPES[deal["type"]][2] == "trade":
        return [deal["date"], deal["price"], None, deal["area"], deal["name"]]
    return [deal["date"], deal["deposit"], deal["monthly"], deal["area"], deal["name"]]


def main() -> int:
    if not RAW.exists():
        print(f"{RAW} 이 없습니다. 먼저 python src/data/fetch_trades.py 를 실행하세요.")
        return 1
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    deals = [d for d in (normalize(r) for r in raw) if d]
    print(f"원본 {len(raw):,}건 → 사용 {len(deals):,}건 (해제·값 누락 제외)")

    geocoder = Geocoder()
    grids: dict[str, dict[str, list]] = {}
    dongs: dict[str, dict[str, list]] = {}
    stats = {"grid": 0, "dong": 0}
    for i, deal in enumerate(deals, 1):
        point = None
        if deal["jibun"]:
            point = geocoder.lookup(deal["dong"], deal["jibun"], deal["name"])
        if point:
            bucket = grids.setdefault(grid_id(*point), {})
            stats["grid"] += 1
        else:
            bucket = dongs.setdefault(deal["dong"] or "미상", {})
            stats["dong"] += 1
        bucket.setdefault(deal["type"], []).append(compact(deal))
        if i % 500 == 0:
            print(f"  {i:,}/{len(deals):,} 처리 (카카오 호출 {geocoder.calls:,}회)")
    geocoder.save()

    for bucket in list(grids.values()) + list(dongs.values()):
        for rows in bucket.values():
            rows.sort(key=lambda r: r[0], reverse=True)  # 최신 거래가 앞

    months = sorted({d["date"][:7] for d in deals})
    payload = {
        "meta": {
            "source": "국토교통부 실거래가 공개시스템 API (공공데이터포털)",
            "region": "강원특별자치도 춘천시 (LAWD_CD 51110)",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "months": months,
            "latest_month": months[-1] if months else None,
            "recent_months": months[-3:],
            "unit": "만원",
            "fields": ["date", "deposit_or_price", "monthly_rent", "area_m2", "name"],
            "types": {k: {"label": v[1], "kind": v[2]} for k, v in TRADE_TYPES.items()},
            "counts": stats,
        },
        "grids": grids,
        "dongs": dongs,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"\n격자 배정 {stats['grid']:,}건 · 법정동 단위 {stats['dong']:,}건")
    print(f"저장 → {OUT} ({size_kb:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
