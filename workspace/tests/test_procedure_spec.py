from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.procedure_spec import load_procedure_library, retrieve_procedures, validate_procedure_spec, steps_for_role
from workspace.tools.vfx_generation.proposal_plan import build_proposal_plan


ROOT = Path(__file__).parents[2]
PROCEDURE_ROOT = ROOT / "workspace/data/vfx_generation/procedures"


class ProcedureSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.procedures = load_procedure_library(PROCEDURE_ROOT)
        cls.fireworks = next(row for row in cls.procedures if row["procedure_id"] == "procedure_fireworks_layered_lifecycle_r001")
        cls.lightning = next(row for row in cls.procedures if row["procedure_id"] == "procedure_lightning_shape_lifecycle_r001")

    def test_verified_fireworks_reproduction_is_a_valid_procedure_but_not_positive_generation_label(self) -> None:
        validate_procedure_spec(self.fireworks)
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/procedure_spec.schema.json").read_text(encoding="utf-8"))

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(self.fireworks)), [])
        self.assertEqual(self.fireworks["validation"]["source_reproduction_status"], "verified")
        self.assertEqual(self.fireworks["validation"]["target_project_reproduction_status"], "pending")
        self.assertTrue(self.fireworks["training_eligibility"]["planner_constraint"])
        self.assertFalse(self.fireworks["training_eligibility"]["controller_sft"])
        self.assertFalse(self.fireworks["training_eligibility"]["positive_generation_supervision"])

    def test_retrieval_matches_family_and_style_without_cross_family_leakage(self) -> None:
        fire = retrieve_procedures(self.procedures, effect_family="fire", style_family="stylized")
        lightning = retrieve_procedures(self.procedures, effect_family="lightning", style_family="stylized")
        slash = retrieve_procedures(self.procedures, effect_family="slash", style_family="stylized")

        self.assertEqual([row["procedure_id"] for row in fire], ["procedure_fireworks_layered_lifecycle_r001"])
        self.assertEqual([row["procedure_id"] for row in lightning], ["procedure_lightning_shape_lifecycle_r001"])
        self.assertEqual(slash, [])

    def test_real_production_tutorial_is_retrievable_but_not_sft_before_target_reproduction(self) -> None:
        validate_procedure_spec(self.lightning)
        self.assertEqual(self.lightning["source"]["source_type"], "production_tutorial")
        self.assertEqual(self.lightning["source"]["source_status"], "partially_verified")
        self.assertTrue(self.lightning["source"]["timecodes"])
        self.assertTrue(self.lightning["source"]["frame_paths"])
        self.assertFalse(self.lightning["training_eligibility"]["controller_sft"])
        self.assertFalse(self.lightning["training_eligibility"]["positive_generation_supervision"])

    def test_inferred_mapping_is_not_an_applied_tutorial_constraint(self) -> None:
        rows = steps_for_role([self.lightning], "core")
        self.assertTrue(rows)
        self.assertTrue(all(step["evidence_status"] != "inferred" for _, step in rows))
        plan = build_proposal_plan("风格化蓝色闪电", "lightning", 23, procedure_specs=[self.lightning])
        inferred = {f"{self.lightning['procedure_id']}:{step['step_id']}" for step in self.lightning["steps"] if step["evidence_status"] == "inferred"}
        self.assertTrue(inferred.isdisjoint(plan["procedure_context"]["applied_step_ids"]))
        self.assertEqual(set(plan["procedure_context"]["hypothesis_step_ids"]), inferred)

    def test_video_audit_does_not_turn_photoshop_layers_or_other_object_mask_into_core_requirements(self) -> None:
        steps = {row['step_id']: row for row in self.lightning['steps']}
        self.assertEqual(steps['step_003']['target_layer'], 'LightningShapeTexture')
        self.assertEqual(steps['step_003']['authoring_stage'], 'texture_authoring')
        self.assertEqual(steps['step_007']['target_layer'], 'SourceQiTrail')
        self.assertNotIn('cutout_control', steps['step_007']['required_shader_features'])
        self.assertEqual(self.lightning['output_contract']['required_roles'], ['core'])
        self.assertNotIn('outline_follows_main_bolt', self.lightning['output_contract']['timing_relationships'])

    def test_procedure_constrains_shader_texture_layers_and_timing_but_target_version_gate_stays_closed(self) -> None:
        plan = build_proposal_plan(
            "风格化烟花爆发，先上升，再爆炸，最后留下火星",
            "fire",
            9,
            procedure_specs=self.procedures,
        )

        self.assertEqual(plan["procedure_context"]["status"], "candidate")
        self.assertIn("procedure_fireworks_layered_lifecycle_r001", plan["procedure_context"]["matched_procedure_ids"])
        self.assertEqual(plan["procedure_context"]["target_verified_procedure_ids"], [])
        self.assertIn("core_precedes_radial_branches", plan["procedure_context"]["timing_relationships"])
        core = next(row for row in plan["layers"] if row["layer_role"] == "core")
        hit = next(row for row in plan["layers"] if row["layer_role"] == "hit")
        self.assertIn("emission_control", core["shader_contract"]["required_all"])
        self.assertTrue(any("luma.bright_core" in group for group in core["texture_contract"]["required_any"]))
        self.assertIn("procedure_fireworks_layered_lifecycle_r001:step_004", hit["procedure_step_ids"])
        self.assertEqual(plan["status"], "blocked")
        self.assertFalse(plan["training_eligibility"]["positive_generation_supervision"])


if __name__ == "__main__":
    unittest.main()
