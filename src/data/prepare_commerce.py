"""2026년 9월 강원 상권 자료에서 춘천 편의시설·여가시설을 추출합니다.

업종은 승인한 소분류 코드·명칭으로 분류합니다. 상호명이나 좌표로 중복 제거하지 않습니다.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_PATH = PROJECT_DIR / "data/raw/gangwon_commerce_202609.csv"
OUTPUT_DIR = PROJECT_DIR / "data/processed"
RULE_PATH = PROJECT_DIR / "config/commerce_categories.json"
SOURCE_FILE = "소상공인시장진흥공단_상가(상권)정보_강원_202609.csv"
SOURCE_SHA256 = "48ec49f65e254b6abd4f069b7977b99afe2c9a2081bfb7486ddee9ad444efd22"
SOURCE_CANONICAL_SHA256 = "2a2413200eee20dcdd54875353443349187d130166a48aed0fd65e47c1f516ce"
EXPORT_COLUMNS = ["상가업소번호", "상호명", "업종", "업종소분류명", "경도", "위도", "전화번호", "주소"]
CATEGORY_LABELS = {"daily_life": "편의시설", "leisure_community": "여가시설"}


def default_source_path() -> Path:
    """개인 원본이 있으면 사용하고, 없으면 Git에 공유된 동일 자료를 사용합니다."""
    return RAW_PATH if RAW_PATH.is_file() else PROJECT_DIR / SOURCE_FILE


def load_source(path: Path) -> tuple[pd.DataFrame, str]:
    """Git 줄바꿈 변환만 허용하고 검증한 바이트에서 CSV와 실제 해시를 읽습니다."""
    content = path.read_bytes()
    canonical = content.replace(b"\r\n", b"\n")
    if hashlib.sha256(canonical).hexdigest() != SOURCE_CANONICAL_SHA256:
        raise ValueError("검증한 202609 원본과 내용이 다릅니다. 기준월과 업종 분류표를 확인하세요.")
    digest = hashlib.sha256(content).hexdigest()
    return pd.read_csv(io.BytesIO(content), encoding="utf-8-sig", dtype="string"), digest


def load_rules(path: Path = RULE_PATH) -> pd.DataFrame:
    rules = pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))
    columns = ["code", "source_name", "category", "subtype"]
    if not set(columns).issubset(rules.columns) or rules.empty:
        raise ValueError("상권 업종 분류표를 확인하세요.")
    if rules[columns].isna().any().any() or rules[columns].eq("").any().any():
        raise ValueError("상권 업종 분류표에 빈 값이 있습니다.")
    if rules.code.duplicated().any() or rules.source_name.duplicated().any():
        raise ValueError("상권 업종 분류표의 코드 또는 이름이 중복됩니다.")
    if not rules.category.isin(CATEGORY_LABELS).all():
        raise ValueError("상권 자료는 편의시설·여가시설만 분류합니다.")
    return rules


def classify_commerce(
    source: pd.DataFrame, rules: pd.DataFrame | None = None, *, source_sha256: str = SOURCE_SHA256,
) -> pd.DataFrame:
    rules = load_rules() if rules is None else rules
    required = [
        "상가업소번호", "상호명", "상권업종소분류코드", "상권업종소분류명",
        "시도코드", "시군구코드", "시군구명", "경도", "위도", "도로명주소", "지번주소",
    ]
    missing = set(required) - set(source.columns)
    if missing:
        raise ValueError(f"필수 원본 컬럼 누락: {sorted(missing)}")
    frame = source.copy().astype("string").apply(lambda col: col.str.strip()).replace("", pd.NA)
    city = frame.loc[frame["시군구명"].eq("춘천시")].copy()
    if city.empty or not (city["시도코드"].eq("51") & city["시군구코드"].eq("51110")).fillna(False).all():
        raise ValueError("춘천시 행 또는 행정구역 코드를 확인하세요.")
    # 이름만 맞거나 코드만 맞는 경우에는 바뀐 분류표를 검토하게 합니다.
    wanted = city.loc[
        city["상권업종소분류코드"].isin(rules.code) | city["상권업종소분류명"].isin(rules.source_name)
    ].copy()
    chosen = wanted.merge(
        rules, left_on=["상권업종소분류코드", "상권업종소분류명"],
        right_on=["code", "source_name"], how="left", validate="many_to_one", indicator=True,
    )
    if not chosen["_merge"].eq("both").all():
        raise ValueError("원본의 업종 코드·명칭이 분류표와 다릅니다. 분류표를 확인하세요.")
    if chosen.empty:
        raise ValueError("지정한 춘천 업종이 없습니다. 기존 결과는 덮어쓰지 않습니다.")
    for column in ("상가업소번호", "상호명"):
        if chosen[column].isna().any():
            raise ValueError(f"필수 값 누락: {column}")
    if chosen["상가업소번호"].duplicated().any():
        raise ValueError("상가업소번호가 중복됩니다. 임의로 삭제하지 않습니다.")

    result = chosen[["상가업소번호", "상호명"]].copy()
    result["업종"] = chosen["category"].map(CATEGORY_LABELS)
    result["업종소분류명"] = chosen["상권업종소분류명"]
    for column, bounds in (("경도", (-180, 180)), ("위도", (-90, 90))):
        numeric = pd.to_numeric(chosen[column], errors="coerce")
        invalid = chosen[column].notna() & (numeric.isna() | ~numeric.between(*bounds))
        if invalid.any():
            raise ValueError(f"숫자가 아니거나 범위를 벗어난 좌표: {column}")
        result[column] = numeric
    # 202609 원본에는 전화번호 컬럼 자체가 없습니다. 추정하거나 0으로 채우지 않습니다.
    result["전화번호"] = chosen["전화번호"] if "전화번호" in chosen else pd.NA
    result["주소"] = chosen["도로명주소"].fillna(chosen["지번주소"])
    if result["주소"].isna().any():
        raise ValueError("도로명주소와 지번주소가 모두 없는 시설이 있습니다.")

    result["facility_id"] = "chuncheon:commerce:" + result["상가업소번호"]
    result["source_facility_id"] = result["상가업소번호"]
    result["name"] = result["상호명"]
    result["category"] = "commerce"
    result["facility_type"] = result["업종소분류명"]
    result["analysis_category"] = chosen["category"]
    result["analysis_subtype"] = chosen["subtype"]
    result["city"] = "춘천시"
    result["lon"] = result["경도"]
    result["lat"] = result["위도"]
    result["has_coordinates"] = result.lon.notna() & result.lat.notna()
    result["phone"] = result["전화번호"]
    result["phone_status"] = result.phone.notna().map({True: "provided", False: "not_provided"})
    result["address"] = result["주소"]
    result["source_business_code"] = chosen["상권업종소분류코드"]
    result["source_business_name"] = chosen["상권업종소분류명"]
    result["source"] = "소상공인시장진흥공단"
    result["source_file"] = SOURCE_FILE
    result["source_url"] = "https://www.data.go.kr/data/15083033/fileData.do"
    result["data_date"] = "2026-09"  # 제공된 파일명의 기준월. 특정 날짜로 추정하지 않습니다.
    result["data_date_precision"] = "month"
    result["source_sha256"] = source_sha256
    return result.sort_values(["analysis_category", "analysis_subtype", "facility_id"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=default_source_path(),
                        help="202609 강원 원본 CSV (생략 시 개인 원본, 없으면 저장소 루트의 공유 원본)")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"원본이 없습니다: {args.input}\n--input '원본 경로'를 지정하세요.")
    try:
        source, digest = load_source(args.input)
    except ValueError as error:
        parser.error(str(error))
    result = classify_commerce(source, source_sha256=digest)
    outputs = {
        "chuncheon_daily_life.csv": result.loc[result.analysis_category.eq("daily_life"), EXPORT_COLUMNS],
        "chuncheon_leisure.csv": result.loc[result.analysis_category.eq("leisure_community"), EXPORT_COLUMNS],
        "chuncheon_commerce_facilities.csv": result,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        frame.to_csv(args.output_dir / name, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {name} — {len(frame):,}개")
    print(result.groupby(["업종", "업종소분류명"]).size().to_string())
    print(f"전화번호 미제공: {result.phone.isna().sum():,}개; 좌표 누락: {(~result.has_coordinates).sum():,}개")


if __name__ == "__main__":
    main()
