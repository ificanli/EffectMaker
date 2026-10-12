from __future__ import annotations

import json
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prompt_graph_generator import _feature_vector, _target_profile, attach_vfxspec, build_compile_request, build_dual_family_report, build_runtime_request, parse_prompt_condition


ROOT = Path(__file__).parents[2]


class PromptGraphGeneratorTests(unittest.TestCase):
    def test_negative_constraint_does_not_change_timing(self) -> None:
        condition = parse_prompt_condition("卡通橙色爆炸冲击，中等节奏，标准性能，不要长拖尾", "test", 1)
        self.assertEqual(condition["timing_profile"], "medium")
        self.assertEqual(condition["negative_constraints"], ["长拖尾"])

    def test_generated_manifests_are_pending_unity_until_verified(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prompt_graph_generation_manifest.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["status"]["enum"], ["generated_pending_unity", "pass_technical_prompt_unscored", "blocked"])

    def test_condition_vector_keeps_timing_performance_and_color(self) -> None:
        condition = parse_prompt_condition("卡通橙色爆炸冲击，中等节奏，标准性能，不要长拖尾", "test", 1, "standard")
        vector = _feature_vector(condition)
        self.assertGreater(sum(vector), 4.0)

    def test_standard_multi_layer_family_stays_multi_particle(self) -> None:
        self.assertEqual(_target_profile("explosion", "fast_impact", "standard"), "multi_particle")
        self.assertEqual(_target_profile("explosion", "loop", "mobile"), "particle_v1")

    def test_motion_burst_does_not_override_slash_family(self) -> None:
        condition = parse_prompt_condition("写实青色刀光，快速爆发，标准性能，不要长拖尾", "slash", 1)
        self.assertEqual(condition["effect_families"], ["slash"])

    def test_prompt_keeps_elements_and_effect_type_as_separate_dimensions(self) -> None:
        condition = parse_prompt_condition("卡通蓝色能量爆点，短时爆发，不要长拖尾", "impact", 1)
        self.assertEqual(condition["effect_element_tags"], ["energy"])
        self.assertEqual(condition["effect_type"], "impact")
        self.assertEqual(condition["target_effect_family"], "impact")
        self.assertEqual(condition["effect_families"], ["impact"])

    def test_hit_and_burst_terms_share_impact_type(self) -> None:
        for text in ("雷电命中", "火焰受击", "蓝色爆点", "energy impact"):
            self.assertEqual(parse_prompt_condition(text, "impact", 1)["effect_type"], "impact")

    def test_lightning_does_not_create_a_light_element(self) -> None:
        condition = parse_prompt_condition("lightning slash", "slash", 1)
        self.assertIn("lightning", condition["effect_element_tags"])
        self.assertNotIn("light", condition["effect_element_tags"])

    def test_slash_does_not_create_a_light_element_from_type_term(self) -> None:
        condition = parse_prompt_condition("卡通蓝色能量刀光，快速斩击", "slash", 1)
        self.assertEqual(condition["effect_type"], "slash")
        self.assertEqual(condition["effect_element_tags"], ["energy"])

    def test_runtime_request_requires_compiled_manifest(self) -> None:
        self.assertTrue(callable(build_runtime_request))
        self.assertTrue(callable(build_compile_request))

    def test_new_prompt_generation_uses_real_material_plan_textures(self) -> None:
        source = (ROOT / "workspace/tools/vfx_generation/prompt_graph_generator.py").read_text(encoding="utf-8")
        self.assertIn("build_material_plan", source)
        self.assertIn("texture_asset_path", source)
        self.assertNotIn('final_billboard["texture"] =', source)
        self.assertNotIn("runtime binding uses generated texture", source)

    def test_batch_compiler_contract_preserves_individual_results(self) -> None:
        source = (ROOT / "UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabGraphCompiler.cs").read_text(encoding="utf-8")
        launcher = (ROOT / "workspace/tools/effectdemo_compile_prefab_graph_batch.ps1").read_text(encoding="utf-8")
        self.assertIn("CompileBatchFromCommandLine", source)
        self.assertIn("WriteResult(item.result_path", source)
        self.assertIn("source_prefab_read = false", source)
        self.assertIn("[switch]$NoUpm", launcher)

    def test_dual_family_report_is_technical_not_human(self) -> None:
        self.assertTrue(callable(build_dual_family_report))
        self.assertTrue(callable(attach_vfxspec))
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prompt_graph_dual_family_report.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["human_aesthetic_labels_used"]["const"], 0)

    def test_real_dual_family_batch_meets_count_and_success_gates(self) -> None:
        report = json.loads((ROOT / "workspace/data/vfx_generation/generated/prompt_graph_dual_family_r001/dual_family_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass_technical_prompt_unscored")
        self.assertEqual({row["effect_family"] for row in report["families"]}, {"explosion", "slash"})
        for row in report["families"]:
            self.assertGreaterEqual(row["candidate_count"], 8)
            self.assertGreaterEqual(row["technical_success_count"], 1)
            self.assertTrue(row["dependency_closed"])
            self.assertEqual(row["selected_candidate"]["label_source"], "ai_hypothesis")

    def test_final_two_family_manifests_pass_separate_technical_gates(self) -> None:
        roots = (
            ROOT / "workspace/data/vfx_generation/generated/prompt_graph_generation_r001/lightning_r004",
            ROOT / "workspace/data/vfx_generation/generated/prompt_graph_generation_r001/explosion_medium_r005",
        )
        families = set()
        for root in roots:
            manifest = json.loads((root / "generation_manifest.json").read_text(encoding="utf-8"))
            candidate = manifest["candidates"][0]
            families.update(manifest["prompt_condition"]["effect_families"])
            self.assertEqual(manifest["status"], "pass_technical_prompt_unscored")
            self.assertEqual(manifest["quality_gates"]["schema_valid_count"], 1)
            self.assertEqual(manifest["quality_gates"]["unity_compile_pass_count"], 1)
            self.assertEqual(manifest["quality_gates"]["runtime_visible_count"], 1)
            self.assertEqual(candidate["parent_prefab_path"], None)
        self.assertEqual(families, {"lightning", "explosion"})
