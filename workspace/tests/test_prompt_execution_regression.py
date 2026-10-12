from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prompt_execution_regression import _capture_metrics, prepare_regression
from workspace.tools.vfx_generation.prompt_execution_controls import apply_prompt_controls


ROOT = Path(__file__).parents[2]


class PromptExecutionRegressionTests(unittest.TestCase):
    def test_empty_unity_gradient_object_keeps_legacy_recoloring_of_both_endpoints(self) -> None:
        graph = {'nodes': [{'node_id': 'n0000', 'role': 'core'}], 'condition': {'effect_family': 'lightning'},
                 'components': {'particle_systems': [{'node_id': 'n0000', 'component_id': 'p0000', 'parameters': {
                     'start_color_rgba': [0.5, 0.5, 0.5, 1.0], 'end_color_rgba': [0.5, 0.5, 0.5, 1.0],
                     'color_over_lifetime_gradient': {'mode': '', 'color_keys': [], 'alpha_keys': []}}}]},
                 'asset_bindings': {'materials': [], 'meshes': []}}
        updated, _ = apply_prompt_controls(graph, 'red lightning')
        parameters = updated['components']['particle_systems'][0]['parameters']
        self.assertEqual(parameters['start_color_rgba'], parameters['end_color_rgba'])
        self.assertNotEqual(parameters['end_color_rgba'], [0.5, 0.5, 0.5, 1.0])
    def test_configured_asset_alone_cannot_prove_urp_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            path.write_text(json.dumps({"frames": [], "active_render_pipeline_type": "UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset"}))
            self.assertFalse(_capture_metrics(path)["target_pipeline_match"])

    def test_urp_execution_requires_verified_runtime_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            for instance, verified, expected in (
                ("UnityEngine.Rendering.Universal.UniversalRenderPipeline", True, True),
                ("UnityEngine.Rendering.Universal.UniversalRenderPipeline", False, False),
                ("no_active_srp", True, False),
            ):
                with self.subTest(instance=instance, verified=verified):
                    path.write_text(json.dumps({"frames": [], "render_pipeline_instance_type": instance, "render_pipeline_verified": verified}))
                    self.assertEqual(expected, _capture_metrics(path)["target_pipeline_match"])

    def test_counterfactuals_lock_assets_and_runtime_particle_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            material_plan = json.loads((ROOT / "workspace/data/vfx_generation/generated/tutorial_lightning_effectdemo2022_r001/material_plan.json").read_text(encoding="utf-8"))
            material_plan["layers"] = [row for row in material_plan["layers"] if row["component_id"] == "p0000"]
            material_plan["quality_gates"].update(selected_layer_count=1, layer_count=1)
            plan_path = Path(directory) / "single_core_material_plan.json"
            plan_path.write_text(json.dumps(material_plan), encoding="utf-8")
            paths = prepare_regression(
                ROOT / "workspace/data/vfx_generation/procedures/procedure_lightning_shape_lifecycle_r001/procedure_spec.json",
                plan_path,
                Path(directory) / "run", "Assets/Generated/PromptControlTest", 100,
            )
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            requests = json.loads(paths["render_requests"].read_text(encoding="utf-8"))["requests"]
            graphs = [json.loads(Path(row["graph_path"]).read_text(encoding="utf-8")) for row in manifest["cases"]]
        self.assertEqual(len(graphs), 4)
        self.assertEqual(len({row["random_seed_key"] for row in requests}), 1)
        self.assertEqual(len({row["candidate_id"] for row in requests}), 4)
        self.assertTrue(all(graph["asset_bindings"] == graphs[0]["asset_bindings"] for graph in graphs))
        self.assertEqual(len({row["execution_sha256"] for row in manifest["cases"]}), 4)
        self.assertFalse(manifest["training_eligibility"]["positive_generation_supervision"])

    def test_stale_two_layer_plan_cannot_silently_apply_to_corrected_core_procedure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'MaterialPlan component set'):
                prepare_regression(
                    ROOT / "workspace/data/vfx_generation/procedures/procedure_lightning_shape_lifecycle_r001/procedure_spec.json",
                    ROOT / "workspace/data/vfx_generation/generated/tutorial_lightning_effectdemo2022_r001/material_plan.json",
                    Path(directory) / "run", "Assets/Generated/StalePlan", 100,
                )


if __name__ == "__main__":
    unittest.main()
