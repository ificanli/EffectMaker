from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_preference_ranker import TrainingDataError, rank_candidates, train_pairwise_ranker


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class VfxPreferenceRankerTests(unittest.TestCase):
    def _dataset(self, root: Path) -> tuple[Path, Path]:
        features: list[dict] = []
        feedback: list[dict] = []
        for run_index, run_id in enumerate(("run-a", "run-b"), start=1):
            candidate_ids = [f"{run_id}-low", f"{run_id}-high"]
            features.extend(
                [
                    {"run_id": run_id, "candidate_id": candidate_ids[0], "features": {"image.edge": 0.1, "spec.width": 0.9, "family": "slash"}},
                    {"run_id": run_id, "candidate_id": candidate_ids[1], "features": {"image.edge": 0.8, "spec.width": 0.4, "family": "slash"}},
                ]
            )
            for comparison_index in range(3):
                feedback.append(
                    {
                        "run_id": run_id,
                        "candidate_id": candidate_ids[1],
                        "pairwise": {
                            "compared_candidate_id": candidate_ids[0],
                            "preference": "candidate",
                            "reason": f"comparison {run_index}-{comparison_index}",
                        },
                    }
                )
        feature_path = root / "features.jsonl"
        feedback_path = root / "feedback.jsonl"
        _write_jsonl(feature_path, features)
        _write_jsonl(feedback_path, feedback)
        return feature_path, feedback_path

    def test_refuses_to_write_model_when_labels_are_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            feature_path, _feedback_path = self._dataset(root)
            empty_feedback = root / "empty.jsonl"
            empty_feedback.write_text("", encoding="utf-8")
            output = root / "model"

            with self.assertRaises(TrainingDataError):
                train_pairwise_ranker([feature_path], [empty_feedback], output, min_comparisons=1, min_candidates=2, min_runs=1)

            self.assertFalse(output.exists())

    def test_trains_and_ranks_with_grouped_pairwise_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            feature_path, feedback_path = self._dataset(root)
            output = root / "model"

            paths = train_pairwise_ranker(
                [feature_path],
                [feedback_path],
                output,
                min_comparisons=4,
                min_candidates=4,
                min_runs=2,
            )
            ranking_path = rank_candidates(paths["model"], [feature_path], root / "ranking.json")

            metrics = json.loads(paths["metrics"].read_text(encoding="utf-8"))
            ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
            self.assertTrue(paths["model"].exists())
            self.assertEqual(metrics["evaluation"]["grouping"], "run_id")
            self.assertFalse(metrics["evaluation"]["candidate_leakage_risk"])
            self.assertEqual(ranking["candidate_count"], 4)
            high_scores = [row["preference_score"] for row in ranking["ranking"] if row["candidate_id"].endswith("high")]
            low_scores = [row["preference_score"] for row in ranking["ranking"] if row["candidate_id"].endswith("low")]
            self.assertGreater(min(high_scores), max(low_scores))


if __name__ == "__main__":
    unittest.main()
