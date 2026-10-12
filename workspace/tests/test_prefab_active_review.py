from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from workspace.tools.vfx_generation import prefab_active_review as review_page
from workspace.tools.vfx_generation.prefab_active_review import add_custom_semantic_option, build_review_batch, carry_compatible_feedback, finalize_feedback, save_feedback


class PrefabActiveReviewTests(unittest.TestCase):
    active_root = Path("workspace/data/vfx_generation/active_learning/prefab_active_r004")
    webgl_catalog = Path("workspace/data/vfx_generation/runs/trains_prefab_playmode_r005_audit_r3_short_window/webgl_catalog_r005c.json")

    def test_builds_capture_v2_chinese_one_click_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_review_batch(self.active_root, Path(temporary) / "review", "test_active", self.webgl_catalog)
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))

        self.assertEqual(batch["record_count"], 1)
        self.assertEqual(batch["records"][0]["capture_pipeline_version"], "play_mode_runtime_isolated_multiview.v2")
        self.assertEqual(len(batch["records"][0]["frames"]), 9)
        self.assertGreaterEqual(batch["records"][0]["peak_frame_index"], 0)
        self.assertEqual(len(batch["allowed_actions"]), 11)
        self.assertIn("AI判断正确", batch["allowed_actions"])
        self.assertIn("无法判断", batch["allowed_actions"])
        self.assertIn("雷电", batch["records"][0]["ai_effect_elements_cn"])
        self.assertIsNotNone(batch["records"][0]["webgl_preview"])
        self.assertTrue(batch["records"][0]["webgl_preview"]["player_url"].startswith("http://"))

    def test_human_correction_preserves_ai_draft_and_becomes_human_gold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.active_root, root, "test_active_gold")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            sample_id = batch["records"][0]["sample_id"]
            first = save_feedback(root, {"sample_id": sample_id, "action": "AI判断正确", "notes": "第一版确认"})
            latest = save_feedback(root, {"sample_id": sample_id, "action": "主体不清楚", "notes": "以第二版为准"})
            store = json.loads(paths["feedback_store"].read_text(encoding="utf-8"))
            outputs = finalize_feedback(root)
            gold = [json.loads(line) for line in outputs["human_gold"].read_text(encoding="utf-8").splitlines()]
            exclusions = outputs["exclusions"].read_text(encoding="utf-8").splitlines()

        self.assertEqual(first["confirmation_mode"], "human_accepted_ai_draft")
        self.assertEqual(latest["confirmation_mode"], "human_corrected_ai_draft")
        self.assertEqual(len(store["records"][sample_id]["revisions"]), 2)
        self.assertEqual(store["records"][sample_id]["latest"]["notes"], "以第二版为准")
        self.assertEqual(len(gold), 1)
        self.assertEqual(exclusions, [])
        self.assertEqual(gold[0]["tier"], "human_gold")
        self.assertEqual(gold[0]["label_provenance"]["label_source"], "human")
        self.assertEqual(gold[0]["observations"]["ai_draft"], latest["ai_draft"])
        self.assertIn("主体不清楚", gold[0]["labels"]["issues"])
        self.assertIn("core_readability_issue_detection", gold[0]["training"]["eligible_tasks"])
        self.assertIn("regression_evaluation", gold[0]["training"]["excluded_tasks"])

    def test_unable_actions_only_create_exclusions(self) -> None:
        for action, expected_reason in (("无法播放", "human_unable_to_play"), ("无法判断", "human_unable_to_judge")):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "review"
                paths = build_review_batch(self.active_root, root, f"test_{action}")
                batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
                sample_id = batch["records"][0]["sample_id"]
                saved = save_feedback(root, {"sample_id": sample_id, "action": action})
                outputs = finalize_feedback(root)
                gold = outputs["human_gold"].read_text(encoding="utf-8").splitlines()
                exclusions = [json.loads(line) for line in outputs["exclusions"].read_text(encoding="utf-8").splitlines()]

            self.assertFalse(saved["result"]["trainable"])
            self.assertEqual(saved["confirmation_mode"], "human_exclusion")
            self.assertEqual(gold, [])
            self.assertEqual(len(exclusions), 1)
            self.assertEqual(exclusions[0]["reason"], expected_reason)
            self.assertIn("human_gold", exclusions[0]["excluded_from"])

    def test_rejects_non_option_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.active_root, root, "test_invalid")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "unsupported active review action"):
                save_feedback(root, {"sample_id": batch["records"][0]["sample_id"], "action": "随便写一个结论"})

    def test_multiple_feedback_actions_are_saved_as_one_confirmed_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.active_root, root, "test_multi_action")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            saved = save_feedback(root, {"sample_id": batch["records"][0]["sample_id"], "actions": ["材质有问题", "应该更差"], "notes": "同时记录质量方向和材质问题"})
        self.assertEqual(saved["action"], "应该更差")
        self.assertEqual(saved["selected_actions"], ["应该更差", "材质有问题"])
        self.assertEqual(saved["confirmation_mode"], "human_corrected_ai_draft")
        self.assertEqual(saved["result"]["labels"]["decisions"], ["应该更差", "材质有问题"])
        self.assertIn("材质有问题", saved["result"]["labels"]["issues"])
        self.assertIn("quality_direction_supervision", saved["result"]["eligible_tasks"])
        self.assertIn("material_issue_detection", saved["result"]["eligible_tasks"])

    def test_exclusion_action_cannot_mix_with_other_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.active_root, root, "test_action_conflict")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "无法播放和无法判断不能与其他选项同时选择"):
                save_feedback(root, {"sample_id": batch["records"][0]["sample_id"], "actions": ["无法判断", "材质有问题"]})

    def test_review_page_exposes_multiselect_and_explicit_confirmation(self) -> None:
        source = review_page.HTML
        self.assertIn("selected_actions", source)
        self.assertIn("pendingActions", source)
        self.assertIn("pendingNotes", source)
        self.assertIn("pendingNotesDirty", source)
        self.assertIn("selectedNotes()", source)
        self.assertIn("aria-pressed", source)
        self.assertIn("确认本条", source)
        self.assertIn("confirmSelection", source)

    def test_semantic_review_collects_elements_type_and_playability_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "semantic-review"
            paths = build_review_batch(self.active_root, root, "test_semantic", review_mode="semantic_function_only")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            source = batch["records"][0]
            selected_type = "explosion" if source["ai_effect_type"] != "explosion" else "slash"
            feedback = save_feedback(root, {"sample_id": source["sample_id"], "effect_elements": ["fire", "lightning"], "effect_type": selected_type, "notes": "元素和类型分别判断"})
        self.assertEqual(batch["review_mode"], "semantic_function_only")
        self.assertEqual(batch["semantic_schema_version"], "effect_element_and_type.v2")
        self.assertEqual(batch["allowed_actions"], ["AI判断正确", "特效元素错误", "特效类型错误", "无法播放", "无法判断"])
        self.assertEqual(feedback["review_scope"], "semantic_function_only")
        self.assertEqual(feedback["semantic_selection"]["selected_effect_elements"], ["fire", "lightning"])
        self.assertEqual(feedback["semantic_selection"]["selected_effect_type"], selected_type)
        self.assertEqual(feedback["result"]["labels"]["observed_element_tags"], ["fire", "lightning"])
        self.assertEqual(feedback["result"]["labels"]["effect_type"], selected_type)
        self.assertEqual(feedback["result"]["labels"]["target_effect_family"], selected_type)
        self.assertEqual(feedback["result"]["labels"]["scores"], {})
        self.assertIsNone(feedback["result"]["labels"]["quality_score"])
        self.assertEqual(feedback["result"]["eligible_tasks"], ["effect_element_supervision", "effect_type_supervision", "pseudo_label_calibration"])
        self.assertIn("特效元素错误", feedback["selected_actions"])

    def test_semantic_review_page_has_no_aesthetic_feedback_controls(self) -> None:
        source = review_page.SEMANTIC_HTML
        self.assertIn("特效元素（可多选）", source)
        self.assertIn("特效类型（主要表现形态）", source)
        self.assertIn("新增元素", source)
        self.assertIn("新增类型", source)
        self.assertIn("/api/semantic-options", source)
        self.assertIn("无法判断", source)
        self.assertIn("专业资料教师训练中", source)
        self.assertNotIn('id="actions"', source)
        self.assertNotIn("主体不清楚", source)
        self.assertNotIn("层次有问题", source)
        self.assertNotIn("节奏有问题", source)
        self.assertNotIn("材质有问题", source)

    def test_custom_semantic_type_persists_and_becomes_human_function_label(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "semantic-review"
            paths = build_review_batch(self.active_root, root, "test_custom_semantic", review_mode="semantic_function_only")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            source = batch["records"][0]
            custom_element = add_custom_semantic_option(root, "星光", "effect_element")
            created = add_custom_semantic_option(root, "烟花", "effect_type")
            duplicate = add_custom_semantic_option(root, " 烟花 ", "effect_type")
            feedback = save_feedback(root, {"sample_id": source["sample_id"], "effect_elements": [custom_element["option"]["value"]], "effect_type": created["option"]["value"], "notes": "自定义元素和类型"})
            option_store = json.loads(paths["semantic_options"].read_text(encoding="utf-8"))

        self.assertTrue(created["created"])
        self.assertFalse(duplicate["created"])
        self.assertEqual(len(option_store["options"]), 2)
        self.assertEqual(feedback["semantic_selection"]["selected_effect_elements_cn"], ["星光"])
        self.assertEqual(feedback["semantic_selection"]["selected_effect_type_cn"], "烟花")
        self.assertEqual(feedback["correction"]["label_delta"]["selected_effect_type_cn"], "烟花")
        self.assertEqual(feedback["result"]["labels"]["observed_element_tags"], [custom_element["option"]["value"]])
        self.assertEqual(feedback["result"]["labels"]["effect_type"], created["option"]["value"])
        self.assertEqual(feedback["result"]["eligible_tasks"], ["effect_element_supervision", "effect_type_supervision", "pseudo_label_calibration"])

    def test_capture_manifest_override_replaces_bad_framing_for_matching_prefab(self) -> None:
        source_active_root = Path("workspace/data/vfx_generation/active_learning/prefab_active_full_r001")
        target = "Assets/Hovl Studio/Sword slash VFX/Prefabs/Sword Slash 1.prefab"
        replacement = Path("workspace/data/vfx_generation/captures/sword_slash_framing_r001/cases/full_prefab_0001_5b7d7f902fb3/capture_manifest.json")
        with tempfile.TemporaryDirectory() as temporary:
            active_root = Path(temporary) / "active"
            active_root.mkdir(parents=True)
            active = json.loads((source_active_root / "active_learning_batch.json").read_text(encoding="utf-8"))
            active["items"] = [row for row in active["items"] if row["prefab_path"] == target]
            active["review_budget"] = 1
            active["eligible_count"] = max(1, int(active.get("eligible_count") or 1))
            (active_root / "active_learning_batch.json").write_text(json.dumps(active, ensure_ascii=False), encoding="utf-8")
            paths = build_review_batch(active_root, Path(temporary) / "review", "test_framing_override", capture_manifest_overrides={target: replacement})
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
        record = next(row for row in batch["records"] if row["prefab_path"] == target)
        self.assertIn("sword_slash_framing_r001", record["capture_manifest_path"])
        self.assertEqual(record["peak_frame_index"], 21)

    def test_concurrent_feedback_saves_keep_store_json_valid_and_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.active_root, root, "test_concurrent_feedback")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            sample_id = batch["records"][0]["sample_id"]
            payloads = [
                {"sample_id": sample_id, "action": "无法判断"},
                {"sample_id": sample_id, "action": "无法播放"},
            ]
            with ThreadPoolExecutor(max_workers=2) as executor:
                list(executor.map(lambda payload: save_feedback(root, payload), payloads))
            store = json.loads(paths["feedback_store"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["feedback"].read_text(encoding="utf-8").splitlines() if line.strip()]
        entry = store["records"][sample_id]
        self.assertEqual(len(entry["revisions"]), 2)
        self.assertIn(entry["latest"]["action"], {"无法判断", "无法播放"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], entry["latest"]["record_id"])

    def test_rebuild_carries_only_feedback_with_matching_capture_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first_root = Path(temporary) / "review-r1"
            first_paths = build_review_batch(self.active_root, first_root, "test_carry_r1", review_mode="semantic_function_only")
            first_batch = json.loads(first_paths["review_batch"].read_text(encoding="utf-8"))
            sample = first_batch["records"][0]
            custom = add_custom_semantic_option(first_root, "烟花", "effect_type")
            original = save_feedback(first_root, {"sample_id": sample["sample_id"], "effect_elements": sample["ai_effect_elements"], "effect_type": custom["option"]["value"], "notes": "保留这条判断"})

            second_root = Path(temporary) / "review-r2"
            second_paths = build_review_batch(
                self.active_root,
                second_root,
                "test_carry_r2",
                review_mode="semantic_function_only",
                carry_feedback_root=first_root,
            )
            second_store = json.loads(second_paths["feedback_store"].read_text(encoding="utf-8"))
            carry = json.loads(second_paths["feedback_carry_manifest"].read_text(encoding="utf-8"))
            second_options = json.loads(second_paths["semantic_options"].read_text(encoding="utf-8"))

        migrated = second_store["records"][sample["sample_id"]]["latest"]
        self.assertEqual(carry["carried_count"], 1)
        self.assertEqual(carry["skipped_count"], 0)
        self.assertEqual(migrated["record_id"], original["record_id"])
        self.assertEqual(migrated["reviewed_at"], original["reviewed_at"])
        self.assertEqual(migrated["batch_id"], "test_carry_r2")
        self.assertEqual(carry["carried_custom_semantic_option_count"], 1)
        self.assertEqual(second_options["options"], [custom["option"]])

    def test_hit_alias_normalizes_to_canonical_impact_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "review"
            paths = build_review_batch(self.active_root, root, "test_impact_alias", review_mode="semantic_function_only")
            batch = json.loads(paths["review_batch"].read_text(encoding="utf-8"))
            source = batch["records"][0]
            self.assertNotIn("hit", [option["value"] for option in source["effect_type_options"]])
            self.assertIn({"value": "impact", "label": "命中/爆点"}, source["effect_type_options"])
            feedback = save_feedback(root, {"sample_id": source["sample_id"], "effect_elements": source["ai_effect_elements"], "effect_type": "impact"})

        self.assertEqual(feedback["semantic_selection"]["selected_effect_type"], "impact")
        self.assertEqual(feedback["semantic_selection"]["selected_effect_type_cn"], "命中/爆点")

    def test_legacy_hit_feedback_is_normalized_during_batch_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary) / "source"
            source_paths = build_review_batch(self.active_root, source_root, "test_legacy_hit_source", review_mode="semantic_function_only")
            source_batch = json.loads(source_paths["review_batch"].read_text(encoding="utf-8"))
            source = source_batch["records"][0]
            feedback = save_feedback(source_root, {"sample_id": source["sample_id"], "effect_elements": source["ai_effect_elements"], "effect_type": "impact"})
            feedback["semantic_selection"]["ai_effect_type"] = "hit"
            feedback["semantic_selection"]["selected_effect_type"] = "hit"
            feedback["semantic_selection"]["selected_effect_type_cn"] = "命中/受击"
            feedback["selected_actions"] = ["特效类型错误"]
            feedback["action"] = "特效类型错误"
            feedback["confirmation_mode"] = "human_corrected_ai_draft"
            feedback["correction"]["action"] = "特效类型错误"
            feedback["correction"]["label_delta"]["ai_effect_type"] = "hit"
            feedback["correction"]["label_delta"]["selected_effect_type"] = "hit"
            feedback["correction"]["label_delta"]["selected_effect_type_cn"] = "命中/受击"
            feedback["result"]["labels"]["effect_type"] = "hit"
            feedback["result"]["labels"]["target_effect_family"] = "hit"
            feedback["result"]["labels"]["decision"] = "特效类型错误"
            feedback["result"]["labels"]["decisions"] = ["特效类型错误"]
            feedback["result"]["labels"]["issues"] = ["特效类型错误"]
            source_store = json.loads(source_paths["feedback_store"].read_text(encoding="utf-8"))
            source_store["records"][source["sample_id"]]["latest"] = feedback
            source_store["records"][source["sample_id"]]["revisions"] = [feedback]
            source_paths["feedback_store"].write_text(json.dumps(source_store, ensure_ascii=False), encoding="utf-8")

            target_root = Path(temporary) / "target"
            target_paths = build_review_batch(self.active_root, target_root, "test_legacy_hit_target", review_mode="semantic_function_only")
            carry_compatible_feedback(source_root, target_root)
            target_store = json.loads(target_paths["feedback_store"].read_text(encoding="utf-8"))

        normalized = target_store["records"][source["sample_id"]]["latest"]
        self.assertEqual(normalized["semantic_selection"]["ai_effect_type"], "impact")
        self.assertEqual(normalized["semantic_selection"]["selected_effect_type"], "impact")
        self.assertEqual(normalized["semantic_selection"]["selected_effect_type_cn"], "命中/爆点")
        self.assertEqual(normalized["action"], "AI判断正确")
        self.assertEqual(normalized["selected_actions"], ["AI判断正确"])
        self.assertEqual(normalized["result"]["labels"]["effect_type"], "impact")

    def test_legacy_single_dimension_feedback_is_not_carried_into_split_semantics(self) -> None:
        source_root = Path("workspace/data/vfx_generation/reviews/prefab_active_review_full_r009")
        if not source_root.is_dir():
            self.skipTest("historical r009 review batch is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            target_root = Path(temporary) / "review-r2"
            paths = build_review_batch(
                Path("workspace/data/vfx_generation/active_learning/prefab_active_full_r005"),
                target_root,
                "test_semantic_schema_upgrade",
                review_mode="semantic_function_only",
                carry_feedback_root=source_root,
            )
            carry = json.loads(paths["feedback_carry_manifest"].read_text(encoding="utf-8"))
            store = json.loads(paths["feedback_store"].read_text(encoding="utf-8"))

        self.assertEqual(carry["carried_count"], 0)
        self.assertGreater(carry["skipped_count"], 0)
        self.assertTrue(all(row["reason"] in {"sample_not_in_target_batch", "semantic_schema_changed"} for row in carry["skipped"]))
        self.assertEqual(store["records"], {})


if __name__ == "__main__":
    unittest.main()
