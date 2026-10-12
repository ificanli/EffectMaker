from __future__ import annotations

import json
import copy
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.material_plan import load_registry
from workspace.tools.vfx_generation.proposal_plan import build_proposal_plan
from workspace.tools.vfx_generation.shader_material_contract import audit_graph_contract, shader_features


ROOT = Path(__file__).parents[2]
PROMPT = "风格化蓝紫横向斩击，外刃锐利，内层克制，前端命中闪点明确，尾迹在峰值后快速收束"


class ShaderMaterialContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(ROOT / "workspace/data/vfx_generation/asset_registry/asset_registry_r003")
        cls.graph = json.loads((ROOT / "workspace/data/vfx_generation/generated/layered_slash_family_r015/candidates/layered_slash_001_pfg_2cece59f7a40dda2d60a/graph.json").read_text(encoding="utf-8"))

    def test_static_match_and_shared_template_cannot_approve_training(self) -> None:
        plan = build_proposal_plan(PROMPT, "slash", 20262501)
        for layer in plan["layers"]:
            layer["shader_contract"].update(required_all=[], required_any=[], forbidden=[])
            layer["texture_contract"].update(required_any=[], forbidden_tags=[])
        audit = audit_graph_contract(copy.deepcopy(self.graph), self.registry, plan)
        self.assertEqual(audit["status"], "pass")
        self.assertTrue(audit["quality_gates"]["single_template_all_roles"])
        self.assertFalse(audit["training_eligibility"]["positive_generation_supervision"])
        self.assertEqual(audit["evidence_scope"], "static_heuristic_only")

    def test_r015_is_blocked_even_though_it_rendered_without_magenta(self) -> None:
        plan = build_proposal_plan(PROMPT, "slash", 20262501)
        audit = audit_graph_contract(self.graph, self.registry, plan)
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/shader_material_contract_audit.schema.json").read_text(encoding="utf-8"))

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(audit)), [])
        self.assertEqual(audit["status"], "blocked")
        self.assertEqual(audit["quality_gates"]["blocked_layer_count"], 4)
        self.assertTrue(audit["quality_gates"]["single_template_all_roles"])
        self.assertGreater(audit["quality_gates"]["shader_role_mismatch_count"], 0)
        self.assertGreater(audit["quality_gates"]["texture_role_mismatch_count"], 0)
        self.assertFalse(audit["training_eligibility"]["positive_generation_supervision"])
        self.assertTrue(audit["training_eligibility"]["proposal_failure_supervision"])

    def test_hovl_sword_slash_shader_is_recognized_as_requiring_vertex_stream_contract(self) -> None:
        material = next(row for row in self.registry["materials"] if row.get("material_path") == "Assets/Hovl Studio/Sword slash VFX/Materials/SwordSlash.mat")
        shader = next(row for row in self.registry["shaders"] if row.get("asset_id") == material.get("shader_asset_id"))

        features = shader_features(shader, material)

        self.assertIn("dissolve_control", features)
        self.assertIn("emission_control", features)
        self.assertIn("uv_motion", features)
        self.assertIn("custom_vertex_stream_required", features)

    def test_whole_batch_human_rejection_is_schema_valid_and_never_positive_supervision(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/human_feedback.schema.json").read_text(encoding="utf-8"))
        feedback_path = ROOT / "workspace/data/vfx_generation/generated/layered_slash_family_r015/human_feedback.jsonl"
        rows = [json.loads(line) for line in feedback_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(len(rows), 8)
        self.assertTrue(all(list(Draft202012Validator(schema).iter_errors(row)) == [] for row in rows))
        self.assertTrue(all(row["decision"] == "reject" for row in rows))
        self.assertTrue(all(not row["training_eligibility"]["positive_generation_supervision"] for row in rows))
        self.assertTrue(all(row["training_eligibility"]["proposal_failure_supervision"] for row in rows))


if __name__ == "__main__":
    unittest.main()
