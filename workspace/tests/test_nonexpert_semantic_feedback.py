from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.nonexpert_semantic_feedback import reclassify


ROOT = Path(__file__).parents[2]


class NonExpertSemanticFeedbackTests(unittest.TestCase):
    def test_real_r005_keeps_semantics_and_excludes_aesthetic_opinions(self) -> None:
        source = ROOT / "workspace/data/vfx_generation/reviews/prefab_active_review_full_r005"
        with tempfile.TemporaryDirectory() as temporary:
            paths = reclassify(source, Path(temporary) / "semantic")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["semantic_human_gold"].read_text(encoding="utf-8").splitlines() if line.strip()]
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(manifest["input_human_gold_count"], 16)
        self.assertEqual(manifest["semantic_human_gold_count"], 9)
        self.assertEqual(manifest["excluded_count"], 7)
        self.assertEqual(manifest["exclusion_reason_counts"]["non_expert_aesthetic_feedback_not_trainable"], 2)
        self.assertEqual(manifest["exclusion_reason_counts"]["legacy_type_error_missing_corrected_function"], 5)
        self.assertEqual(len(rows), 9)
        self.assertEqual(len(exclusions), 7)
        self.assertTrue(all(row["labels"]["quality_score"] is None and row["labels"]["scores"] == {} for row in rows))
        self.assertTrue(all("non_expert_semantic_scope_only" in row["limitations"] for row in rows))
        self.assertEqual(sum(item["reason"] == "non_expert_aesthetic_feedback_not_trainable" for item in exclusions), 2)
        self.assertEqual(sum(item["reason"] == "legacy_type_error_missing_corrected_function" for item in exclusions), 5)


if __name__ == "__main__":
    unittest.main()
