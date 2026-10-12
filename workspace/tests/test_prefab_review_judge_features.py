from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_review_judge_features import build_judge_features


ROOT = Path(__file__).parents[2]


class PrefabReviewJudgeFeatureTests(unittest.TestCase):
    def test_real_r007_builds_unlabeled_judge_inputs_for_every_review_item(self) -> None:
        active = ROOT / "workspace/data/vfx_generation/active_learning/prefab_active_full_r003"
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_judge_features(active, Path(temporary) / "features")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["features"].read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(manifest["status"], "pass")
        self.assertEqual(manifest["record_count"], 32)
        self.assertEqual(len(rows), 32)
        self.assertTrue(all(row["provenance"]["label_status"] == "unlabeled_judge_input" for row in rows))
        self.assertTrue(all(row["features"]["image.frame_count"] > 0 for row in rows))
        self.assertTrue(all(row["features"]["spec.effect_type"] == "imported_prefab" for row in rows))


if __name__ == "__main__":
    unittest.main()
