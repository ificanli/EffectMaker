from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prefab_graph_model import split_by_prefab_group, window_examples_for_training
from workspace.tools.vfx_generation.prefab_graph_training_view import build_training_view


ROOT = Path(__file__).parents[2]


class PrefabGraphTrainingViewTests(unittest.TestCase):
    def test_declared_structure_split_wins_over_group_hash(self) -> None:
        rows = [
            {"example_id": "train", "split_group": {"prefab_group": "shared", "structure_split": "train"}},
            {"example_id": "validation", "split_group": {"prefab_group": "shared", "structure_split": "validation"}},
        ]
        with self.assertRaises(ValueError):
            split_by_prefab_group(rows)

    def test_windowing_bounds_length_and_preserves_overlap(self) -> None:
        sequence = list(range(1200))
        rows = window_examples_for_training([("graph", sequence)], max_tokens=512, overlap=64)
        self.assertEqual([len(values) for _, values in rows], [512, 512, 304])
        self.assertEqual(rows[0][1][-64:], rows[1][1][:64])
        self.assertTrue(rows[1][0].endswith("window_0001"))

    def test_builds_schema_valid_view_and_aligns_graphs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            output = Path(temp) / "view"
            source.mkdir()
            examples = []
            graphs = []
            for index in range(120):
                example_id = f"example_{index:03d}"
                graph_id = f"graph_{index:03d}"
                examples.append({
                    "schema_version": "vfx_prefab_graph_training_example.v1",
                    "example_id": example_id,
                    "graph_id": graph_id,
                    "tokens": ["<PREFAB>", f"COMP_UNIQUE_{index}", "</PREFAB>"],
                    "split_group": {"prefab_group": f"group_{index:03d}", "source_group": "test"},
                    "eligible_tasks": ["hierarchy_modeling"],
                })
                graphs.append({"graph_id": graph_id, "order": index})
            (source / "dataset_manifest.json").write_text(json.dumps({
                "schema_version": "vfx_prefab_graph_training_dataset.v1",
                "dataset_id": "source",
                "status": "pass",
            }), encoding="utf-8")
            (source / "examples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in examples), encoding="utf-8")
            (source / "graphs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in reversed(graphs)), encoding="utf-8")
            paths = build_training_view(source, output, "view")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_graph_training_view.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(manifest)), [])
            view_examples = [json.loads(line) for line in paths["examples"].read_text(encoding="utf-8").splitlines() if line.strip()]
            view_graphs = [json.loads(line) for line in paths["graphs"].read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual([row["graph_id"] for row in view_examples], [row["graph_id"] for row in view_graphs])
            self.assertEqual(manifest["quality_gates"]["cluster_split_leakage"], 0)


if __name__ == "__main__":
    unittest.main()
