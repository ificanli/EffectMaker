from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.aesthetic_judge import AestheticJudgeError, JudgeTrainingNotReady, build_preflight, evaluate_regression, predict, train_judge


class AestheticJudgeTests(unittest.TestCase):
    def _rows(self, count: int = 40) -> list[dict]:
        rows = []
        for index in range(count):
            style = "cartoon" if index % 2 else "realistic"
            value = float(index % 10) / 10.0
            rows.append({
                "schema_version": "vfx_aesthetic_training_example.v1",
                "record_id": f"record-{index}",
                "candidate_id": f"candidate-{index}",
                "effect_family": "fire",
                "style_family": style,
                "split": "train",
                "group_id": f"run-{index // 10}",
                "evaluation_group_id": f"run-{index // 10}",
                "label": {
                    "quality_score": 1 + index % 5,
                    "scores": {
                        "core_readability": index % 6,
                        "layer_separation": (index + 1) % 6,
                        "rhythm": (index + 2) % 6,
                        "material": (index + 3) % 6,
                        "composition": (index + 4) % 6,
                    },
                },
                "features": {"image.edge_density.mean": value, "spec.layers.length": float(index % 4)},
                "provenance": {"prefab_path": f"Assets/FX/fire/{index % 5}.prefab"},
            })
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_real_aesthetic_judge_gate_allows_ready_score_heads(self) -> None:
        path = Path("workspace/data/vfx_generation/datasets/aesthetic_training_r006/judge_training.jsonl")
        self.assertTrue(path.is_file(), "real aesthetic training audit is required")
        preflight = build_preflight(path)

        self.assertEqual(preflight["status"], "partial_ready")
        self.assertIn("style_family", preflight["reason"])
        self.assertEqual(preflight["ready_tasks"], ["quality_score", "core_readability", "layer_separation", "rhythm", "material", "composition"])
        self.assertEqual(preflight["blocked_tasks"], ["style_family"])
        self.assertFalse(preflight["weight_written"])

    def test_training_refuses_insufficient_labels_without_writing_weight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._write_jsonl(root / "judge_training.jsonl", self._rows(4))
            output = root / "model"
            with self.assertRaises(JudgeTrainingNotReady):
                train_judge(path, output, minimum_examples=8, minimum_groups=2, minimum_style_per_class=2)
            self.assertTrue((output / "training_preflight.json").is_file())
            self.assertFalse((output / "aesthetic_judge.joblib").exists())

    def test_trains_multitask_baseline_and_predicts_scores_and_style(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._write_jsonl(root / "judge_training.jsonl", self._rows())
            output = root / "model"
            paths = train_judge(path, output, minimum_examples=8, minimum_groups=2, minimum_style_per_class=2)
            predictions = predict(paths["model"], path, root / "predictions.json")
            metrics = json.loads(paths["metrics"].read_text(encoding="utf-8"))
            predicted = json.loads(predictions.read_text(encoding="utf-8"))
            self.assertTrue(paths["model"].is_file())
            self.assertEqual(metrics["model_status"], "experimental_lightweight_multitask")
            self.assertEqual(predicted["prediction_count"], 40)
            self.assertIn("quality_score", predicted["predictions"][0])
            self.assertIn(predicted["predictions"][0]["style_family"], {"cartoon", "realistic"})
            self.assertIn("style_probabilities", predicted["predictions"][0])
            self.assertNotIn("unknown", predicted["predictions"][0]["style_probabilities"])
            pseudo = predicted["predictions"][0]["ai_pseudo_label"]
            self.assertEqual(pseudo["label_source"], "ai_pseudo_label")
            self.assertLessEqual(pseudo["training_weight"], 0.2)
            self.assertTrue(pseudo["expires_with_model_version"])
            self.assertEqual(set(pseudo["task_confidences"]), set(pseudo["task_disagreements"]))
            self.assertGreaterEqual(pseudo["model_disagreement"], 0.0)
            self.assertLessEqual(pseudo["model_disagreement"], 1.0)
            self.assertIn("regression_evaluation", pseudo["excluded_tasks"])

    def test_partial_training_writes_only_ready_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = self._rows()
            for row in rows:
                row["style_family"] = "unknown"
            path = self._write_jsonl(root / "judge_training.jsonl", rows)
            paths = train_judge(path, root / "model", minimum_examples=8, minimum_groups=2, minimum_style_per_class=2)
            predictions_path = predict(paths["model"], path, root / "predictions.json")
            metrics = json.loads(paths["metrics"].read_text(encoding="utf-8"))
            preflight = json.loads(paths["preflight"].read_text(encoding="utf-8"))
            predicted = json.loads(predictions_path.read_text(encoding="utf-8"))

        self.assertEqual(preflight["status"], "partial_ready")
        self.assertTrue(preflight["weight_written"])
        self.assertEqual(metrics["model_status"], "experimental_lightweight_partial_multitask")
        self.assertEqual(metrics["blocked_tasks"].keys(), {"style_family"})
        self.assertNotIn("style_family", predicted["available_tasks"])
        self.assertIn("style_family", predicted["blocked_tasks"])
        self.assertNotIn("style_family", predicted["predictions"][0])
        self.assertNotIn("style_probabilities", predicted["predictions"][0])
        self.assertEqual(set(predicted["predictions"][0]["ai_pseudo_label"]["task_confidences"]), set(metrics["available_tasks"]))

    def test_regression_evaluation_rejects_leakage_and_reports_underfilled_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            training_rows = self._rows()
            for row in training_rows:
                row["style_family"] = "unknown"
            training_path = self._write_jsonl(root / "judge_training.jsonl", training_rows)
            model_path = train_judge(training_path, root / "model", minimum_examples=8, minimum_groups=2, minimum_style_per_class=2)["model"]
            leaked_path = self._write_jsonl(root / "leaked.jsonl", [training_rows[0]])
            with self.assertRaisesRegex(AestheticJudgeError, "regression contamination"):
                evaluate_regression(model_path, leaked_path, root / "leaked_report.json", minimum_samples=8)

            regression_rows = []
            for index, row in enumerate(training_rows[:2]):
                copied = json.loads(json.dumps(row))
                copied["record_id"] = f"regression-{index}"
                copied["candidate_id"] = f"regression-candidate-{index}"
                copied["provenance"]["prefab_path"] = f"Assets/FX/regression/{index}.prefab"
                regression_rows.append(copied)
            regression_path = self._write_jsonl(root / "regression.jsonl", regression_rows)
            paths = evaluate_regression(model_path, regression_path, root / "regression_report.json", minimum_samples=8)
            report = json.loads(paths["evaluation"].read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "underfilled")
        self.assertFalse(report["promotion_eligible"])
        self.assertEqual(report["training_overlap_count"], 0)
        self.assertEqual(report["sample_count"], 2)
        self.assertEqual(report["metrics"]["quality_score"]["sample_count"], 2)
        self.assertIn("mae", report["metrics"]["material"])

    def test_style_task_has_its_own_label_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = self._rows(20)
            for row in rows:
                row["style_family"] = "cartoon"
            path = self._write_jsonl(root / "judge_training.jsonl", rows)
            preflight = build_preflight(path, minimum_examples=8, minimum_groups=2, minimum_style_per_class=2)

        self.assertEqual(preflight["status"], "partial_ready")
        self.assertIn("style_family", preflight["tasks"])
        self.assertTrue(preflight["tasks"]["style_family"]["reasons"])

    def test_style_class_must_span_evaluation_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = self._rows(40)
            for row in rows:
                row["style_family"] = "cartoon" if row["evaluation_group_id"] == "run-0" else "realistic"
            path = self._write_jsonl(root / "judge_training.jsonl", rows)
            preflight = build_preflight(path, minimum_examples=8, minimum_groups=2, minimum_style_per_class=2)

        self.assertEqual(preflight["tasks"]["style_family"]["group_count"], 4)
        self.assertIn("each style class needs labels in 2 evaluation groups", preflight["tasks"]["style_family"]["reasons"])

    def test_unknown_style_is_not_a_style_training_class(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = self._rows(40)
            for row in rows:
                row["style_family"] = "unknown"
            path = self._write_jsonl(root / "judge_training.jsonl", rows)
            preflight = build_preflight(path, minimum_examples=8, minimum_groups=2, minimum_style_per_class=2)

        self.assertEqual(preflight["tasks"]["style_family"]["label_count"], 0)
        self.assertEqual(preflight["status"], "partial_ready")


if __name__ == "__main__":
    unittest.main()
