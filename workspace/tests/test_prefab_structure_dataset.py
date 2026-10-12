from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_structure_dataset import (
    build_prefab_structure_dataset,
    load_prefab_structure_examples,
)


class PrefabStructureDatasetTests(unittest.TestCase):
    def test_builds_real_trains_prefab_structure_dataset(self) -> None:
        cases = Path("workspace/data/vfx_generation/datasets/trains_fx_all_002/prefab_cases.jsonl")
        audit = Path("workspace/data/vfx_generation/audits/effectdemo_prefab_structure_audit_r2.json")
        project = Path("UnityDemo/EffectDemo")
        self.assertTrue(cases.is_file())
        self.assertTrue(audit.is_file())

        with tempfile.TemporaryDirectory() as temporary:
            first_root = Path(temporary) / "first"
            second_root = Path(temporary) / "second"
            rendered_root = Path(temporary) / "rendered"
            first = build_prefab_structure_dataset(cases, audit, project, first_root, "test_prefab_structure")
            second = build_prefab_structure_dataset(cases, audit, project, second_root, "test_prefab_structure")
            rendered = build_prefab_structure_dataset(
                cases,
                audit,
                project,
                rendered_root,
                "test_prefab_structure_rendered",
                Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002"),
            )
            manifest = json.loads(first["dataset_manifest"].read_text(encoding="utf-8"))
            examples = [json.loads(line) for line in first["examples"].read_text(encoding="utf-8").splitlines()]
            render_candidates = [json.loads(line) for line in first["play_mode_render_candidates"].read_text(encoding="utf-8").splitlines()]

            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["example_count"], 259)
            self.assertEqual(manifest["prefab_structure_example_count"], 259)
            self.assertEqual(manifest["particle_parameter_example_count"], 220)
            self.assertEqual(manifest["play_mode_render_candidate_count"], 79)
            self.assertEqual(manifest["image_conditioned_example_count"], 0)
            self.assertEqual(manifest["aesthetic_preference_example_count"], 0)
            self.assertEqual(len(examples), 259)
            self.assertEqual(len(render_candidates), 79)
            self.assertTrue(all(example["task_membership"]["prefab_structure"] for example in examples))
            self.assertTrue(all(not example["task_membership"]["image_conditioned"] for example in examples))
            self.assertTrue(all(not example["task_membership"]["aesthetic_preference"] for example in examples))
            self.assertTrue(all(not example["outputs"]["render_paths"] for example in examples))
            self.assertTrue(all(example["label"]["aesthetic_quality"] == "unlabeled" for example in examples))
            self.assertTrue(all(example["label"]["technical_status"] == "particle_playable" for example in render_candidates))
            self.assertTrue(any(example["inputs"]["dependency_health"]["missing_dependency_count"] for example in render_candidates))
            self.assertEqual(first["examples"].read_text(encoding="utf-8"), second["examples"].read_text(encoding="utf-8"))
            self.assertEqual(len(load_prefab_structure_examples(first_root, "prefab_structure")), 259)
            self.assertEqual(len(load_prefab_structure_examples(first_root, "particle_parameters")), 220)
            self.assertEqual(len(load_prefab_structure_examples(first_root, "play_mode_render_candidate")), 79)
            with self.assertRaisesRegex(ValueError, "no human aesthetic labels"):
                load_prefab_structure_examples(first_root, "aesthetic_preference")
            rendered_manifest = json.loads(rendered["dataset_manifest"].read_text(encoding="utf-8"))
            self.assertEqual(rendered_manifest["rendered_example_count"], 59)
            self.assertEqual(rendered_manifest["image_conditioned_example_count"], 36)
            self.assertEqual(rendered_manifest["render_status_counts"], {"pass": 2, "reject": 23, "warn": 34})
            self.assertEqual(len(load_prefab_structure_examples(rendered_root, "image_conditioned")), 36)


if __name__ == "__main__":
    unittest.main()
