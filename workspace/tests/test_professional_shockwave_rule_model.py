from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from workspace.tools.vfx_generation.professional_shockwave_rule_model import (
    CAPTURE_PROTOCOL,
    FEATURE_NAMES,
    feature_vector,
    prepare_evaluation_capture,
)


class ProfessionalShockwaveRuleModelTests(unittest.TestCase):
    def test_evaluation_capture_uses_fixed_camera_protocol(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            compile_path = root / "compile.json"
            source_path = root / "generation.json"
            compile_path.write_text(json.dumps({"status": "pass", "output_prefab_path": "Assets/X.prefab"}), encoding="utf-8")
            source_path.write_text(json.dumps({
                "run_id": "r001",
                "effect_family": "explosion",
                "candidates": [{
                    "candidate_id": "x",
                    "compile_result_path": compile_path.as_posix(),
                    "capture_manifest_path": "old.json",
                }],
            }), encoding="utf-8")

            paths = prepare_evaluation_capture(source_path, root / "evaluation")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            requests = json.loads(paths["runtime_request"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["capture_protocol"], CAPTURE_PROTOCOL)
        self.assertTrue(requests["requests"][0]["force_orthographic"])
        self.assertEqual(requests["requests"][0]["forced_camera_view"], "front")
        self.assertEqual(requests["width"], 640)

    def test_feature_vector_has_stable_order(self) -> None:
        row = {"image_features": {FEATURE_NAMES[0]: 0.2, FEATURE_NAMES[-1]: 0.8}}
        vector = feature_vector(row)

        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.2)
        self.assertEqual(vector[-1], 0.8)
        self.assertEqual(sum(vector[1:-1]), 0.0)

    def test_feature_contract_excludes_global_image_features(self) -> None:
        self.assertTrue(FEATURE_NAMES)
        self.assertTrue(all(name.startswith("shockwave.") for name in FEATURE_NAMES))


if __name__ == "__main__":
    unittest.main()
