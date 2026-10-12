from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.full_prefab_capture_report import finalize_capture_batch


class FullPrefabCaptureReportTests(unittest.TestCase):
    def test_real_r002_routes_visual_and_technical_records_without_aesthetic_labels(self) -> None:
        batch = Path("workspace/data/vfx_generation/captures/full_prefab_capture_r002")
        with tempfile.TemporaryDirectory() as temporary:
            paths = finalize_capture_batch(batch, Path(temporary) / "report")
            report = json.loads(paths["report"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in paths["records"].read_text(encoding="utf-8").splitlines()]
            technical = paths["technical_only"].read_text(encoding="utf-8").splitlines()

        self.assertEqual(report["capture_count"], 64)
        self.assertEqual(report["valid_frame_count"], 1411)
        self.assertEqual(report["invalid_frame_count"], 0)
        self.assertEqual(report["visual_feature_ready_count"], 51)
        self.assertEqual(report["technical_only_count"], 13)
        self.assertEqual(report["material_render_error_count"], 6)
        self.assertEqual(report["full_visual_ready_count"], 0)
        self.assertEqual(len(technical), 13)
        self.assertEqual(set(report["quality_gates"].values()), {0})
        self.assertTrue(all(row["aesthetic_label_source"] == "none" for row in records))
        self.assertTrue(all("aesthetic_judge" in row["training"]["excluded_tasks"] for row in records))


if __name__ == "__main__":
    unittest.main()
