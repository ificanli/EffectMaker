from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_human_review import build_composition_review_batch, build_review_batch, finalize_composition_feedback, finalize_feedback, generate_ai_drafts, migrate_feedback, save_feedback
from workspace.tools.vfx_web_training_review import build_asset_map, build_catalog_manifest


class PrefabHumanReviewTests(unittest.TestCase):
    def test_builds_stratified_pending_batch_and_validates_feedback(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        run = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(dataset, run, root, "test_prefab_review")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            store = json.loads(paths["feedback_store"].read_text(encoding="utf-8"))

            self.assertEqual(batch["selected_count"], 259)
            self.assertEqual(batch["review_route_counts"], {"主体过小": 37, "可评价": 22, "当前无有效输出": 57, "需要上下文": 143})
            self.assertEqual(store["records"], {})
            self.assertTrue(all(row["feedback_status"] == "pending" for row in batch["records"]))
            self.assertTrue(any(row["auto_eval"]["status"] == "pass" for row in batch["records"]))
            self.assertIn("fire", {row["effect_family_hint"] for row in batch["records"]})
            self.assertIn("shield", {row["effect_family_hint"] for row in batch["records"]})
            self.assertEqual(sum(bool(row["frames"]) for row in batch["records"]), 59)
            drafts_path = generate_ai_drafts(root)
            drafts = [json.loads(line) for line in drafts_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(drafts), 259)
            self.assertTrue(all(row["status"] == "ai_draft_not_human_label" for row in drafts))
            self.assertEqual(sum(row["evidence"]["rendered"] for row in drafts), 59)
            self.assertEqual(sum(row["suggested_feedback"]["decision"] == "not_visible" for row in drafts), 237)
            rendered = next(row for row in batch["records"] if row["frames"])
            self.assertAlmostEqual(rendered["frames"][1]["time_seconds"], 0.1, places=4)
            self.assertNotEqual(rendered["frames"][1]["time_seconds"], 1)

            candidate = batch["records"][0]["candidate_id"]
            saved = save_feedback(
                root,
                {
                    "candidate_id": candidate,
                    "decision": "partial",
                    "style_family": "stylized",
                    "style_keywords": ["粒子感"],
                    "quality_score": 3,
                    "scores": {
                        "core_readability": 3,
                        "layer_separation": 2,
                        "rhythm": 4,
                        "material": 3,
                        "composition": 2,
                    },
                    "layer_roles": {"core": "一般", "support": "没有", "hit": "没有", "residual": "没有"},
                    "reusable_layers": ["主体"],
                    "issues": ["无明显问题"],
                    "summary": "部分可复用",
                    "ai_draft_changed": True,
                    "notes": "主体闪烁节奏自然。",
                },
            )
            self.assertEqual(saved["candidate_id"], candidate)
            self.assertEqual(saved["confirmation_mode"], "human_corrected_ai_draft")
            self.assertNotIn("ai_draft_changed", saved)
            self.assertEqual(saved["notes"], "主体闪烁节奏自然。")
            self.assertEqual(len(paths["feedback"].read_text(encoding="utf-8").splitlines()), 1)
            self.assertEqual(json.loads(paths["feedback_store"].read_text(encoding="utf-8"))["records"][candidate]["decision"], "partial")
            with self.assertRaisesRegex(ValueError, "human review is incomplete"):
                finalize_feedback(root)

    def test_rejects_incomplete_feedback(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        run = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(dataset, run, root, "test_prefab_review")
            candidate = json.loads(paths["review_batch"].read_text(encoding="utf-8"))["records"][0]["candidate_id"]
            with self.assertRaisesRegex(ValueError, "feedback schema error"):
                save_feedback(root, {"candidate_id": candidate})

    def test_attaches_only_verified_webgl_catalog_entries(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        run = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            asset_map = root / "webgl_asset_map.json"
            asset_map.write_text(json.dumps(build_asset_map(run / "run_manifest.json"), ensure_ascii=False), encoding="utf-8")
            catalog = root / "webgl_catalog.json"
            catalog.write_text(json.dumps(
                build_catalog_manifest(asset_map, Path("UnityDemo/EffectDemo"), "http://127.0.0.1:8775/", dataset),
                ensure_ascii=False,
            ), encoding="utf-8")
            paths = build_review_batch(dataset, run, root / "review", "test_webgl_review", webgl_catalog_path=catalog)
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            statuses = {row["candidate_id"]: row["webgl_preview"]["status"] for row in batch["records"]}
            self.assertEqual(batch["webgl_status_counts"]["webgl_ready"], 59)
            self.assertEqual(sum(status == "webgl_ready" for status in statuses.values()), 59)
            self.assertEqual(statuses["trains_fx_024_fx_conecold"], "webgl_ready")
            self.assertIn("needs_context", set(statuses.values()))

    def test_finalizes_complete_feedback_into_overlays_and_summary(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        run = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(dataset, run, root, "complete_review", 2)
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            for index, row in enumerate(batch["records"], start=1):
                save_feedback(root, {
                    "candidate_id": row["candidate_id"], "decision": "partial",
                    "style_family": "stylized", "style_keywords": ["粒子感"], "quality_score": index + 2,
                    "scores": {"core_readability": 3, "layer_separation": 2, "rhythm": 4, "material": 3, "composition": 2},
                    "layer_roles": {"core": "一般", "support": "没有", "hit": "没有", "residual": "没有"},
                    "reusable_layers": ["主体"], "issues": ["无明显问题"], "summary": "部分可复用",
                })
            outputs = finalize_feedback(root)
            summary = json.loads(outputs["feedback_summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["review_count"], 2)
            self.assertEqual(summary["decision_counts"], {"partial": 2})
            self.assertEqual(len(outputs["human_label_overlays"].read_text(encoding="utf-8").splitlines()), 2)

    def test_not_visible_feedback_is_excluded_from_training_overlays(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        run = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(dataset, run, root, "not_visible_review", 2)
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            for index, row in enumerate(batch["records"]):
                save_feedback(root, {
                    "candidate_id": row["candidate_id"],
                    "decision": "partial" if index == 0 else "not_visible",
                    "style_family": "stylized" if index == 0 else "unknown",
                    "style_keywords": ["粒子感"] if index == 0 else [],
                    "quality_score": 3 if index == 0 else 1,
                    "scores": {"core_readability": 3 if index == 0 else 0, "layer_separation": 2, "rhythm": 2, "material": 3, "composition": 2 if index == 0 else 0},
                    "layer_roles": {"core": "一般" if index == 0 else "没有", "support": "没有", "hit": "没有", "residual": "没有"},
                    "reusable_layers": ["主体"] if index == 0 else ["无"],
                    "issues": ["无明显问题"] if index == 0 else ["主体不清楚"],
                    "summary": "部分可复用" if index == 0 else "无法判断",
                })
            outputs = finalize_feedback(root)
            summary = json.loads(outputs["feedback_summary"].read_text(encoding="utf-8"))
            overlays = [json.loads(line) for line in outputs["human_label_overlays"].read_text(encoding="utf-8").splitlines()]
            exclusions = [json.loads(line) for line in outputs["technical_exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["trainable_human_label_count"], 1)
        self.assertTrue(summary["not_visible_is_not_training_data"])
        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0]["human_label"]["decision"], "partial")
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["exclusion_reason"], "human_not_visible_no_training_label")

    def test_builds_a_separate_review_batch_for_actual_compositions(self) -> None:
        composition = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_composed_r005_human_bound")
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_composition_review_batch(composition, Path(temporary) / "review", "composition_review")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            drafts = [json.loads(line) for line in generate_ai_drafts(Path(temporary) / "review").read_text(encoding="utf-8").splitlines()]

        self.assertEqual(batch["review_subject"], "prompt_composition")
        self.assertEqual(batch["selected_count"], 6)
        self.assertEqual(batch["review_route_counts"], {"可评价": 6})
        self.assertTrue(all(row["review_subject_cn"] == "组合候选（本次运行结果）" for row in batch["records"]))
        self.assertTrue(all("仅用于检索，不代表本次组合结论" in row["source_label_note"] for row in batch["records"]))
        self.assertTrue(all(row["frames"] for row in batch["records"]))
        self.assertEqual(len(drafts), 6)
        self.assertTrue(all(row["status"] == "ai_draft_not_human_label" for row in drafts))

    def test_finalizes_composition_feedback_without_promoting_unscored_prompt_conditions(self) -> None:
        composition = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_composed_r005_human_bound")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_composition_review_batch(composition, root, "composition_finalize")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            for index, row in enumerate(batch["records"]):
                not_visible = index == 0
                save_feedback(root, {
                    "candidate_id": row["candidate_id"],
                    "decision": "not_visible" if not_visible else "partial",
                    "style_family": "unknown" if not_visible else "stylized",
                    "style_keywords": [] if not_visible else ["粒子感"],
                    "quality_score": 1 if not_visible else 3,
                    "scores": {"core_readability": 0 if not_visible else 3, "layer_separation": 0 if not_visible else 3, "rhythm": 0 if not_visible else 3, "material": 0 if not_visible else 3, "composition": 0 if not_visible else 3},
                    "layer_roles": {"core": "没有" if not_visible else "一般", "support": "没有", "hit": "没有", "residual": "没有"},
                    "reusable_layers": ["无"] if not_visible else ["粒子参数"],
                    "issues": ["主体不清楚"] if not_visible else ["无明显问题"],
                    "summary": "无法判断" if not_visible else "部分可复用",
                })
            outputs = finalize_composition_feedback(root)
            summary = json.loads(outputs["composition_feedback_summary"].read_text(encoding="utf-8"))
            overlays = [json.loads(line) for line in outputs["composition_human_label_overlays"].read_text(encoding="utf-8").splitlines()]
            exclusions = [json.loads(line) for line in outputs["composition_technical_exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["trainable_human_label_count"], 5)
        self.assertTrue(summary["not_visible_is_not_training_data"])
        self.assertTrue(summary["prompt_conditions_are_not_inferred"])
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(len(overlays), 5)
        self.assertTrue(all(not row["training_eligibility"]["prompt_condition_supervision"] for row in overlays))
        self.assertTrue(all(not row["training_eligibility"]["positive_generation_supervision"] for row in overlays))

    def test_technical_exclusion_requires_no_visual_evidence(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        run = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(dataset, run, root, "technical_exclusion_review", 2)
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            technical = batch["records"][1]
            technical["review_route"] = "需要上下文"
            technical["frames"] = []
            technical["webgl_preview"] = {"status": "needs_context"}
            paths["review_batch"].write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            save_feedback(root, {
                "candidate_id": batch["records"][0]["candidate_id"], "decision": "partial", "style_family": "stylized", "style_keywords": ["粒子感"], "quality_score": 3,
                "scores": {"core_readability": 3, "layer_separation": 2, "rhythm": 4, "material": 3, "composition": 2},
                "layer_roles": {"core": "一般", "support": "没有", "hit": "没有", "residual": "没有"},
                "reusable_layers": ["主体"], "issues": ["无明显问题"], "summary": "部分可复用",
            })
            outputs = finalize_feedback(root, allow_technical_exclusions=True)
            summary = json.loads(outputs["feedback_summary"].read_text(encoding="utf-8"))
            exclusions = [json.loads(line) for line in outputs["technical_exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["completion_mode"], "human_plus_technical_exclusions")
        self.assertEqual(summary["trainable_human_label_count"], 1)
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["exclusion_reason"], "no_independent_visual_evidence")

    def test_migrates_human_feedback_and_rebuilds_trace(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002")
        run = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r002")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"; destination = root / "destination"
            source_paths = build_review_batch(dataset, run, source, "source_review", 2)
            destination_paths = build_review_batch(dataset, run, destination, "destination_review", 2)
            source_batch = json.loads(source_paths["review_batch"].read_text(encoding="utf-8"))
            candidate_id = source_batch["records"][0]["candidate_id"]
            original = save_feedback(source, {
                "candidate_id": candidate_id, "decision": "partial", "style_family": "stylized", "style_keywords": ["粒子感"], "quality_score": 3,
                "scores": {"core_readability": 3, "layer_separation": 2, "rhythm": 4, "material": 3, "composition": 2},
                "layer_roles": {"core": "一般", "support": "没有", "hit": "没有", "residual": "没有"},
                "reusable_layers": ["主体"], "issues": ["无明显问题"], "summary": "部分可复用", "ai_draft_changed": True, "notes": "保留主体节奏。",
            })
            migration_path = migrate_feedback(source, destination)
            migration = json.loads(migration_path.read_text(encoding="utf-8"))
            migrated = json.loads(destination_paths["feedback_store"].read_text(encoding="utf-8"))["records"][candidate_id]
            self.assertEqual(migration["migrated_candidate_ids"], [candidate_id])
            self.assertEqual(migrated["batch_id"], "destination_review")
            self.assertEqual(migrated["reviewed_at"], original["reviewed_at"])
            self.assertEqual(migrated["confirmation_mode"], "human_corrected_ai_draft")
            self.assertEqual(migrated["notes"], "保留主体节奏。")
            self.assertNotIn("ai_draft_changed", migrated)


if __name__ == "__main__":
    unittest.main()
