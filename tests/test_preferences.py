"""사용자 시설 선택이 지도와 점수에 일관되게 반영되는지 검증합니다."""

import unittest

import pandas as pd

from src.scoring.preferences import (
    available_facility_types, calculate_preference_scores,
    filter_facilities, normalize_selected_weights,
)


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        # 검증 전용 가상 자료. 실제 춘천 관측값이 아닙니다.
        self.scores = pd.DataFrame([
            ("A", "leisure_community", "당구장", 90),
            ("A", "leisure_community", "볼링장", 20),
            ("A", "leisure_community", "탁구장", 100),
            ("B", "leisure_community", "당구장", 30),
            ("B", "leisure_community", "볼링장", 80),
            ("B", "leisure_community", "탁구장", 0),
        ], columns=["grid_id", "analysis_category", "analysis_subtype", "score"])

    def test_selecting_a_different_facility_changes_ranking(self):
        billiards = calculate_preference_scores(self.scores, {"leisure_community": ["당구장"]}).set_index("grid_id")
        bowling = calculate_preference_scores(self.scores, {"leisure_community": ["볼링장"]}).set_index("grid_id")
        self.assertEqual(billiards.loc["A", "rank"], 1)
        self.assertEqual(bowling.loc["B", "rank"], 1)

    def test_unselected_facilities_do_not_affect_scores(self):
        selection = {"leisure_community": ["당구장", "볼링장"]}
        expected = calculate_preference_scores(self.scores, selection)
        changed = self.scores.copy()
        changed.loc[changed.analysis_subtype.eq("탁구장"), "score"] = None
        pd.testing.assert_frame_equal(expected, calculate_preference_scores(changed, selection))
        self.assertEqual(expected.total_score.tolist(), [55, 55])

    def test_missing_selected_score_is_not_zero_or_partial_average(self):
        data = self.scores.drop(index=1)
        result = calculate_preference_scores(data, {"leisure_community": ["당구장", "볼링장"]}).set_index("grid_id")
        self.assertTrue(pd.isna(result.loc["A", "total_score"]))
        self.assertFalse(result.loc["A", "eligible_for_ranking"])
        self.assertTrue(pd.isna(result.loc["A", "rank"]))
        self.assertEqual(result.loc["B", "total_score"], 55)

    def test_an_entirely_unavailable_selected_type_remains_unavailable(self):
        result = calculate_preference_scores(self.scores, {"leisure_community": ["영화관"]})
        self.assertTrue(result.total_score.isna().all())

    def test_map_filter_uses_same_selection_and_preserves_original(self):
        facilities = self.scores.drop(columns=["grid_id", "score"]).assign(facility_id=list("abcdef"))
        before = facilities.copy(deep=True)
        options = available_facility_types(facilities)
        self.assertEqual(set(options["leisure_community"]), {"당구장", "볼링장", "탁구장"})
        actual = filter_facilities(facilities, {"leisure_community": ["볼링장"]})
        self.assertEqual(actual.facility_id.tolist(), ["b", "e"])
        pd.testing.assert_frame_equal(before, facilities)
        with self.assertRaises(ValueError):
            filter_facilities(facilities, {"leisure_community": ["없는유형"]})

    def test_weights_exclude_unselected_categories(self):
        actual = normalize_selected_weights({"healthcare": ["약국"], "transport": ["버스정류장"]})
        self.assertEqual(set(actual), {"healthcare", "transport"})
        self.assertAlmostEqual(actual["healthcare"], 3 / 7)
        self.assertAlmostEqual(actual["transport"], 4 / 7)
        self.assertAlmostEqual(sum(actual.values()), 1)

    def test_invalid_inputs_and_duplicate_scores_are_rejected(self):
        for selection in [{}, {"safety": ["CCTV"]}, {"leisure_community": "당구장"}]:
            with self.assertRaises(ValueError):
                calculate_preference_scores(self.scores, selection)
        with self.assertRaises(ValueError):
            normalize_selected_weights({"leisure_community": ["당구장"]}, {"leisure_community": 0})
        with self.assertRaises(ValueError):
            calculate_preference_scores(pd.concat([self.scores, self.scores.iloc[[0]]]), {"leisure_community": ["당구장"]})

    def test_zero_weight_does_not_hide_other_categories_missing_scores(self):
        extra = pd.DataFrame([("A", "healthcare", "약국", 70), ("B", "healthcare", "약국", None)], columns=self.scores.columns)
        result = calculate_preference_scores(pd.concat([self.scores, extra]),
            {"leisure_community": ["당구장"], "healthcare": ["약국"]},
            {"leisure_community": 0, "healthcare": 1}).set_index("grid_id")
        self.assertEqual(result.loc["A", "total_score"], 70)
        self.assertTrue(pd.isna(result.loc["B", "total_score"]))

    def test_empty_identifiers_are_rejected(self):
        for invalid in ["", "   ", None]:
            facility = pd.DataFrame([{
                "facility_id": invalid, "analysis_category": "leisure_community",
                "analysis_subtype": "당구장",
            }])
            with self.assertRaises(ValueError):
                filter_facilities(facility, {"leisure_community": ["당구장"]})
            scores = self.scores.copy()
            scores.loc[0, "grid_id"] = invalid
            with self.assertRaises(ValueError):
                calculate_preference_scores(scores, {"leisure_community": ["당구장"]})


if __name__ == "__main__":
    unittest.main()
