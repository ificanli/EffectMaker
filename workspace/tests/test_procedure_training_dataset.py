from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.procedure_training_dataset import build_procedure_training_dataset


ROOT = Path(__file__).parents[2]


class ProcedureTrainingDatasetTests(unittest.TestCase):
    def test_inferred_steps_remain_excluded_even_if_document_flags_claim_approval(self) -> None:
        source = ROOT / "workspace/data/vfx_generation/procedures/procedure_lightning_shape_lifecycle_r001/procedure_spec.json"
        spec = json.loads(source.read_text(encoding="utf-8"))
        spec["source"]["source_status"] = "verified"
        spec["validation"]["target_project_reproduction_status"] = "verified"
        spec["validation"]["visual_quality_status"] = "professionally_verified"
        spec["training_eligibility"]["controller_sft"] = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = root / "procedures" / "test"
            library.mkdir(parents=True)
            (library / "procedure_spec.json").write_text(json.dumps(spec), encoding="utf-8")
            paths = build_procedure_training_dataset(root / "procedures", root / "dataset", "inference_gate")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines()]
        self.assertEqual(manifest["controller_sft_count"], 0)
        self.assertIn("inferred_steps_require_separate_validation", exclusions[0]["reasons"])

    def test_verified_cross_version_tutorial_is_retrieval_supervision_but_not_sft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = build_procedure_training_dataset(
                ROOT / "workspace/data/vfx_generation/procedures",
                Path(directory) / "dataset",
                "procedure_training_test_r001",
            )
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/procedure_training_dataset.schema.json").read_text(encoding="utf-8"))
            constraints = [json.loads(line) for line in paths["planner_constraints"].read_text(encoding="utf-8").splitlines() if line]
            sft = [json.loads(line) for line in paths["controller_sft"].read_text(encoding="utf-8").splitlines() if line]
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines() if line]

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(manifest)), [])
        self.assertEqual(manifest["procedure_count"], 2)
        self.assertEqual(manifest["planner_constraint_count"], 2)
        self.assertEqual(manifest["target_verified_count"], 0)
        self.assertEqual(manifest["controller_sft_count"], 0)
        self.assertEqual(manifest["status"], "ready_for_retrieval_only")
        self.assertEqual(len(constraints), 2)
        self.assertEqual(sft, [])
        self.assertEqual(len(exclusions), 2)
        self.assertTrue(all("target_project_reproduction_not_verified" in row["reasons"] for row in exclusions))
        self.assertTrue(manifest["policy"]["tutorials_are_causal_supervision"])
        self.assertTrue(manifest["policy"]["prefabs_are_not_the_only_training_source"])


if __name__ == "__main__":
    unittest.main()
