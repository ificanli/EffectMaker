from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.material_plan_validation import build_validation


ROOT = Path(__file__).parents[2]


class MaterialPlanValidationTests(unittest.TestCase):
    def test_real_r004_keeps_technical_negatives_out_of_aesthetic_training(self) -> None:
        manifests = [ROOT / f"workspace/data/vfx_generation/generated/material_plan_prompt_r004/{family}/generation_manifest.json" for family in ("fire", "lightning", "slash")]
        baseline = ROOT / "workspace/data/vfx_generation/generated/material_plan_prompt_r003/runtime_captures"
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_validation(manifests, Path(temporary) / "validation", "test_validation", baseline)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in paths["records"].read_text(encoding="utf-8").splitlines()]
            negatives = [json.loads(line) for line in paths["technical_negatives"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["record_count"], 9)
        self.assertEqual(manifest["effect_family_counts"], {"fire": 3, "lightning": 3, "slash": 3})
        self.assertEqual(manifest["technical_label_counts"], {"near_blank": 1, "visible": 8})
        self.assertEqual(manifest["baseline_comparison"]["baseline_visible_count"], 5)
        self.assertEqual(manifest["baseline_comparison"]["visible_count_delta"], 3)
        self.assertEqual(set(manifest["quality_gates"].values()), {0})
        self.assertEqual(len(negatives), 1)
        self.assertTrue(all(row["aesthetic_label_source"] == "none" for row in records))
        self.assertTrue(all("aesthetic_judge" in row["training"]["excluded_tasks"] for row in records))
        self.assertTrue(all(row["compile"]["planned_texture_readback_match"] for row in records))
        self.assertTrue(all(not row["compile"]["generated_texture_paths"] for row in records))


if __name__ == "__main__":
    unittest.main()
