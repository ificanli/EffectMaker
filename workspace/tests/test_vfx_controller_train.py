from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.vfx_controller_train import TrainingNotReady, audit, train


class VfxControllerTrainTests(unittest.TestCase):
    def test_preflight_refuses_current_insufficient_dataset_without_weight(self) -> None:
        dataset = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_variation_r009_all_layers")
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "dataset.json"
            manifest.write_text(json.dumps({"training_gate": {"status": "no_eligible_examples", "reason": "none", "positive_sft_ready": False}, "sft_example_count": 0, "family_counts": {"explosion": 1}}), encoding="utf-8")
            report = audit(manifest, Path(temporary) / "audit.json", minimum_sft_examples=32, minimum_sft_families=2)
            with self.assertRaises(TrainingNotReady):
                train(manifest, Path(temporary) / "output", minimum_sft_examples=32, minimum_sft_families=2)
            output_files = list((Path(temporary) / "output").glob("*"))
            report_payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(report_payload["status"], "blocked_insufficient_labels")
        self.assertTrue(all(path.suffix != ".pth" for path in output_files))

    def test_preflight_does_not_count_course_prior_family_as_labeled_sft_family(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/course_controller_r003/controller_dataset_manifest.json")
        self.assertTrue(dataset.is_file(), "real course Controller dataset is required")
        with tempfile.TemporaryDirectory() as temporary:
            report = audit(dataset, Path(temporary) / "audit.json", minimum_sft_examples=1, minimum_sft_families=1)
            payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(payload["sft_example_count"], 0)
        self.assertEqual(payload["labeled_family_count"], 0)
        self.assertEqual(payload["status"], "blocked_insufficient_labels")


if __name__ == "__main__":
    unittest.main()
