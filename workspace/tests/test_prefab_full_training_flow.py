from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[2]


class PrefabFullTrainingFlowTests(unittest.TestCase):
    def test_full_five_layer_dataset_and_active_queue_are_current_and_isolated(self) -> None:
        dataset_root = ROOT / "workspace/data/vfx_generation/datasets/prefab_five_layer_full_r001"
        active_root = ROOT / "workspace/data/vfx_generation/active_learning/prefab_active_full_r001"
        review_root = ROOT / "workspace/data/vfx_generation/reviews/prefab_active_review_full_r003"
        dataset = json.loads((dataset_root / "dataset_manifest.json").read_text(encoding="utf-8"))
        batch = json.loads((active_root / "active_learning_batch.json").read_text(encoding="utf-8"))
        clusters = json.loads((active_root / "cluster_manifest.json").read_text(encoding="utf-8"))
        review = json.loads((review_root / "review_batch.json").read_text(encoding="utf-8"))
        store = json.loads((review_root / "feedback_store.json").read_text(encoding="utf-8"))

        self.assertEqual(dataset["sample_count"], 2115)
        self.assertEqual(dataset["tier_counts"], {"technical_corpus": 2115, "visual_feature_only": 60, "ai_pseudo_label": 703, "human_gold": 41, "regression_gold": 0})
        self.assertEqual(dataset["quality_gates"]["technical_sample_coverage"], 1.0)
        self.assertEqual(dataset["quality_gates"]["schema_errors"], 0)
        self.assertEqual(clusters["unit_count"], 2115)
        self.assertEqual(clusters["cluster_count"], 92)
        self.assertEqual(batch["eligible_count"], 58)
        self.assertEqual(batch["review_budget"], 16)
        self.assertEqual(batch["quality_gates"], {"already_gold_items": 0, "cluster_split_leakage": 0, "duplicate_queue_prefabs": 0, "duplicate_queue_samples": 0, "non_visual_items": 0, "regression_items": 0})
        self.assertEqual(review["record_count"], 16)
        self.assertTrue(all(row["capture_pipeline_version"] == "play_mode_runtime_isolated_multiview.v2" for row in review["records"]))
        self.assertTrue(all(0 <= row["peak_frame_index"] < len(row["frames"]) for row in review["records"]))
        self.assertTrue(all(len(row["allowed_actions"]) == 11 for row in review["records"]))
        self.assertFalse(any("explosion" in row["ai_summary_cn"] or "projectile" in row["ai_summary_cn"] or "magic_circle" in row["ai_summary_cn"] for row in review["records"]))
        self.assertEqual(store["records"], {})

        batch_schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_active_learning_batch.schema.json").read_text(encoding="utf-8"))
        review_schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_active_review_batch.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(batch_schema).iter_errors(batch)), [])
        self.assertEqual(list(Draft202012Validator(review_schema).iter_errors(review)), [])


if __name__ == "__main__":
    unittest.main()
