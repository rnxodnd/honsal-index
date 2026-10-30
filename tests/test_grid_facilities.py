"""후보 밖 시설 보존과 3×3 공간 집계의 의미를 검증합니다."""

import unittest

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Polygon

from src.data.assign_facilities_to_grid import (
    assign_facilities, count_facilities, count_neighbors, validate_grids,
)


TO_LONLAT = Transformer.from_crs(5179, 4326, always_xy=True)
ORIGIN_X, ORIGIN_Y = 1_000_000, 2_000_000


def candidate_grid():
    lon, lat = TO_LONLAT.transform(ORIGIN_X + 250, ORIGIN_Y + 250)
    return pd.DataFrame([{
        "grid_id": "G500_1000000_2000000", "x_center": str(ORIGIN_X + 250),
        "y_center": str(ORIGIN_Y + 250), "lon": str(round(lon, 6)), "lat": str(round(lat, 6)),
    }], dtype="string")


def facility(identifier, x, y, subtype="의원", category="healthcare"):
    # 검증 전용 가상 시설입니다. 실제 결과 CSV에는 포함하지 않습니다.
    lon, lat = TO_LONLAT.transform(ORIGIN_X + x, ORIGIN_Y + y)
    return {
        "facility_id": identifier, "name": "테스트 시설",
        "analysis_category": category, "analysis_subtype": subtype,
        "lon": str(lon), "lat": str(lat),
    }


class GridFacilityTests(unittest.TestCase):
    def test_adjacent_non_candidate_facilities_contribute_and_far_type_is_zero(self):
        facilities = pd.DataFrame([
            facility("center", 250, 250),
            facility("east", 750, 250),
            facility("diagonal", -250, -250, "당구장", "leisure_community"),
            facility("far", 1250, 250, "볼링장", "leisure_community"),
        ], dtype="string")
        original = facilities.copy(deep=True)
        assigned = assign_facilities(facilities, candidate_grid())
        self.assertEqual(len(assigned), 4)
        self.assertEqual(assigned.in_candidate_grid.tolist(), [True, False, False, False])
        counts = count_facilities(assigned)
        self.assertEqual(counts.facility_count.sum(), 4)
        nearby = count_neighbors(counts, candidate_grid()).set_index("analysis_subtype")
        self.assertEqual(nearby.facility_count.to_dict(), {"의원": 2, "당구장": 1, "볼링장": 0})
        pd.testing.assert_frame_equal(facilities, original)

    def test_colocated_distinct_ids_are_preserved_but_duplicate_ids_fail(self):
        facilities = pd.DataFrame([
            facility("one", 250, 250), facility("two", 250, 250),
        ], dtype="string")
        assigned = assign_facilities(facilities, candidate_grid())
        counts = count_facilities(assigned)
        self.assertEqual(len(counts), 1)
        self.assertEqual(counts.iloc[0].facility_count, 2)
        self.assertEqual(count_neighbors(counts, candidate_grid()).iloc[0].facility_count, 2)
        with self.assertRaisesRegex(ValueError, "중복"):
            assign_facilities(pd.concat([facilities, facilities.iloc[[0]]]), candidate_grid())
        with self.assertRaisesRegex(ValueError, "중복"):
            count_facilities(pd.concat([assigned, assigned.iloc[[0]]]))

    def test_missing_or_invalid_coordinates_are_not_silently_counted_as_zero(self):
        source = pd.DataFrame([facility("one", 250, 250)], dtype="string")
        for value in (None, "", "잘못된 값", "181", "inf"):
            with self.subTest(lon=value):
                broken = source.copy()
                broken["lon"] = value
                with self.assertRaises(ValueError):
                    assign_facilities(broken, candidate_grid())

    def test_grid_origin_center_projection_and_uniqueness_are_checked(self):
        for column, value in (
            ("grid_id", "G1000_1000000_2000000"),
            ("grid_id", "G500_1000100_2000000"),
            ("x_center", "1000300"),
            ("lon", "127"),
        ):
            with self.subTest(column=column, value=value):
                broken = candidate_grid()
                broken[column] = value
                with self.assertRaises(ValueError):
                    validate_grids(broken)
        with self.assertRaisesRegex(ValueError, "중복"):
            validate_grids(pd.concat([candidate_grid(), candidate_grid()]))

    def test_administrative_boundary_flag_is_independent_of_candidate_flag(self):
        facilities = pd.DataFrame([
            facility("inside", 100, 250), facility("outside", 400, 250),
        ], dtype="string")
        boundary = Polygon([
            TO_LONLAT.transform(ORIGIN_X + x, ORIGIN_Y + y)
            for x, y in ((0, 0), (300, 0), (300, 500), (0, 500))
        ])
        assigned = assign_facilities(facilities, candidate_grid(), boundary)
        self.assertEqual(assigned.in_candidate_grid.tolist(), [True, True])
        self.assertEqual(assigned.in_city_boundary.tolist(), [True, False])
        self.assertTrue(assign_facilities(facilities, candidate_grid()).in_city_boundary.isna().all())

    def test_duplicate_or_invalid_aggregate_counts_fail_before_neighbor_sum(self):
        assigned = assign_facilities(
            pd.DataFrame([facility("one", 250, 250)], dtype="string"), candidate_grid(),
        )
        counts = count_facilities(assigned)
        with self.assertRaisesRegex(ValueError, "중복"):
            count_neighbors(pd.concat([counts, counts]), candidate_grid())
        for value in (-1, 0.5, None):
            with self.subTest(count=value):
                broken = counts.copy()
                broken["facility_count"] = value
                with self.assertRaises(ValueError):
                    count_neighbors(broken, candidate_grid())


if __name__ == "__main__":
    unittest.main()
