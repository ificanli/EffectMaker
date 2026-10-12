from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.aesthetic_judge import build_preflight
from workspace.tools.vfx_generation.prefab_regression_gold import freeze_regression_gold


ROOT = Path(__file__).parents[2]


class PrefabRegressionGoldTests(unittest.TestCase):
    def test_freezes_only_capture_v2_human_gold_and_isolates_whole_clusters(self) -> None:
        dataset = ROOT / "workspace/data/vfx_generation/datasets/prefab_five_layer_r001"
        active = ROOT / "workspace/data/vfx_generation/active_learning/prefab_active_r004"
        judge = ROOT / "workspace/data/vfx_generation/datasets/aesthetic_training_r006/judge_training.jsonl"
        with tempfile.TemporaryDirectory() as temporary:
            paths = freeze_regression_gold(dataset, active, Path(temporary) / "freeze", "test_freeze", judge_training_path=judge)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            regression = [json.loads(line) for line in paths["regression_gold"].read_text(encoding="utf-8").splitlines()]
            training = [json.loads(line) for line in paths["training_records"].read_text(encoding="utf-8").splitlines()]
            pseudo = [json.loads(line) for line in paths["pseudo_propagation_records"].read_text(encoding="utf-8").splitlines()]
            filtered_judge = [json.loads(line) for line in paths["judge_training_excluding_regression"].read_text(encoding="utf-8").splitlines()]
            regression_judge = [json.loads(line) for line in paths["judge_regression_rows"].read_text(encoding="utf-8").splitlines()]
            preflight = build_preflight(paths["judge_training_excluding_regression"])

        self.assertEqual(manifest["eligible_count"], 2)
        self.assertEqual(manifest["frozen_count"], 2)
        self.assertEqual(manifest["status"], "underfilled")
        self.assertEqual(set(manifest["quality_gates"].values()), {0})
        self.assertEqual(len(regression), 2)
        self.assertTrue(all(row["tier"] == "regression_gold" and row["status"] == "frozen" for row in regression))
        self.assertTrue(all(row["training"]["weight"] == 0 and not row["training"]["eligible_tasks"] for row in regression))
        self.assertTrue(all(row["training"]["split"] == "regression" and row["training"]["frozen"] for row in regression))
        self.assertTrue(all(row["label_provenance"]["label_source"] == "regression_frozen" for row in regression))
        regression_clusters = set(manifest["regression_cluster_ids"])
        heldout_prefabs = set(manifest["held_out_prefab_paths"])
        self.assertFalse(any(row["grouping"]["cluster_id"] in regression_clusters for row in training))
        self.assertFalse(any(str(row["source"].get("prefab_path") or "").replace("\\", "/").lower() in heldout_prefabs for row in pseudo))
        self.assertFalse(any(str((row.get("provenance") or {}).get("prefab_path") or "").replace("\\", "/").lower() in heldout_prefabs for row in filtered_judge))
        self.assertGreaterEqual(manifest["historical_training_audit"]["direct_regression_overlap_count"], 2)
        self.assertEqual(len(regression_judge), 2)
        self.assertFalse({row["candidate_id"] for row in regression_judge} & {row["candidate_id"] for row in filtered_judge})
        self.assertTrue(manifest["historical_training_audit"]["affected_existing_models_must_not_use_this_regression_set"])
        self.assertEqual(preflight["status"], "partial_ready")
        self.assertEqual(preflight["blocked_tasks"], ["style_family"])
        record_schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_training_layer_record.schema.json").read_text(encoding="utf-8"))
        self.assertEqual([error for row in regression for error in Draft202012Validator(record_schema).iter_errors(row)], [])


if __name__ == "__main__":
    unittest.main()
