from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_graph_training_dataset_merge import merge_training_datasets


ROOT = Path(__file__).parents[2]


class PrefabGraphTrainingDatasetMergeTests(unittest.TestCase):
    def test_merges_real_r003_source_graphs_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "prefab_graph_r002"
            paths = merge_training_datasets(
                ROOT / "workspace/data/vfx_generation/datasets/prefab_graph_r001",
                ROOT / "workspace/data/vfx_generation/generated/prefab_graph_source_export_r003",
                output,
                "prefab_graph_r002",
            )
            manifest = json.loads(paths["dataset_manifest"].read_text(encoding="utf-8"))
            examples = [json.loads(line) for line in paths["examples"].read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["example_count"], 269)
            self.assertEqual(manifest["quality_gates"]["graph_schema_errors"], 0)
            self.assertEqual(manifest["quality_gates"]["duplicate_graph_ids"], 0)
            self.assertEqual(manifest["reconstruction_status_counts"]["reconstructable"], 10)
            self.assertEqual(len({row["graph_id"] for row in examples}), 269)
            source_rows = [row for row in examples if row["example_id"].startswith("prefab_graph_r002_trains_fx_")]
            self.assertEqual(len(source_rows), 10)
            self.assertTrue(all(row["split_group"]["prefab_group"] for row in source_rows))


if __name__ == "__main__":
    unittest.main()
