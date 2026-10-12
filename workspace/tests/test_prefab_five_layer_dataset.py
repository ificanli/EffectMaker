from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prefab_five_layer_dataset import assemble


ROOT = Path(__file__).parents[2]


class PrefabFiveLayerDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = ROOT / "workspace/data/vfx_generation/datasets/prefab_five_layer_r001"
        cls.manifest = json.loads((cls.root / "dataset_manifest.json").read_text(encoding="utf-8"))
        cls.records = [json.loads(line) for line in (cls.root / "records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_real_dataset_has_full_technical_coverage_and_strict_tiers(self) -> None:
        self.assertEqual(self.manifest["status"], "pass")
        self.assertEqual(self.manifest["sample_count"], 269)
        self.assertEqual(self.manifest["tier_counts"]["technical_corpus"], 269)
        self.assertEqual(self.manifest["quality_gates"]["technical_sample_coverage"], 1.0)
        self.assertEqual(self.manifest["quality_gates"]["duplicate_record_ids"], 0)
        self.assertEqual(self.manifest["quality_gates"]["duplicate_sample_tiers"], 0)

    def test_ai_and_human_label_provenance_do_not_mix(self) -> None:
        pseudo = [row for row in self.records if row["tier"] == "ai_pseudo_label"]
        human = [row for row in self.records if row["tier"] == "human_gold"]
        self.assertTrue(pseudo)
        self.assertTrue(human)
        self.assertTrue(all(row["label_provenance"]["label_source"] == "ai_pseudo_label" for row in pseudo))
        self.assertTrue(all(row["training"]["weight"] <= 0.2 for row in pseudo))
        self.assertTrue(all(row["label_provenance"]["label_source"] == "human" for row in human))
        self.assertTrue(all(row["training"]["weight"] >= 0.75 for row in human))

    def test_old_human_labels_are_pending_until_capture_v2(self) -> None:
        human = [row for row in self.records if row["tier"] == "human_gold"]
        pending = [row for row in human if row["status"] == "pending_revalidation"]
        ready = [row for row in human if row["status"] == "ready"]
        self.assertEqual(len(human), 41)
        self.assertEqual(len(pending), 39)
        self.assertEqual(len(ready), 2)
        self.assertTrue(all("regression_evaluation" in row["training"]["excluded_tasks"] for row in pending))

    def test_all_records_validate_against_layer_schema(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_training_layer_record.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        errors = [error for row in self.records for error in validator.iter_errors(row)]
        self.assertEqual(errors, [])

    def test_active_review_human_gold_merges_into_full_dataset(self) -> None:
        graph_root = ROOT / "workspace/data/vfx_generation/datasets/prefab_graph_full_r002"
        capture_root = ROOT / "workspace/data/vfx_generation/captures/full_prefab_capture_r002"
        timing_root = ROOT / "workspace/data/vfx_generation/captures/sword_slash_timing_r002"
        active_gold = ROOT / "workspace/data/vfx_generation/reviews/prefab_active_review_full_r005/human_gold.jsonl"
        with tempfile.TemporaryDirectory() as temporary:
            paths = assemble(
                graph_root,
                Path(temporary) / "full",
                "prefab_five_layer_active_review_test",
                [capture_root, timing_root],
                human_gold_paths=[active_gold],
            )
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            human = [json.loads(line) for line in paths["human_gold"].read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertIn("prefab_active_review", manifest["source_dataset_ids"])
        self.assertEqual(len(human), 16)
        self.assertTrue(all(row["status"] == "ready" for row in human))
        sword = next(row for row in human if row["source"]["prefab_path"].endswith("Sword Slash 1.prefab"))
        self.assertIn("sword_slash_timing_r002", sword["evidence"]["capture_manifest_path"])
        self.assertEqual(sword["labels"]["decision"], "AI判断正确")

    def test_current_review_labels_keep_element_and_type_separate(self) -> None:
        review_root = ROOT / "workspace/data/vfx_generation/reviews/prefab_active_review_full_r011"
        if not review_root.is_dir():
            self.skipTest("current normalized review batch is unavailable")
        rows = [json.loads(line) for line in (review_root / "feedback.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 32)
        self.assertTrue(all(row["review_scope"] == "semantic_function_only" for row in rows))
        self.assertTrue(all("effect_element_supervision" in row["result"]["eligible_tasks"] for row in rows))
        self.assertTrue(all("effect_type_supervision" in row["result"]["eligible_tasks"] for row in rows))
        self.assertTrue(all((row["semantic_selection"] or {}).get("selected_effect_type") != "hit" for row in rows))


if __name__ == "__main__":
    unittest.main()
