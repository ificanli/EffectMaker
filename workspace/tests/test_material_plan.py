from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.material_plan import apply_material_plan, build_material_plan, load_registry


ROOT = Path(__file__).parents[2]


class MaterialPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(ROOT / "workspace/data/vfx_generation/asset_registry/asset_registry_r003")
        graph_path = ROOT / "workspace/data/vfx_generation/generated/prompt_graph_dual_family_r001/slash_r002/candidates/prompt_graph_generation_001_000_pfg_82c44bcdeecdc60802ad/graph.json"
        cls.graph = json.loads(graph_path.read_text(encoding="utf-8"))

    def test_prompt_family_and_layer_role_change_real_texture_selection(self) -> None:
        slash = build_material_plan(self.graph, self.registry, {"text": "写实青色刀光", "effect_family": "slash", "style_family": "realistic", "color_keywords": ["cyan"], "performance_tier": "standard"}, seed=1)
        fire = build_material_plan(self.graph, self.registry, {"text": "卡通橙色火焰", "effect_family": "fire", "style_family": "cartoon", "color_keywords": ["orange"], "performance_tier": "standard"}, seed=1)
        slash_texture = slash["layers"][0]["candidates"][0]["texture"]
        fire_texture = fire["layers"][0]["candidates"][0]["texture"]

        self.assertEqual(slash["status"], "pass")
        self.assertEqual(fire["status"], "pass")
        self.assertTrue(slash_texture["path"].startswith("Assets/"))
        self.assertTrue(fire_texture["path"].startswith("Assets/"))
        self.assertNotEqual(slash_texture["asset_id"], fire_texture["asset_id"])
        self.assertTrue({"semantic.slash", "semantic.trail", "semantic.spark"} & set(slash_texture["tags"]))
        self.assertTrue({"semantic.fire", "semantic.spark", "semantic.smoke"} & set(fire_texture["tags"]))
        self.assertEqual(set(slash["quality_gates"].values()) - {len(slash["layers"])}, {0})
        self.assertEqual(len({row["texture"]["asset_id"] for row in fire["layers"][0]["candidates"]}), len(fire["layers"][0]["candidates"]))
        self.assertTrue(all("pairing" in row["scores"] for row in fire["layers"][0]["candidates"]))

    def test_applied_graph_uses_selected_project_texture_and_no_generated_profile(self) -> None:
        plan = build_material_plan(self.graph, self.registry, {"text": "风格化蓝色雷电", "effect_family": "lightning", "style_family": "stylized", "color_keywords": ["blue"], "performance_tier": "mobile"}, seed=9)
        graph = apply_material_plan(self.graph, plan)
        selected = plan["layers"][0]["candidates"][0]
        parameters = graph["components"]["particle_systems"][0]["parameters"]
        self.assertEqual(parameters["texture_asset_path"], selected["texture"]["path"])
        self.assertEqual(parameters["texture_property_name"], selected["texture_property_name"])
        self.assertIsNone(parameters["texture_profile"])
        self.assertEqual(parameters["material_template_path"], selected["material"]["path"])
        self.assertEqual(graph["condition"]["parent_prefab_path"], None)

    def test_plan_matches_strict_schema_and_selects_no_reference_assets(self) -> None:
        plan = build_material_plan(self.graph, self.registry, {"text": "卡通橙色爆炸", "effect_family": "explosion", "style_family": "cartoon", "color_keywords": ["orange"], "performance_tier": "standard"}, seed=3)
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/material_plan.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(plan)), [])
        for layer in plan["layers"]:
            for candidate in layer["candidates"]:
                self.assertEqual(candidate["shader"]["binding_status"], "project_bindable")
                self.assertEqual(candidate["texture"]["binding_status"], "project_bindable")
                self.assertEqual(candidate["material"]["binding_status"], "usable")

    def test_optional_neural_asset_pair_ranker_is_recorded(self) -> None:
        checkpoint = ROOT / "workspace/data/vfx_generation/models/material_asset_pair_full_r003/material_asset_pair_model.pt"
        if not checkpoint.is_file():
            self.skipTest("asset pair checkpoint is not available")
        from workspace.tools.vfx_generation.material_asset_pair_model import load_model
        plan = build_material_plan(self.graph, self.registry, {"text": "卡通蓝色爆炸冲击", "effect_family": "explosion", "effect_type": "explosion", "effect_element_tags": ["energy"], "style_family": "cartoon", "color_keywords": ["blue"], "performance_tier": "standard"}, seed=4, asset_pair_model=load_model(checkpoint))
        self.assertTrue(plan["selection_policy"]["neural_asset_pair_ranking"])
        self.assertTrue(all("neural_probability" in layer["candidates"][0]["scores"] and "rank_total" in layer["candidates"][0]["scores"] for layer in plan["layers"]))


if __name__ == "__main__":
    unittest.main()
