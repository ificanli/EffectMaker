from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prompt_condition_review import (
    CONDITION_FIELDS,
    build_review_batch,
    build_variation_review_batch,
    finalize_feedback,
    save_feedback,
)


class PromptConditionReviewTests(unittest.TestCase):
    @property
    def composition_root(self) -> Path:
        return Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_composed_r005_human_bound")

    def test_builds_separate_prompt_condition_batch_and_ai_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.composition_root, root, "prompt_condition_test")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            drafts = [json.loads(line) for line in paths["ai_drafts"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(batch["selected_count"], 6)
        self.assertEqual(batch["prompt_condition"]["style_family"], "cartoon")
        self.assertEqual(len(drafts), 6)
        self.assertTrue(all(row["status"] == "ai_draft_not_human_label" for row in drafts))
        self.assertTrue(all(row["frames"] for row in batch["records"]))

    def test_finalization_excludes_all_unknown_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.composition_root, root, "prompt_condition_finalize")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            for index, record in enumerate(batch["records"]):
                conditions = {field: "无法判断" for field in CONDITION_FIELDS} if index == 0 else {field: "符合" for field in CONDITION_FIELDS}
                save_feedback(root, {"candidate_id": record["candidate_id"], "conditions": conditions})
            outputs = finalize_feedback(root)
            summary = json.loads(outputs["prompt_condition_feedback_summary"].read_text(encoding="utf-8"))
            overlays = [json.loads(line) for line in outputs["prompt_condition_human_label_overlays"].read_text(encoding="utf-8").splitlines()]
            exclusions = [json.loads(line) for line in outputs["prompt_condition_technical_exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["condition_supervision_count"], 5)
        self.assertTrue(summary["not_judgable_is_not_training_data"])
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["reason"], "all_prompt_conditions_not_judgable")
        self.assertEqual(len(overlays), 5)
        self.assertTrue(all(row["training_eligibility"]["positive_generation_supervision"] for row in overlays))

    def test_builds_single_variation_condition_review_without_promoting_it_to_training(self) -> None:
        variation = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_variation_r007_blue_fast_multi_material")
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_variation_review_batch(variation, Path(temporary) / "review", "variation_condition_test")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            draft = json.loads(paths["ai_drafts"].read_text(encoding="utf-8").strip())

        self.assertEqual(batch["selected_count"], 1)
        self.assertEqual(batch["records"][0]["review_subject"], "prompt_variation")
        self.assertTrue(batch["records"][0]["frames"])
        self.assertEqual(draft["status"], "ai_draft_not_human_label")
        self.assertEqual(draft["suggested_conditions"]["主色"], "部分符合")


if __name__ == "__main__":
    unittest.main()
