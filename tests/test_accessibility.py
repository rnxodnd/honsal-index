"""거리 산식, 후보 밖 시설 보존, 입력 검증 및 실제 데이터의 JSON 응답 검증."""

import json
import math
from pathlib import Path
import unittest

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Polygon

from src.scoring.accessibility import AccessibilityEngine, AnalysisError


TO_LONLAT = Transformer.from_crs(5179, 4326, always_xy=True)
X0, Y0 = 1_000_000, 2_000_000
WEIGHTS = {"daily_life": 0.3, "healthcare": 0.2, "transport": 0.4, "leisure_community": 0.1}


def point(x=250, y=250):
    return TO_LONLAT.transform(X0 + x, Y0 + y)


def grids():
    lon, lat = point()
    return pd.DataFrame([{
        "grid_id": "G500_1000000_2000000", "x_center": X0 + 250, "y_center": Y0 + 250,
        "lon": lon, "lat": lat, "adm_nm": "테스트 지역",
    }])


def boundary(left=-2000, bottom=-2000, right=2000, top=2000):
    return Polygon([point(x, y) for x, y in ((left, bottom), (right, bottom), (right, top), (left, top))])


def facility(identifier, x, y, subtype="버스정류장", category="transport", **extra):
    lon, lat = point(x, y)
    return {"facility_id": identifier, "name": f"테스트 {identifier}", "lon": lon, "lat": lat,
            "analysis_category": category, "analysis_subtype": subtype, **extra}


def make_engine(rows, city=None):
    return AccessibilityEngine(pd.DataFrame(rows), grids(), boundary() if city is None else city, WEIGHTS)


class AccessibilityTests(unittest.TestCase):
    def test_linear_distance_and_selected_type_average_then_category_weights(self):
        engine = make_engine([
            facility("bus", 400, 250),  # 150m, 80점
            facility("daily", 250, 250, "편의점", "daily_life"),  # 0m, 100점
            facility("health", 700, 250, "약국", "healthcare"),  # 450m, 40점
            facility("billiards", 400, 250, "당구장", "leisure_community"),
            facility("bowling", 700, 250, "볼링장", "leisure_community"),
            facility("pc", 250, 250, "PC방", "leisure_community"),  # 선택하지 않은 유형
        ])
        selected = {"transport": ["버스정류장"], "daily_life": ["편의점"], "healthcare": ["약국"],
                    "leisure_community": ["당구장", "볼링장"]}
        result = engine.analyze(*point(), selected)
        self.assertEqual(result["total_score"], 76.0)
        self.assertEqual({x["key"]: x["score"] for x in result["categories"]}, {
            "daily_life": 100.0, "healthcare": 40.0, "transport": 80.0, "leisure_community": 60.0,
        })
        self.assertEqual({x["facility_id"] for x in result["facilities"]}, {"bus", "daily", "health", "billiards", "bowling"})
        self.assertEqual({x["key"]: x["weight"] for x in result["categories"]}, WEIGHTS)
        leisure_only = engine.analyze(*point(), {"leisure_community": ["당구장", "볼링장", "당구장"]})
        self.assertEqual(leisure_only["total_score"], 60.0)
        self.assertEqual(len(leisure_only["types"]), 2)
        leisure_category = next(x for x in leisure_only["categories"] if x["key"] == "leisure_community")
        self.assertEqual(leisure_category["weight"], 1.0)

    def test_distances_are_from_grid_center_and_not_query_point(self):
        engine = make_engine([facility("bus", 400, 250)])
        center = engine.analyze(*point(), {"transport": ["버스정류장"]})
        on_facility = engine.analyze(*point(400, 250), {"transport": ["버스정류장"]})
        self.assertEqual(center["total_score"], on_facility["total_score"])
        self.assertEqual(on_facility["types"][0]["nearest"]["distance_m"], 150.0)
        self.assertEqual(on_facility["scoring"]["distance_basis"], "grid_center_straight_line")

    def test_neighbor_non_candidate_and_outside_city_facilities_are_kept(self):
        engine = make_engine([
            facility("outside", 750, 250), facility("far", 1250, 250),
        ], boundary(0, 0, 600, 500))
        result = engine.analyze(*point(), {"transport": ["버스정류장"]})
        self.assertEqual([x["facility_id"] for x in result["facilities"]], ["outside"])
        self.assertFalse(result["facilities"][0]["in_city_boundary"])
        self.assertEqual(result["types"][0]["count_3x3"], 1)
        self.assertEqual(result["total_score"], 33.33)
        self.assertEqual(len(result["neighborhood"]["grid_ids"]), 9)

    def test_zero_without_neighbor_is_distinct_from_zero_beyond_radius(self):
        engine = make_engine([
            facility("far", 1250, 250, "멀리있는 유형", "leisure_community"),
            facility("diagonal", 900, 900, "모서리 유형", "leisure_community"),
        ])
        result = engine.analyze(*point(), {"leisure_community": ["멀리있는 유형", "모서리 유형"]})
        types = {row["subtype"]: row for row in result["types"]}
        self.assertEqual(result["total_score"], 0.0)
        self.assertIsNone(types["멀리있는 유형"]["nearest"])
        self.assertEqual(types["멀리있는 유형"]["status"], "no_facility_in_neighborhood")
        self.assertEqual(types["모서리 유형"]["status"], "outside_scoring_radius")
        self.assertEqual(types["모서리 유형"]["count_3x3"], 1)
        self.assertEqual(types["모서리 유형"]["count_within_radius"], 0)

    def test_radius_limit_and_collocated_unique_facilities(self):
        offset = 750 / math.sqrt(2)
        engine = make_engine([
            facility("limit", 250 + offset, 250 + offset),
            facility("colocated_a", 250, 250, "편의점", "daily_life"),
            facility("colocated_b", 250, 250, "편의점", "daily_life"),
        ])
        result = engine.analyze(*point(), {"transport": ["버스정류장"], "daily_life": ["편의점"]})
        types = {row["category"]: row for row in result["types"]}
        self.assertEqual(types["transport"]["nearest"]["distance_m"], 750.0)
        self.assertEqual(types["transport"]["score"], 0.0)
        self.assertEqual(types["transport"]["status"], "outside_scoring_radius")
        self.assertEqual(types["transport"]["count_within_radius"], 1)
        self.assertEqual(types["daily_life"]["score"], 100.0)
        self.assertEqual(types["daily_life"]["count_3x3"], 2)
        self.assertEqual(types["daily_life"]["nearest"]["facility_id"], "colocated_a")
        self.assertAlmostEqual(result["total_score"], 100 * 3 / 7, places=2)

    def test_invalid_coordinates_and_location_names(self):
        engine = make_engine([facility("bus", 250, 250)])
        for lon, lat in ((True, 38), ("127.5", 38), (None, 38), (float("nan"), 38),
                         (float("inf"), 38), (181, 38), (127, 91), ([], 38), (10**400, 38)):
            with self.subTest(lon=lon, lat=lat), self.assertRaises(AnalysisError) as caught:
                engine.analyze(lon, lat, {"transport": ["버스정류장"]})
            self.assertEqual(caught.exception.code, "invalid_coordinates")
        with self.assertRaises(AnalysisError) as caught:
            engine.analyze(*point(), {"transport": ["버스정류장"]}, name={"bad": "name"})
        self.assertEqual(caught.exception.code, "invalid_location_name")

    def test_outside_city_and_unavailable_candidate_grid_are_explicit(self):
        engine = make_engine([facility("bus", 250, 250)])
        for coordinate, expected in ((point(3000, 3000), "outside_city"),
                                     (point(750, 250), "outside_candidate_grid")):
            with self.subTest(expected=expected), self.assertRaises(AnalysisError) as caught:
                engine.analyze(*coordinate, {"transport": ["버스정류장"]})
            self.assertEqual(caught.exception.code, expected)

    def test_empty_unknown_and_malformed_selections_are_not_zero_scores(self):
        engine = make_engine([facility("bus", 250, 250)])
        for selection in ({}, {"transport": []}, {"transport": ["없는 시설"]},
                          {"safety": ["경찰서"]}, {"transport": "버스정류장"}, [], None):
            with self.subTest(selected=selection), self.assertRaises(AnalysisError) as caught:
                engine.analyze(*point(), selection)
            self.assertEqual(caught.exception.code, "invalid_selection")

    def test_missing_coordinates_invalid_data_fail_during_loading(self):
        for lon in (None, float("nan"), "bad", 181):
            row = facility("bus", 250, 250)
            row["lon"] = lon
            with self.subTest(lon=lon), self.assertRaises(ValueError):
                make_engine([row])
        duplicate = facility("same", 250, 250)
        with self.assertRaises(ValueError):
            make_engine([duplicate, duplicate])

    def test_options_and_json_are_native_values_with_null_for_missing_phone(self):
        engine = make_engine([facility("bus", 250, 250, phone=pd.NA, address="")])
        options = engine.options()
        self.assertEqual(options["dataset"], {"facility_count": 1, "grid_count": 1})
        transport = next(row for row in options["categories"] if row["key"] == "transport")
        self.assertEqual(transport["subtypes"], [{"name": "버스정류장", "facility_count": 1}])
        result = engine.analyze(*point(), {"transport": ["버스정류장"]})
        self.assertIsNone(result["facilities"][0]["phone"])
        self.assertIsNone(result["facilities"][0]["address"])
        json.dumps(options, allow_nan=False)
        json.dumps(result, allow_nan=False)


class ProjectDataSmokeTests(unittest.TestCase):
    def test_chuncheon_billiards_and_bowling_use_actual_dataset(self):
        project = Path(__file__).resolve().parents[1]
        engine = AccessibilityEngine.from_project(project)
        options = engine.options()
        self.assertEqual(options["dataset"], {"facility_count": 5252, "grid_count": 2526})
        self.assertEqual(sum(len(row["subtypes"]) for row in options["categories"]), 40)
        result = engine.analyze(127.7298, 37.8813, {"leisure_community": ["당구장", "볼링장"]}, "춘천시청 인근")
        self.assertEqual({row["subtype"] for row in result["types"]}, {"당구장", "볼링장"})
        self.assertTrue(result["facilities"])
        self.assertTrue(all(row["subtype"] in {"당구장", "볼링장"} for row in result["facilities"]))
        self.assertGreaterEqual(result["total_score"], 0)
        self.assertLessEqual(result["total_score"], 100)
        json.dumps(result, ensure_ascii=False, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
