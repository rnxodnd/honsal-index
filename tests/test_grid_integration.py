import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import filter_grid, locate


class GridFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "processed"
        self.out.mkdir()
        self.stats = self.root / "stats"
        self.code = filter_grid.km_code(1000250, 1999250)
        self.cell = {"grid_id": "G500_1000000_1999000", "x_center": "1000250",
                     "y_center": "1999250", "in_city_ratio": "1", "lat": "37.9", "lon": "127.7"}
        self.write_csv(self.out / "grid_500m.csv", [self.cell])
        geo = {"type": "FeatureCollection", "features": [{"type": "Feature",
               "geometry": {"type": "Point", "coordinates": [127.7, 37.9]}, "properties": self.cell.copy()}]}
        (self.out / "grid_500m.geojson").write_text(json.dumps(geo))
        self.outputs = [self.out / "grid_500m_filtered.csv", self.out / "grid_500m_filtered.geojson"]
        for path in self.outputs:
            path.write_bytes(b"existing result")

    def write_csv(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def write_stats(self, pop):
        for folder, pattern, items in filter_grid.STAT_FILES.values():
            rows = [{"격자코드": self.code, "통계항목": code,
                     "통계값": str(pop) if field == "pop_1km" else ""} for code, field in items.items()]
            self.write_csv(self.stats / folder / pattern.format(self.code[:2]), rows)

    def run_filter(self):
        with patch.object(filter_grid, "OUT_DIR", self.out), patch.object(filter_grid, "SGIS_DIR", self.stats), \
             patch("sys.argv", ["filter_grid.py"]), patch.object(filter_grid, "preview"):
            filter_grid.main()

    def assert_existing_results(self):
        for path in self.outputs:
            self.assertEqual(path.read_bytes(), b"existing result")

    def test_missing_source_preserves_previous_outputs(self):
        with self.assertRaises(FileNotFoundError):
            self.run_filter()
        self.assert_existing_results()

    def test_empty_filter_result_preserves_previous_outputs(self):
        self.write_stats(0)
        with self.assertRaises(SystemExit):
            self.run_filter()
        self.assert_existing_results()

    def test_missing_geometry_preserves_previous_outputs(self):
        self.write_stats(5)
        (self.out / "grid_500m.geojson").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_filter()
        self.assert_existing_results()

    def test_missing_household_values_are_not_zero_filled(self):
        self.write_stats(5)
        self.run_filter()
        rows = filter_grid.read_csv(self.outputs[0])
        self.assertEqual(rows[0]["pop_1km"], "5")
        self.assertEqual(rows[0]["hh_1km"], "")
        self.assertEqual(rows[0]["single_hh_1km"], "")
        geo = json.loads(self.outputs[1].read_text())
        self.assertIsNone(geo["features"][0]["properties"]["hh_1km"])


class LocateTests(unittest.TestCase):
    def test_coordinate_and_neighborhood_are_compatible_with_shared_grid(self):
        with Path("data/processed/grid_500m_filtered.csv").open(encoding="utf-8-sig", newline="") as stream:
            cells = list(csv.DictReader(stream))
        for cell in (cells[0], cells[len(cells) // 2], cells[-1]):
            actual = locate.grid_id_from_lonlat(float(cell["lon"]), float(cell["lat"]))
            self.assertEqual(actual, cell["grid_id"])
            neighbors = locate.neighbors_3x3(actual)
            self.assertEqual(len(set(neighbors)), 9)
            self.assertIn(actual, neighbors)

    def test_address_search_falls_back_to_keyword_without_live_api(self):
        empty = Mock(status_code=200)
        empty.json.return_value = {"documents": []}
        found = Mock(status_code=200)
        found.json.return_value = {"documents": [{"x": "127.730", "y": "37.881", "place_name": "춘천시청"}]}
        with patch.object(locate, "_kakao_key", return_value="unit-test-key"), \
             patch.object(locate.requests, "get", side_effect=[empty, found]) as request:
            lon, lat, name = locate.address_to_lonlat("춘천시청")
            self.assertEqual((lon, lat, name), (127.730, 37.881, "춘천시청"))
            self.assertEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
