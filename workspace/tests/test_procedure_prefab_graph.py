from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.material_plan import apply_material_plan, load_registry
from workspace.tools.vfx_generation.procedure_prefab_graph import build_procedure_prefab_graph, generate_procedure_candidate, prepare_runtime
from workspace.tools.vfx_generation.procedure_spec import load_procedure_library
from workspace.tools.vfx_generation.proposal_asset_router import build_proposal_asset_plan
from workspace.tools.vfx_generation.proposal_plan import build_proposal_plan


ROOT = Path(__file__).parents[2]


class ProcedurePrefabGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.procedures = load_procedure_library(ROOT / "workspace/data/vfx_generation/procedures")
        cls.procedure = next(row for row in cls.procedures if row["procedure_id"] == "procedure_fireworks_layered_lifecycle_r001")
        cls.lightning_procedure = next(row for row in cls.procedures if row["procedure_id"] == "procedure_lightning_shape_lifecycle_r001")
        cls.registry = load_registry(ROOT / "workspace/data/vfx_generation/asset_registry/asset_registry_r003")
        cls.prompt = "风格化橙红烟花，先上升，再爆炸，峰值后留下暗红火星"

    def test_prompt_color_changes_particles_without_changing_geometry_or_timing(self) -> None:
        blue = build_procedure_prefab_graph(self.lightning_procedure, "风格化蓝色闪电", "lightning", 23)
        red = build_procedure_prefab_graph(self.lightning_procedure, "风格化红色闪电", "lightning", 23)
        self.assertEqual(blue["nodes"], red["nodes"])
        for left, right in zip(blue["components"]["particle_systems"], red["components"]["particle_systems"]):
            a, b = left["parameters"], right["parameters"]
            self.assertGreater(a["start_color_rgba"][2], a["start_color_rgba"][0])
            self.assertGreater(b["start_color_rgba"][0], b["start_color_rgba"][2])
            self.assertEqual(a["start_color_rgba"][3], b["start_color_rgba"][3])
            for field in ("start_lifetime_max", "start_delay_max", "start_size_x_max", "start_size_y_max", "start_rotation_max"):
                self.assertEqual(a[field], b[field])

    def test_new_tutorials_separate_particle_tint_from_lifetime_and_material_color(self) -> None:
        for prompt in ("white lightning", "blue lightning"):
            graph = build_procedure_prefab_graph(self.lightning_procedure, prompt, "lightning", 23)
            for particle in graph["components"]["particle_systems"]:
                parameters = particle["parameters"]
                self.assertEqual(parameters.get("material_color_mode"), "preserve_template")
                gradient = parameters.get("color_over_lifetime_gradient")
                self.assertIsNotNone(gradient)
                self.assertEqual(gradient["mode"], "Fixed")
                self.assertEqual(gradient["color_keys"][0]["rgb"], [1.0, 1.0, 1.0])
                self.assertTrue(any(key["rgb"] == [0.0, 0.0, 0.0] for key in gradient["color_keys"]))
                self.assertEqual(gradient["alpha_keys"][0], {"time": 0.0, "alpha": 1.0})
                self.assertEqual(gradient["alpha_keys"][-1], {"time": 1.0, "alpha": 1.0})

    def test_prompt_direction_rotates_planar_particles_and_keeps_other_parameters(self) -> None:
        horizontal = build_procedure_prefab_graph(self.lightning_procedure, "风格化蓝色横向闪电", "lightning", 23)
        vertical = build_procedure_prefab_graph(self.lightning_procedure, "风格化蓝色纵向闪电", "lightning", 23)
        a = horizontal["components"]["particle_systems"][0]["parameters"]
        b = vertical["components"]["particle_systems"][0]["parameters"]
        self.assertAlmostEqual(math.sin(a["start_rotation_max"]), 0.0, places=5)
        self.assertAlmostEqual(abs(math.sin(b["start_rotation_max"])), 1.0, places=5)
        self.assertEqual(a["start_lifetime_max"], b["start_lifetime_max"])
        self.assertEqual(a["start_color_rgba"], b["start_color_rgba"])

    def test_explicit_prompt_duration_scales_the_visible_window(self) -> None:
        def visible_end(graph):
            return max(row["parameters"]["start_delay_max"] + row["parameters"]["start_lifetime_max"] for row in graph["components"]["particle_systems"])
        short = build_procedure_prefab_graph(self.lightning_procedure, "蓝色闪电，持续0.15秒", "lightning", 23)
        long = build_procedure_prefab_graph(self.lightning_procedure, "蓝色闪电，持续0.45秒", "lightning", 23)
        self.assertAlmostEqual(visible_end(short), 0.15, places=6)
        self.assertAlmostEqual(visible_end(long), 0.45, places=6)
        self.assertEqual(short["components"]["particle_systems"][0]["parameters"]["start_size_x_max"], long["components"]["particle_systems"][0]["parameters"]["start_size_x_max"])

    def test_procedure_builds_asset_neutral_five_layer_graph(self) -> None:
        graph = build_procedure_prefab_graph(self.procedure, self.prompt, "fire", 17)
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json").read_text(encoding="utf-8"))
        roles = {node["name"]: node["role"] for node in graph["nodes"] if node["role"] != "root"}
        particles = {next(node["name"] for node in graph["nodes"] if node["node_id"] == row["node_id"]): row for row in graph["components"]["particle_systems"]}

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(graph)), [])
        self.assertEqual(list(roles), ["Launch", "AscentTrail", "ExplosionCore", "RadialBranches", "Residue"])
        self.assertEqual(roles["ExplosionCore"], "core")
        self.assertEqual(roles["RadialBranches"], "hit")
        self.assertEqual(particles["ExplosionCore"]["parameters"]["start_delay_max"], 0.75)
        self.assertTrue(particles["ExplosionCore"]["parameters"]["start_size_3d"])
        self.assertEqual(particles["ExplosionCore"]["parameters"]["start_size_x_max"], 0.475)
        self.assertEqual(particles["RadialBranches"]["parameters"]["shape_type"], "Sphere")
        self.assertTrue(all(row["parameters"]["material_template_path"] is None for row in particles.values()))
        self.assertTrue(all(row["parameters"]["active_vertex_streams"] == ["Position", "Color", "UV"] for row in graph["components"]["renderers"]))

    def test_original_asset_tuple_router_applies_without_arbitrary_texture_swaps(self) -> None:
        graph = build_procedure_prefab_graph(self.procedure, self.prompt, "fire", 17)
        proposal = build_proposal_plan(self.prompt, "fire", 17, procedure_specs=self.procedures)
        material_plan = build_proposal_asset_plan(graph, self.registry, proposal)

        self.assertEqual(material_plan["status"], "pass")
        self.assertEqual(material_plan["quality_gates"]["selected_layer_count"], 5)
        selected = [layer["candidates"][0] for layer in material_plan["layers"]]
        self.assertEqual(len({row["material"]["material_id"] for row in selected}), 5)
        self.assertTrue(all("original Unity Material-Shader-Texture binding is preserved" in row["selection_basis"] for row in selected))
        applied = apply_material_plan(graph, material_plan)
        self.assertTrue(all(row["parameters"]["material_template_path"] for row in applied["components"]["particle_systems"]))
        self.assertTrue(all(row["parameters"]["texture_asset_path"] for row in applied["components"]["particle_systems"]))

    def test_generation_package_is_traceable_and_remains_ineligible_until_unity_reproduction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = generate_procedure_candidate(
                ROOT / "workspace/data/vfx_generation/procedures/procedure_fireworks_layered_lifecycle_r001/procedure_spec.json",
                ROOT / "workspace/data/vfx_generation/asset_registry/asset_registry_r003",
                self.prompt,
                "fire",
                17,
                Path(directory) / "run",
                "Assets/Generated/TutorialFireworksR001",
            )
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            material_plan = json.loads(paths["material_plan"].read_text(encoding="utf-8"))
            compile_request = json.loads(paths["compile_request"].read_text(encoding="utf-8"))
            compile_result_path = Path(directory) / "run" / "compile_results" / f"{manifest['candidate']['candidate_id']}.json"
            compile_result_path.parent.mkdir(parents=True, exist_ok=True)
            compile_result_path.write_text(json.dumps({"status": "pass", "output_prefab_path": manifest["candidate"]["output_prefab_path"]}), encoding="utf-8")
            runtime_path = prepare_runtime(paths["manifest"], Path(directory) / "run" / "render_requests_focus.json", capture_variant="runtime_capture_focus", forced_camera_view="front", forced_orthographic_size=2.5)
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "prepared_for_target_project_reproduction")
        self.assertFalse(manifest["training_eligibility"]["positive_generation_supervision"])
        self.assertEqual(material_plan["status"], "pass")
        self.assertEqual(len(compile_request["requests"]), 1)
        self.assertEqual(runtime["requests"][0]["forced_camera_view"], "front")
        self.assertTrue(runtime["requests"][0]["force_orthographic"])
        self.assertEqual(runtime["requests"][0]["forced_orthographic_size"], 2.5)
        self.assertIn("runtime_capture_focus", runtime["requests"][0]["capture_manifest_path"])

    def test_real_lightning_tutorial_can_route_controlled_shader_texture_rebinds(self) -> None:
        prompt = "风格化蓝白短促闪电，硬朗主电流和轻微粗细变化"
        graph = build_procedure_prefab_graph(self.lightning_procedure, prompt, "lightning", 23)
        proposal = build_proposal_plan(prompt, "lightning", 23, procedure_specs=self.procedures)
        material_plan = build_proposal_asset_plan(graph, self.registry, proposal)

        self.assertEqual(material_plan["status"], "pass")
        selected = [layer["candidates"][0] for layer in material_plan["layers"]]
        self.assertTrue(all("semantic.lightning" in row["texture"]["tags"] for row in selected))
        self.assertTrue(any("controlled texture rebind passed Shader property and semantic contracts" in row["selection_basis"] for row in selected))
        self.assertEqual(len({row["material"]["material_id"] for row in selected}), len(selected))


if __name__ == "__main__":
    unittest.main()
