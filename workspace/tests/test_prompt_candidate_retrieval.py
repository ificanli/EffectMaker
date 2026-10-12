from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prompt_candidate_retrieval import build_retrieval_run, parse_prompt


class PromptCandidateRetrievalTests(unittest.TestCase):
    def test_parses_chinese_prompt_and_builds_unlabeled_retrieval_baseline(self) -> None:
        prompt = parse_prompt("卡通蓝色能量冲击，快速爆发，不要长拖尾", "prompt_test", 6, 42)
        self.assertEqual(prompt["style_family"], "cartoon")
        self.assertEqual(prompt["color_keywords"], ["blue"])
        self.assertIn("impact", prompt["motion_keywords"])
        self.assertEqual(prompt["timing_profile"], "fast_impact")
        self.assertTrue(prompt["negative_constraints"])

        with tempfile.TemporaryDirectory() as temporary:
            paths = build_retrieval_run(
                prompt,
                Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002"),
                Path("workspace/data/vfx_generation/datasets/material_trajectory_r002_training_r001"),
                Path(temporary) / "run",
                "retrieval_test",
            )
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            self.assertEqual(manifest["candidate_count"], 6)
            self.assertEqual(manifest["human_aesthetic_labels_used"], 0)
            self.assertEqual(manifest["status"], "retrieval_baseline")
            self.assertTrue(paths["contact_sheet"].is_file())
            self.assertTrue(all(row["execution_status"] == "retrieval_proposal_not_yet_composed" for row in manifest["candidates"]))
            self.assertTrue(all("style_requires_human_labels" in row["unmatched_conditions"] for row in manifest["candidates"]))
            self.assertTrue(all("/specs/" in row["material_trajectory"]["spec_path"] for row in manifest["candidates"]))

    def test_uses_only_trainable_human_overlays_for_style_conditioning(self) -> None:
        prompt = parse_prompt("卡通蓝色能量冲击，快速爆发，不要长拖尾", "prompt_human", 6, 42)
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        material = Path("workspace/data/vfx_generation/datasets/material_trajectory_r002_training_r001")
        prefab_rows = [json.loads(line) for line in (dataset / "image_feature_examples.jsonl").read_text(encoding="utf-8").splitlines()]
        material_paths = {
            row["inputs"]["material_selection"]["materials"][0]["material_path"]
            for row in (json.loads(line) for line in (material / "material_state_examples.jsonl").read_text(encoding="utf-8").splitlines())
            if row["split"]["name"] == "train" and row["label"]["trajectory_label"] == "positive"
        }
        first_prefab = next(
            row for row in prefab_rows
            if material_paths.intersection({material["material_path"] for material in row["inputs"]["material_selection"]["materials"]})
        )
        overlay = {
            "schema_version": "prefab_human_label_overlay.v1",
            "batch_id": "test_human_batch",
            "candidate_id": first_prefab["candidate_id"],
            "reviewed_at": "2026-08-31T00:00:00+00:00",
            "human_label": {
                "decision": "accept_reference",
                "style_family": "cartoon",
                "quality_score": 5,
                "confirmation_mode": "human_corrected_ai_draft",
            },
            "trace": {},
            "training_eligibility": {
                "quality_supervision": True,
                "style_conditioned_supervision": True,
                "preference_training": False,
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            overlays = root / "human_label_overlays.jsonl"
            overlays.write_text(json.dumps(overlay, ensure_ascii=False) + "\n", encoding="utf-8")
            paths = build_retrieval_run(prompt, dataset, material, root / "run", "retrieval_human", overlays)
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "retrieval_human_label_assisted")
        self.assertEqual(manifest["human_aesthetic_labels_used"], 1)
        self.assertGreaterEqual(manifest["human_aesthetic_labels_selected"], 1)
        selected = [row for row in manifest["candidates"] if row["human_label_context"] is not None]
        self.assertTrue(selected)
        self.assertTrue(all("style_requires_human_labels" not in row["unmatched_conditions"] for row in selected))

    def test_retrieval_only_uses_prefab_bound_trajectory_materials(self) -> None:
        prompt = parse_prompt("卡通蓝色能量冲击，快速爆发，不要长拖尾", "prompt_bound", 6, 42)
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        material = Path("workspace/data/vfx_generation/datasets/material_trajectory_r002_training_r001")
        prefab_rows = {
            row["candidate_id"]: row
            for row in (json.loads(line) for line in (dataset / "image_feature_examples.jsonl").read_text(encoding="utf-8").splitlines())
        }
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_retrieval_run(prompt, dataset, material, Path(temporary) / "run", "retrieval_bound")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

        for candidate in manifest["candidates"]:
            prefab = prefab_rows[candidate["source_prefab"]["case_id"]]
            bound_materials = {material["material_path"] for material in prefab["inputs"]["material_selection"]["materials"]}
            self.assertEqual(candidate["material_trajectory"]["binding_status"], "direct_prefab_renderer_material")
            self.assertTrue(set(candidate["material_trajectory"]["material_paths"]).intersection(bound_materials))
            self.assertIn("direct_prefab_material_binding", candidate["selection_reasons"])

    def test_rejects_not_visible_overlay(self) -> None:
        prompt = parse_prompt("卡通蓝色能量冲击", "prompt_invalid", 4, 42)
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        material = Path("workspace/data/vfx_generation/datasets/material_trajectory_r002_training_r001")
        first_prefab = json.loads((dataset / "image_feature_examples.jsonl").read_text(encoding="utf-8").splitlines()[0])
        overlay = {
            "candidate_id": first_prefab["candidate_id"],
            "human_label": {"decision": "not_visible"},
            "training_eligibility": {"quality_supervision": True},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            overlays = root / "invalid_overlays.jsonl"
            overlays.write_text(json.dumps(overlay) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not_visible label must not be supplied"):
                build_retrieval_run(prompt, dataset, material, root / "run", "retrieval_invalid", overlays)


if __name__ == "__main__":
    unittest.main()
