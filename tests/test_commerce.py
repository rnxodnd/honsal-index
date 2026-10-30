"""상권 분류의 지역·업종 경계와 결측값 처리를 검증합니다."""

import unittest

import pandas as pd

from src.data.prepare_commerce import classify_commerce


def shop(identifier="test:1", code="R10202", subtype="독서실/스터디 카페", **changes):
    # 검증 전용 가상 업소이며 실제 산출물에 포함하지 않습니다.
    return {
        "상가업소번호": identifier, "상호명": "테스트 업소",
        "상권업종소분류코드": code, "상권업종소분류명": subtype,
        "시도코드": "51", "시군구코드": "51110", "시군구명": "춘천시",
        "경도": "127.72", "위도": "37.88", "도로명주소": "춘천시 테스트 도로",
        "지번주소": "춘천시 테스트 지번", **changes,
    }


class CommerceTests(unittest.TestCase):
    def test_exact_codes_select_chuncheon_and_preserve_source_name(self):
        source = pd.DataFrame([
            shop(), shop("other-city", 시군구명="원주시", 시군구코드="51130"),
            shop("not-selected", "R10499", "기타 오락관련 서비스업", 상호명="테스트 볼링장"),
        ])
        result = classify_commerce(source)
        self.assertEqual(result["상가업소번호"].tolist(), ["test:1"])
        self.assertEqual(result.analysis_subtype.tolist(), ["독서실/스터디카페"])
        self.assertEqual(result["업종소분류명"].tolist(), ["독서실/스터디 카페"])
        self.assertEqual(result.source_business_code.tolist(), ["R10202"])

    def test_phone_stays_unknown_and_land_address_is_fallback(self):
        result = classify_commerce(pd.DataFrame([shop(도로명주소=" ")]))
        self.assertTrue(result["전화번호"].isna().all())
        self.assertEqual(result.phone_status.tolist(), ["not_provided"])
        self.assertEqual(result["주소"].tolist(), ["춘천시 테스트 지번"])

    def test_colocated_shops_remain_distinct_but_duplicate_ids_fail(self):
        rows = [shop(), shop("test:2")]
        result = classify_commerce(pd.DataFrame(rows))
        self.assertEqual(len(result), 2)
        with self.assertRaisesRegex(ValueError, "중복"):
            classify_commerce(pd.DataFrame([rows[0], rows[0]]))

    def test_changed_codes_invalid_coordinates_and_wrong_city_code_fail(self):
        for broken in (
            shop(code="CHANGED"), shop(경도="181"), shop(위도="잘못된 좌표"), shop(시군구코드="51130"),
        ):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                classify_commerce(pd.DataFrame([broken]))


if __name__ == "__main__":
    unittest.main()
