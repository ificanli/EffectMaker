from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.runtime_capture_regression import CASES, finalize, prepare


ROOT = Path(__file__).parents[2]


class RuntimeCaptureRegressionTests(unittest.TestCase):
    def test_regression_suite_covers_five_failure_categories(self) -> None:
        self.assertEqual({case[0] for case in CASES}, {"instant", "moving", "ground", "ui", "script_material"})

    def test_prepare_writes_eight_second_multicategory_request(self) -> None:
        project = ROOT / "UnityDemo/EffectDemo"
        with tempfile.TemporaryDirectory() as temporary:
            request_path = prepare(project, Path(temporary) / "capture")
            request = json.loads(request_path.read_text(encoding="utf-8"))

        self.assertEqual(request["sampling"]["max_duration_seconds"], 8.0)
        self.assertEqual(request["sampling"]["max_interval_seconds"], 0.1)
        self.assertEqual(len(request["requests"]), 5)
        self.assertEqual({row["capture_category"] for row in request["requests"]}, {"instant", "moving", "ground", "ui", "script_material"})

    def test_finalize_contract_requires_controlled_probe_but_not_unknown_prefabs(self) -> None:
        source = (ROOT / "workspace/tools/vfx_generation/runtime_capture_regression.py").read_text(encoding="utf-8")
        self.assertTrue(callable(finalize))
        self.assertIn("controlled_probe_global_and_mpb_instrumented", source)
        self.assertIn('row["category"] != "script_material"', source)
        self.assertIn('row["camera_candidate_count"] >= 3', source)


if __name__ == "__main__":
    unittest.main()
