import unittest
import tempfile
from pathlib import Path

import pandas as pd

from src.data.classify_facilities import build_classified, classify_existing, combine_classified, make_catalog, make_status


def example(facility_id, category, facility_type):
    # 검증 전용 가상 시설이며 실제 사업장 데이터가 아닙니다.
    return {
        "facility_id": facility_id, "name": "테스트 시설", "category": category,
        "facility_type": facility_type, "city": "춘천시", "lat": "37.88", "lon": "127.72",
        "source": "테스트", "source_file": "fixture.csv", "source_url": "https://example.org/data",
        "data_date": "2026-10-30",
    }


class ClassificationTests(unittest.TestCase):
    def test_source_types_are_preserved_and_rail_is_not_duplicated(self):
        source = pd.DataFrame([
            example("hospital:1", "medical", "치과의원"),
            example("pharmacy:1", "pharmacy", "약국"),
            {**example("station:1", "rail_station", "철도역"), "has_itx": "True"},
        ])
        result = combine_classified([classify_existing(source)])
        self.assertEqual(len(result), 3)
        self.assertEqual(set(result.analysis_subtype), {"치과의원", "약국", "철도역"})
        self.assertEqual(result.loc[result.facility_id.eq("station:1"), "has_itx"].tolist(), [True])
        expected = source.set_index("facility_id")
        actual = result.set_index("facility_id")
        for field in ("name", "category", "facility_type", "source", "data_date"):
            self.assertEqual(expected[field].to_dict(), actual[field].to_dict())

    def test_pending_categories_are_not_recorded_as_zero(self):
        result = combine_classified([classify_existing(pd.DataFrame([example("a", "pharmacy", "약국")]))])
        status = make_status(result).set_index("analysis_category")
        self.assertEqual(status.loc["healthcare", "facility_count"], 1)
        for category in ("daily_life", "leisure_community"):
            self.assertEqual(status.loc[category, "status"], "awaiting_data")
            self.assertTrue(pd.isna(status.loc[category, "facility_count"]))

    def test_same_named_different_stops_remain_distinct(self):
        frame = classify_existing(pd.DataFrame([
            example("stop:1", "bus_stop", "버스정류장"), example("stop:2", "bus_stop", "버스정류장"),
        ]))
        result = combine_classified([frame])
        self.assertEqual(len(result), 2)
        self.assertEqual(make_catalog(result).iloc[0].facility_count, 2)
        with self.assertRaises(ValueError):
            combine_classified([frame, frame])

    def test_unknown_types_and_bad_coordinates_are_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            classify_existing(pd.DataFrame([example("x", "medical", "미확인종류")]))
        frame = classify_existing(pd.DataFrame([example("x", "medical", "의원")]))
        for invalid in ("잘못된좌표", "181"):
            broken = frame.copy()
            broken["lon"] = invalid
            with self.assertRaises(ValueError):
                combine_classified([broken])
        missing = frame.copy()
        missing["lon"] = None
        self.assertFalse(combine_classified([missing]).iloc[0].has_coordinates)

    def test_preclassified_commerce_keeps_source_code_and_requires_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pd.DataFrame([example("medical:1", "medical", "의원")]).to_csv(
                root / "chuncheon_medical_facilities.csv", index=False, encoding="utf-8-sig")
            pd.DataFrame([example("bus:1", "bus_stop", "버스정류장")]).to_csv(
                root / "chuncheon_transport_facilities.csv", index=False, encoding="utf-8-sig")
            shop = pd.DataFrame([{
                **example("shop:1", "test_business", "볼링장"),
                "analysis_category": "leisure_community", "analysis_subtype": "볼링장",
                "source_business_code": "TEST_BOWLING", "source_business_name": "테스트용 업종",
            }])
            path = root / "commerce.csv"
            shop.to_csv(path, index=False, encoding="utf-8-sig")
            result = build_classified(root, path)
            self.assertEqual(len(result), 3)
            self.assertEqual(result.loc[result.facility_id.eq("shop:1"), "source_business_code"].iloc[0], "TEST_BOWLING")
            shop.to_csv(root / "chuncheon_commerce_facilities.csv", index=False, encoding="utf-8-sig")
            pd.testing.assert_frame_equal(
                result.drop(columns="input_dataset"), build_classified(root).drop(columns="input_dataset")
            )
            shop["source_business_code"] = ""
            shop.to_csv(path, index=False, encoding="utf-8-sig")
            with self.assertRaises(ValueError):
                build_classified(root, path)


if __name__ == "__main__":
    unittest.main()
