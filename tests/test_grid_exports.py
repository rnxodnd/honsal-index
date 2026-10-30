"""격자 범위 내보내기가 미확인 통계와 기존 결과를 보존하는지 검증합니다."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import export_grid_bounds


class GridExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / "grid_500m_bounds.csv"
        self.output.write_bytes(b"previous verified output\n")
        self.previous = self.output.read_bytes()
        self.grids = ["G500_1000000_2000000", "G500_1000500_2000000"]
        self.write_csv("grid_500m.csv", [
            {"grid_id": gid, "adm_nm": "검증용 동", "lat": "37.0", "lon": "127.0"}
            for gid in self.grids
        ])
        self.write_csv("grid_500m_filtered.csv", [{
            "grid_id": self.grids[0], "pop_1km": "7", "hh_1km": "3", "single_hh_1km": "0",
        }])
        self.geometry_path = self.root / "grid_500m.geojson"
        self.geometry_path.write_text(json.dumps({
            "type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"grid_id": gid}, "geometry": {
                    "type": "Polygon", "coordinates": [[
                        [127.0 + index * 0.01, 37.0], [127.01 + index * 0.01, 37.0],
                        [127.01 + index * 0.01, 37.01], [127.0 + index * 0.01, 37.01],
                        [127.0 + index * 0.01, 37.0],
                    ]],
                }} for index, gid in enumerate(self.grids)
            ],
        }), encoding="utf-8")

    def write_csv(self, filename, rows):
        with (self.root / filename).open("w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def run_export(self):
        with patch.object(export_grid_bounds, "D", self.root):
            export_grid_bounds.main()

    def test_noncandidate_statistics_are_unknown_and_recorded_zero_is_preserved(self):
        self.run_export()
        with self.output.open(encoding="utf-8-sig", newline="") as fp:
            rows = {row["grid_id"]: row for row in csv.DictReader(fp)}
        candidate, other = rows[self.grids[0]], rows[self.grids[1]]
        self.assertEqual(candidate["is_populated"], "1")
        self.assertEqual(candidate["pop_1km"], "7")
        self.assertEqual(candidate["single_hh_1km"], "0")
        self.assertEqual(other["is_populated"], "0")
        for column in ("pop_1km", "hh_1km", "single_hh_1km"):
            self.assertEqual(other[column], "")

    def test_empty_geometry_preserves_previous_output(self):
        self.geometry_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "도형이 없습니다"):
            self.run_export()
        self.assertEqual(self.output.read_bytes(), self.previous)

    def test_missing_or_empty_candidate_list_preserves_previous_output(self):
        path = self.root / "grid_500m_filtered.csv"
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_export()
        self.assertEqual(self.output.read_bytes(), self.previous)
        path.write_text("grid_id,pop_1km,hh_1km,single_hh_1km\n", encoding="utf-8-sig")
        with self.assertRaisesRegex(ValueError, "비어 있습니다"):
            self.run_export()
        self.assertEqual(self.output.read_bytes(), self.previous)


if __name__ == "__main__":
    unittest.main()
