from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prefab_asset_router import ROUTE_KINDS, RUNTIME_VERIFIED_MATERIALS, _route_component, _validate


ROOT = Path(__file__).parents[2]


class PrefabAssetRouterTests(unittest.TestCase):
    def test_route_schema_requires_three_explicit_route_kinds(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_asset_route_plan.schema.json").read_text(encoding="utf-8"))
        routes = schema["properties"]["routes"]["items"]["properties"]["route_kind"]["enum"]
        self.assertEqual(tuple(routes), ROUTE_KINDS)
        self.assertTrue(schema["properties"]["selection_policy"]["properties"]["no_silent_fallback"]["const"])

    def test_minimal_pass_plan_validates(self) -> None:
        asset = lambda kind: {"asset_id": None, "path": f"Assets/{kind}", "asset_type": kind, "authorization_status": "generated", "selection_basis": ["test"]}
        plan = {
            "schema_version": "vfx_prefab_asset_route_plan.v1",
            "created_at": "2026-09-02T00:00:00+00:00",
            "plan_id": "asset_route_pfg_00000000000000000000",
            "graph_id": "pfg_00000000000000000000",
            "condition": {"prompt": None, "effect_family": None, "style_family": None, "seed": None},
            "routes": [
                {"route_id": kind, "route_kind": kind, "target_component_id": None, "material": asset("material"), "texture": asset("texture"), "mesh": asset("mesh") if kind == "mesh_particle" else None, "compatibility": {}, "selection_basis": ["test"], "status": "pass"}
                for kind in ROUTE_KINDS
            ],
            "selection_policy": {"material_selection": "shader_property_and_texture_slot_compatibility", "texture_selection": "content_tag_and_slot_role", "mesh_selection": "unity_api_geometry_audit", "no_silent_fallback": True},
            "status": "pass",
        }
        _validate(plan)
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_asset_route_plan.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(plan)), [])

    def test_unity_audit_contract_uses_asset_database_mesh_data(self) -> None:
        source = (ROOT / "UnityDemo/EffectDemo/Assets/Editor/EffectDemoAssetRouteAudit.cs").read_text(encoding="utf-8")
        self.assertIn("AssetDatabase.LoadAllAssetsAtPath", source)
        self.assertIn("mesh.uv", source)
        self.assertIn("source_import_pivot", source)
        self.assertNotIn("ReadAllText(assetPath)", source)

    def test_mesh_route_does_not_fallback_to_billboard_component(self) -> None:
        graph = {"components": {"renderers": [{"component_id": "r0000", "renderer_type": "ParticleSystemRenderer", "parameters": {"particle_render_mode": "Billboard"}}]}}
        self.assertIsNone(_route_component(graph, "mesh_particle"))
        self.assertEqual(_route_component(graph, "billboard"), "r0000")

    def test_audit_launcher_keeps_unity_2022_and_asset_database_boundary(self) -> None:
        source = (ROOT / "workspace/tools/effectdemo_audit_asset_routes.ps1").read_text(encoding="utf-8")
        self.assertIn("EffectDemoAssetRouteAudit.Run", source)
        self.assertIn("2022.3.16f1", source)
        self.assertIn("material-binding-audit.json", source)
        self.assertIn('"Assets/" + $_.FullName.Substring', source)

    def test_real_route_batch_contains_all_three_verified_routes(self) -> None:
        plan = json.loads((ROOT / "workspace/data/vfx_generation/generated/prefab_asset_routes_r001/asset_route_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["status"], "pass")
        self.assertEqual({route["route_kind"] for route in plan["routes"]}, set(ROUTE_KINDS))
        self.assertTrue(all(route["material"]["asset_id"] for route in plan["routes"]))
        self.assertTrue(all(route["texture"]["asset_id"] for route in plan["routes"]))
        mesh_route = next(route for route in plan["routes"] if route["route_kind"] == "mesh_particle")
        self.assertEqual(mesh_route["mesh"]["verification"], "unity_api_geometry_audit_pass")
        self.assertTrue(mesh_route["compatibility"]["requires_component_creation"])

    def test_runtime_verified_material_route_is_explicit(self) -> None:
        self.assertIn("Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_S_fozu/mat/Mat_fozu_03.mat", RUNTIME_VERIFIED_MATERIALS)

    def test_hardcoded_shader_set_is_legacy_only(self) -> None:
        source = (ROOT / "workspace/tools/vfx_generation/prefab_asset_router.py").read_text(encoding="utf-8")
        self.assertIn("LEGACY_ALLOWED_SHADERS", source)
        self.assertNotIn("\nALLOWED_SHADERS =", source)


if __name__ == "__main__":
    unittest.main()
