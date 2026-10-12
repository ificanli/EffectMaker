from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.aesthetic_preference_ranker import AestheticPreferenceNotReady, build_preflight, train_preference_ranker


class AestheticPreferenceRankerTests(unittest.TestCase):
    def _rows(self, count: int = 4) -> list[dict]:
        rows = []
        for index in range(count):
            run_id = f"run-{index % 2}"
            rows.append({
                "schema_version": "vfx_aesthetic_preference_example.v1",
                "record_id": f"pair-{index}",
                "candidate_a": f"candidate-a-{index}",
                "candidate_b": f"candidate-b-{index}",
                "preference": "a" if index % 2 == 0 else "b",
                "reason_codes": ["core_readability"],
                "human_note": "主体更清楚。",
                "split": "train",
                "group_id": f"prompt-group-{index}",
                "effect_family": "fire",
                "style_family": "cartoon",
                "features_a": {"image.edge": 0.8 + index / 100.0, "spec.width": 0.2},
                "features_b": {"image.edge": 0.1, "spec.width": 0.8 + index / 100.0},
                "provenance": {"run_id": run_id},
            })
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_real_preference_training_gate_is_empty_and_no_weight_is_written(self) -> None:
        path = Path("workspace/data/vfx_generation/datasets/aesthetic_training_r006/preference_training.jsonl")
        self.assertTrue(path.is_file(), "real aesthetic preference audit is required")
        preflight = build_preflight(path)

        self.assertEqual(preflight["status"], "no_eligible_examples")
        self.assertFalse(preflight["weight_written"])

    def test_training_refuses_insufficient_pairs_without_weight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._write_jsonl(root / "preference.jsonl", self._rows(1))
            output = root / "model"
            with self.assertRaises(AestheticPreferenceNotReady):
                train_preference_ranker(path, output, minimum_comparisons=4, minimum_candidates=8, minimum_runs=2)
            self.assertTrue((output / "training_preflight.json").is_file())
            self.assertFalse((output / "preference_ranker.joblib").exists())

    def test_trains_existing_pairwise_ranker_from_canonical_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._write_jsonl(root / "preference.jsonl", self._rows())
            output = root / "model"
            paths = train_preference_ranker(path, output, minimum_comparisons=4, minimum_candidates=8, minimum_runs=2)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            metrics = json.loads(paths["metrics"].read_text(encoding="utf-8"))
            self.assertTrue(paths["model"].is_file())

        self.assertEqual(manifest["status"], "experimental_pairwise_ranker")
        self.assertEqual(metrics["readiness"]["comparison_count"], 4)
        self.assertEqual(metrics["readiness"]["run_count"], 2)

    def test_validation_rows_are_not_used_for_fit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = self._rows(4)
            for row in rows:
                row["split"] = "validation"
            path = self._write_jsonl(root / "preference.jsonl", rows)
            preflight = build_preflight(path, minimum_comparisons=1, minimum_candidates=2, minimum_runs=1)

        self.assertEqual(preflight["status"], "no_eligible_examples")
        self.assertEqual(preflight["ignored_counts"].get("non_train_split_not_used_for_fit"), 4)
