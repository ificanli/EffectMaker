from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.proposal_plan import build_proposal_plan, parse_prompt_intent


ROOT = Path(__file__).parents[2]
PROMPT = "风格化蓝紫横向斩击，外刃锐利，内层克制，前端命中闪点明确，尾迹在峰值后快速收束"


class ProposalPlanTests(unittest.TestCase):
    def test_prompt_changes_explicit_shape_hit_color_direction_and_timing_controls(self) -> None:
        intent = parse_prompt_intent(PROMPT, "slash")

        self.assertEqual(intent["style_family"], "stylized")
        self.assertEqual(intent["color_keywords"], ["blue", "purple"])
        self.assertEqual(intent["direction"], "horizontal")
        self.assertIn("sharp_outer_edge", intent["shape_keywords"])
        self.assertIn("restrained_inner_layer", intent["shape_keywords"])
        self.assertEqual(intent["hit_placement"], "leading_edge")
        self.assertIn("fast_collapse_after_peak", intent["timing_keywords"])

    def test_shared_plan_requires_role_specific_shader_and_absolute_quality_gates(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/vfx_proposal_plan.schema.json").read_text(encoding="utf-8"))
        plan = build_proposal_plan(PROMPT, "slash", 20262501)

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(plan)), [])
        self.assertTrue(plan["selection_policy"]["role_specific_shader_plan"])
        self.assertTrue(plan["selection_policy"]["whole_batch_absolute_quality_gate"])
        self.assertFalse(plan["training_eligibility"]["positive_generation_supervision"])
        self.assertEqual(plan["procedure_context"]["status"], "missing")
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual({row["layer_role"] for row in plan["layers"]}, {"core", "support", "hit", "residual"})
        self.assertTrue(all(len(row["topology_candidates"]) >= 3 for row in plan["layers"]))
        self.assertIn("hit_placement", next(row for row in plan["layers"] if row["layer_role"] == "hit")["prompt_controls"])
        self.assertIn("timing_keywords", next(row for row in plan["layers"] if row["layer_role"] == "residual")["prompt_controls"])

    def test_every_migration_family_uses_multiple_topologies_and_no_unverified_fallback(self) -> None:
        for family in ("slash", "lightning", "explosion", "fire", "shield"):
            plan = build_proposal_plan(f"风格化蓝色 {family}", family, 7)
            self.assertTrue(all(len(row["topology_candidates"]) >= 3 for row in plan["layers"]))
            self.assertTrue(all(row["shader_contract"]["forbid_unverified_fallback"] for row in plan["layers"]))


if __name__ == "__main__":
    unittest.main()
