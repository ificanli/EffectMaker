from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.material_trajectory_dataset import (
    assign_strict_group_splits,
    build_material_trajectory_dataset,
    load_material_trajectory_examples,
)


class MaterialTrajectoryDatasetTests(unittest.TestCase):
    def test_strict_split_keeps_shader_and_material_groups_together(self) -> None:
        records = []
        for shader, count in (("shader_main", 8), ("shader_holdout", 3), ("shader_single", 1)):
            for index in range(count):
                records.append(
                    {
                        "example_id": f"{shader}_{index}",
                        "shader_group": shader,
                        "material_group": f"{shader}_material_{index // 2}",
                    }
                )

        assignments, strategy = assign_strict_group_splits(records, seed=42)

        self.assertEqual(strategy["component_count"], 3)
        self.assertIsNotNone(strategy["imbalance_warning"])
        self.assertEqual({assignments[f"shader_main_{index}"] for index in range(8)}, {"train"})
        self.assertEqual({assignments[f"shader_holdout_{index}"] for index in range(3)}, {"test"})
        self.assertEqual(assignments["shader_single_0"], "validation")

    def test_rejects_material_group_that_spans_shaders(self) -> None:
        records = [
            {"example_id": "a", "shader_group": "s1", "material_group": "shared"},
            {"example_id": "b", "shader_group": "s2", "material_group": "shared"},
            {"example_id": "c", "shader_group": "s3", "material_group": "m3"},
        ]

        with self.assertRaisesRegex(ValueError, "material group spans Shader groups"):
            assign_strict_group_splits(records, seed=42)

    def test_builds_verified_r002_dataset_deterministically(self) -> None:
        curriculum = Path("workspace/data/vfx_generation/curricula/material_trajectory_curriculum_r002")
        run = Path("workspace/data/vfx_generation/runs/material_trajectory_r002_full_r001")
        self.assertTrue(curriculum.is_dir(), "R002 curriculum evidence is required for this integration test")
        self.assertTrue(run.is_dir(), "R002 execution evidence is required for this integration test")

        with tempfile.TemporaryDirectory() as temporary:
            first_root = Path(temporary) / "first"
            second_root = Path(temporary) / "second"
            first = build_material_trajectory_dataset(curriculum, run, first_root, "test_r002", 20260828)
            second = build_material_trajectory_dataset(curriculum, run, second_root, "test_r002", 20260828)
            manifest = json.loads(first["dataset_manifest"].read_text(encoding="utf-8"))
            examples = [json.loads(line) for line in first["examples"].read_text(encoding="utf-8").splitlines()]
            image_examples = [json.loads(line) for line in first["image_conditioned_examples"].read_text(encoding="utf-8").splitlines()]

            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["example_count"], 100)
            self.assertEqual(manifest["material_state_example_count"], 100)
            self.assertEqual(manifest["image_conditioned_example_count"], 72)
            self.assertEqual(manifest["aesthetic_preference_example_count"], 0)
            self.assertEqual(manifest["splits"]["train"]["example_count"], 93)
            self.assertEqual(manifest["splits"]["test"]["example_count"], 6)
            self.assertEqual(manifest["splits"]["validation"]["example_count"], 1)
            self.assertEqual(manifest["splits"]["validation"]["image_conditioned_count"], 0)
            self.assertTrue(manifest["leakage_checks"]["passed"])
            self.assertEqual(manifest["leakage_checks"]["material_group_overlap_count"], 0)
            self.assertEqual(manifest["leakage_checks"]["shader_group_overlap_count"], 0)
            self.assertEqual(manifest["training_eligibility"]["aesthetic_preference"], "not_ready_no_human_labels")
            self.assertEqual(len(examples), 100)
            self.assertEqual(len(image_examples), 72)
            self.assertTrue(all(example["task_membership"]["material_state"] for example in examples))
            self.assertTrue(all(not example["task_membership"]["aesthetic_preference"] for example in examples))
            self.assertTrue(all(example["outputs"]["render_paths"] for example in image_examples))
            self.assertTrue(all(example["outputs"]["visual_evidence"]["status"] == "visible" for example in image_examples))
            self.assertTrue(all(example["label"]["aesthetic_quality"] == "unlabeled" for example in examples))
            self.assertEqual(
                first["examples"].read_text(encoding="utf-8"),
                second["examples"].read_text(encoding="utf-8"),
            )
            self.assertEqual(
                first["split_assignments"].read_text(encoding="utf-8"),
                second["split_assignments"].read_text(encoding="utf-8"),
            )
            self.assertEqual(len(load_material_trajectory_examples(first_root, task="material_state")), 100)
            self.assertEqual(len(load_material_trajectory_examples(first_root, task="image_conditioned")), 72)
            self.assertEqual(len(load_material_trajectory_examples(first_root, task="material_state", split="test")), 6)
            self.assertEqual(len(load_material_trajectory_examples(first_root, task="image_conditioned", split="validation")), 0)
            with self.assertRaisesRegex(ValueError, "no human aesthetic labels"):
                load_material_trajectory_examples(first_root, task="aesthetic_preference")


if __name__ == "__main__":
    unittest.main()
