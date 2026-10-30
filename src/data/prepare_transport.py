"""공식 원본에서 춘천 버스 정류장·경춘선 역 위치를 추출합니다.

기본 실행은 로컬 원본을 사용합니다. --download는 검증한 원본을 다시 받습니다.
"""

import argparse
import hashlib
import io
from pathlib import Path
from urllib.request import urlopen

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_DIR / "data" / "raw"
OUTPUT_DIR = PROJECT_DIR / "data" / "processed"
SOURCES = {
    "bus": {
        "filename": "chuncheon_bus_stops_portal_20260326.csv",
        "download_url": "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003616610&fileDetailSn=1",
        "source_url": "https://www.data.go.kr/data/15045129/fileData.do",
        "source": "강원특별자치도 춘천시",
        "sha256": "cfeb76163160820257acb3ed04fa821dfb420416d9137f64db3dddc4ad05ca02",
    },
    "rail": {
        "filename": "gyeongchun_station_locations_20241022.csv",
        "download_url": "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000002647504&fileDetailSn=1",
        "source_url": "https://www.data.go.kr/data/15041483/fileData.do",
        "source": "국가철도공단",
        "sha256": "ccc30ea151a6d70d0447ad64da73e7be179842a323f81b4f5f1921f7c3b5e132",
    },
}
CHUNCHEON_STATIONS = {"굴봉산", "백양리", "강촌", "김유정", "남춘천", "춘천"}
# 코레일 2026-09-01 시행 평일·휴일 ITX청춘 상행/하행 시간표 확인.
# 통과시각이 아닌 도착·출발행 기준이며, 춘천은 기종착역입니다.
ITX_STATIONS = {"강촌", "남춘천", "춘천"}
ITX_SOURCE_URL = "https://www.korail.com/com/userBoard.do?mode=list&schBcid=ticketTable"


def load_source(kind: str, download: bool) -> pd.DataFrame:
    source = SOURCES[kind]
    path = RAW_DIR / source["filename"]
    if not path.exists():
        if not download:
            raise FileNotFoundError(f"원본이 없습니다: {path}\n--download 옵션으로 받으세요.")
        with urlopen(source["download_url"], timeout=40) as response:
            content = response.read()
        # 오류 HTML 또는 다른 버전의 자료를 원본으로 저장하지 않습니다.
        if hashlib.sha256(content).hexdigest() != source["sha256"]:
            raise ValueError(f"다운로드 내용이 검증한 원본과 다릅니다: {source['filename']}")
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != source["sha256"]:
        raise ValueError(f"원본이 변경되었습니다. 출처와 기준일을 다시 확인하세요: {path}")
    return pd.read_csv(io.BytesIO(content), encoding="cp949", dtype="string").apply(
        lambda column: column.str.strip()
    )


def add_metadata(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["city"] = "춘천시"
    frame["source"] = SOURCES[kind]["source"]
    frame["source_file"] = SOURCES[kind]["filename"]
    frame["source_url"] = SOURCES[kind]["source_url"]

    for column in ["lon", "lat"]:
        original = frame[column]
        numeric = pd.to_numeric(original, errors="coerce")
        if (original.notna() & original.ne("") & numeric.isna()).any():
            raise ValueError(f"숫자로 해석할 수 없는 {column} 값이 있습니다: {kind}")
        frame[column] = numeric
    # 결측을 0으로 바꾸지 않습니다. 좌표 존재 여부와 행정경계 검증은 다릅니다.
    frame["has_coordinates"] = frame["lon"].notna() & frame["lat"].notna()
    complete = frame.loc[frame["has_coordinates"]]
    if not (complete["lon"].between(-180, 180) & complete["lat"].between(-90, 90)).all():
        raise ValueError(f"위경도 범위를 벗어난 값이 있습니다: {kind}")
    if frame.empty or frame["name"].isna().any() or frame["name"].eq("").any():
        raise ValueError(f"자료 또는 시설명이 비어 있습니다: {kind}")
    if frame["facility_id"].isna().any() or frame["facility_id"].duplicated().any():
        raise ValueError(f"시설 식별자가 없거나 중복됩니다: {kind}")
    return frame.sort_values("facility_id").reset_index(drop=True)


def prepare_bus(download: bool = False) -> pd.DataFrame:
    source = load_source("bus", download)
    frame = source.rename(columns={
        "관리번호": "source_facility_id", "정류장 번호": "stop_no",
        "정류장명": "name", "위도": "lat", "경도": "lon",
        "데이터기준일": "data_date",
    })[["source_facility_id", "stop_no", "name", "lat", "lon", "data_date"]].copy()
    if frame["source_facility_id"].isna().any() or frame["source_facility_id"].eq("").any():
        raise ValueError("정류장 관리번호가 비어 있습니다.")
    # 같은 이름의 맞은편 승강장을 각각 보존합니다.
    frame["facility_id"] = "chuncheon:bus:" + frame["source_facility_id"]
    frame["category"] = "bus_stop"
    frame["facility_type"] = "버스정류장"
    frame["source_name"] = frame["name"]
    frame["line"] = pd.NA  # 위치 원본에는 노선 정보가 없습니다.
    frame["operator"] = pd.NA
    frame["has_itx"] = pd.NA  # 버스 정류장에는 해당하지 않습니다.
    frame["itx_schedule_effective_date"] = pd.NA
    frame["itx_source_url"] = pd.NA
    return add_metadata(frame, "bus")


def prepare_rail(download: bool = False) -> pd.DataFrame:
    source = load_source("rail", download)
    source["name"] = source["역명"].str.replace(r"\([^)]*\)", "", regex=True).str.strip()
    frame = source.loc[source["name"].isin(CHUNCHEON_STATIONS)].rename(columns={
        "역명": "source_name", "선명": "line", "철도운영기관명": "operator",
        "위도": "lat", "경도": "lon",
    })[["name", "source_name", "line", "operator", "lat", "lon"]].copy()
    if set(frame["name"]) != CHUNCHEON_STATIONS or len(frame) != 6:
        raise ValueError("춘천 경춘선 6개 역이 정확히 한 번씩 포함되어야 합니다.")
    # 원본에는 역 ID가 없으므로 프로젝트 내부 식별자를 부여합니다.
    frame["facility_id"] = "chuncheon:rail:" + frame["name"]
    frame["source_facility_id"] = pd.NA
    frame["stop_no"] = pd.NA
    frame["category"] = "rail_station"
    frame["facility_type"] = "철도역"
    frame["data_date"] = "2024-10-22"  # 원본 목록의 기준일. 다운로드일이 아닙니다.
    frame["has_itx"] = frame["name"].isin(ITX_STATIONS)
    frame["itx_schedule_effective_date"] = "2026-09-01"
    frame["itx_source_url"] = ITX_SOURCE_URL
    return add_metadata(frame, "rail")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="없는 원본을 공식 공개 URL에서 다운로드")
    args = parser.parse_args()
    bus = prepare_bus(args.download)
    rail = prepare_rail(args.download)
    combined = pd.concat([bus, rail], ignore_index=True)
    if combined["facility_id"].duplicated().any():
        raise ValueError("통합 데이터의 시설 식별자가 중복됩니다.")
    columns = [
        "facility_id", "name", "category", "facility_type", "city", "lat", "lon",
        "has_coordinates", "source_facility_id", "stop_no", "source_name", "line",
        "operator", "data_date", "source", "source_file", "source_url",
        "has_itx", "itx_schedule_effective_date", "itx_source_url",
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, frame in {
        "chuncheon_bus_stops.csv": bus,
        "chuncheon_rail_stations.csv": rail,
        "chuncheon_transport_facilities.csv": combined,
    }.items():
        frame[columns].to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {filename} — {len(frame):,}개")
    print(f"좌표 누락: {(~combined['has_coordinates']).sum():,}개")
    print("같은 시설의 중복 집계를 막으려면 통합 파일 하나만 사용하세요.")
    print("ITX 정차 여부는 코레일 2026-09-01 시행 시간표 기준이며 좌표 기준일과 다릅니다.")


if __name__ == "__main__":
    main()
