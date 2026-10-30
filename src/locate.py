"""주소 → 격자 → 3×3 생활권 격자 찾기

카카오 로컬 API로 주소(또는 장소명)를 좌표로 바꾸고,
그 좌표가 속한 500m 격자와 주변 8개 격자(3×3, 1.5km × 1.5km)를 돌려준다.

준비:
    프로젝트 폴더에 .env 파일을 만들고 한 줄 추가 (GitHub에 올라가지 않음)
        KAKAO_REST_KEY=카카오_REST_API_키

사용법 (터미널 테스트):
    python src/locate.py "강원특별자치도 춘천시 강원대학길 1"

다른 코드에서:
    from src.locate import locate
    info = locate("춘천시청")
    info["grid_id"]      # 가운데 격자
    info["grid_3x3"]     # 9개 격자 ID 리스트
"""
import os
import sys
from pathlib import Path

import requests
from pyproj import Transformer

GRID_SIZE = 500
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/{}.json"
_TO_M = Transformer.from_crs(4326, 5179, always_xy=True)   # 위경도 → 미터 좌표(EPSG:5179)


def _kakao_key() -> str:
    key = os.getenv("KAKAO_REST_KEY")
    if not key:
        env = Path(__file__).resolve().parents[1] / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("KAKAO_REST_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise RuntimeError(".env 파일에 KAKAO_REST_KEY=키 를 넣어주세요.")
    return key


def address_to_lonlat(query: str) -> tuple[float, float, str]:
    """주소 검색 → 없으면 장소(키워드) 검색. (경도, 위도, 찾은 이름) 반환."""
    headers = {"Authorization": f"KakaoAK {_kakao_key()}"}
    for kind, name_key in (("address", "address_name"), ("keyword", "place_name")):
        r = requests.get(KAKAO_URL.format(kind), headers=headers, params={"query": query}, timeout=5)
        if r.status_code != 200:
            raise RuntimeError(f"카카오 API 오류 {r.status_code}: {r.text}")
        docs = r.json().get("documents", [])
        if docs:
            d = docs[0]
            return float(d["x"]), float(d["y"]), d.get(name_key, query)
    raise ValueError(f"'{query}' 위치를 찾지 못했어요.")


def grid_id_from_lonlat(lon: float, lat: float, size: int = GRID_SIZE) -> str:
    """위경도가 속한 격자 ID (G500_x0_y0)."""
    x, y = _TO_M.transform(lon, lat)
    return f"G{size}_{int(x // size) * size}_{int(y // size) * size}"


def neighbors_3x3(grid_id: str) -> list[str]:
    """가운데 격자 + 주변 8개 격자 ID (왼쪽 아래부터 오른쪽 위 순서)."""
    prefix, x0, y0 = grid_id.split("_")
    size, x0, y0 = int(prefix[1:]), int(x0), int(y0)
    return [f"G{size}_{x0 + dx * size}_{y0 + dy * size}"
            for dy in (-1, 0, 1) for dx in (-1, 0, 1)]


def locate(query: str) -> dict:
    """주소 → {찾은 이름, 경도, 위도, 가운데 격자, 3×3 격자 9개}."""
    lon, lat, name = address_to_lonlat(query)
    gid = grid_id_from_lonlat(lon, lat)
    return {"query": query, "found": name, "lon": lon, "lat": lat,
            "grid_id": gid, "grid_3x3": neighbors_3x3(gid)}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "춘천시청"
    info = locate(q)
    print(f"검색어: {info['query']} → {info['found']} ({info['lat']:.6f}, {info['lon']:.6f})")
    print(f"가운데 격자: {info['grid_id']}")
    print("3×3 격자:")
    g = info["grid_3x3"]
    for row in (g[6:9], g[3:6], g[0:3]):   # 위쪽 줄부터 출력
        print("   " + "  ".join(row))
