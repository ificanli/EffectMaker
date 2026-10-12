from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from workspace.tools.vfx_generation.prompt_condition_scorer import (
    CONDITION_FIELDS,
    LABELS,
    ScorerNotReady,
    build_dataset,
    predict,
    train_scorer,
)


class PromptConditionScorerTests(unittest.TestCase):
    def test_current_human_overlay_builds_features_but_refuses_training(self) -> None:
        overlay = Path("workspace/data/vfx_generation/reviews/prompt_cartoon_blue_energy_impact_variation_r007_blue_fast_multi_material_conditions_r002/prompt_condition_human_label_overlays.jsonl")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = build_dataset([overlay], root / "dataset", "current_prompt_scorer")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            with self.assertRaises(ScorerNotReady):
                train_scorer(paths["manifest"], root / "model")
            model_exists = (root / "model" / "prompt_condition_scorer.joblib").is_file()
            preflight = json.loads((root / "model" / "training_preflight.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["overlay_count"], 1)
        self.assertEqual(manifest["feature_row_count"], 1)
        self.assertEqual(manifest["condition_counts"]["风格"], {})
        self.assertEqual(manifest["unknown_condition_counts"]["风格"], 1)
        self.assertFalse(model_exists)
        self.assertEqual(preflight["status"], "blocked_insufficient_labels")

    def test_trains_grouped_multitask_model_and_predicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = []
            for group_index in range(2):
                for label_index, label in enumerate(LABELS):
                    rows.append({
                        "candidate_id": f"c-{group_index}-{label_index}",
                        "group_id": f"group-{group_index}",
                        "features": {"blue_fraction_max": float(label_index), "temporal_delta_mean": float(group_index + label_index), "visible_ratio_max": 0.1 + label_index * 0.1},
                        "labels": {field: label for field in CONDITION_FIELDS},
                    })
            dataset = root / "dataset"
            dataset.mkdir()
            feature_path = dataset / "scorer_feature_rows.jsonl"
            feature_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            manifest_path = dataset / "scorer_dataset_manifest.json"
            manifest_path.write_text(json.dumps({"files": {"feature_rows": feature_path.name}}), encoding="utf-8")
            paths = train_scorer(manifest_path, root / "model", minimum_per_class=1, minimum_groups=2)
            image = np.zeros((32, 32, 3), dtype=np.uint8)
            image[8:24, 8:24] = (255, 100, 30)
            frame = root / "frame.png"
            self.assertTrue(cv2.imwrite(str(frame), image))
            prediction_path = predict(paths["model"], [frame], root / "prediction.json")
            prediction = json.loads(prediction_path.read_text(encoding="utf-8"))

        self.assertTrue(paths["model"].name.endswith(".joblib"))
        self.assertEqual(set(prediction["predicted_conditions"]), set(CONDITION_FIELDS))
        self.assertTrue(prediction["human_review_required"])


if __name__ == "__main__":
    unittest.main()
