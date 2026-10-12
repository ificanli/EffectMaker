from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prefab_graph_generation_report import _training_eligibility


ROOT = Path(__file__).parents[2]


class PrefabGraphGenerationReportTests(unittest.TestCase):
    def test_near_blank_is_excluded_from_visual_training(self) -> None:
        capture = {
            "capture_pipeline_version": "play_mode_runtime_isolated_multiview.v2",
            "invalid_frame_count": 0,
            "technical_frame_eligible": True,
            "image_sequence_training_eligible": False,
            "visual_evidence_status": "near_blank",
        }
        integrity = {"material_render_error": False}
        compile_result = {"status": "pass"}
        readback = {"status": "pass", "differences": []}
        self.assertEqual(_training_eligibility(capture, integrity, compile_result, readback), (False, "near_blank"))

    def test_generation_report_schema_is_strict(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_graph_generation_report.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["status"]["const"], "pass")
        self.assertIn("all_texture_bindings_verified", schema["properties"]["quality_gates"]["required"])
        self.assertEqual(schema["additionalProperties"], False)
        self.assertIsInstance(Draft202012Validator(schema), Draft202012Validator)


if __name__ == "__main__":
    unittest.main()
