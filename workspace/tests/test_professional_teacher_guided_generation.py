from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.professional_teacher_guided_generation import _load_teacher_rule, apply_explosion_core_prior


def graph() -> dict:
    return {
        "schema_version": "vfx_prefab_graph.v1",
        "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None},
        "condition": {"prompt": "x", "effect_family": "explosion", "style_family": "cartoon", "seed": 1, "parent_prefab_path": None},
        "root_node_id": "n0000",
        "nodes": [
            {"node_id": "n0000", "name": "Root", "parent_node_id": None, "sibling_index": 0, "depth": 0, "hierarchy_path": "Root[0]", "active_self": True, "component_types": ["UnityEngine.Transform"], "role": "root", "transform": {"local_position": [0, 0, 0], "local_rotation": [0, 0, 0, 1], "local_scale": [1, 1, 1]}},
            {"node_id": "n0001", "name": "Core", "parent_node_id": "n0000", "sibling_index": 0, "depth": 1, "hierarchy_path": "Root[0]/Core[0]", "active_self": True, "component_types": ["UnityEngine.Transform", "UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer"], "role": "core", "transform": {"local_position": [0, 0, 0], "local_rotation": [0, 0, 0, 1], "local_scale": [1, 1, 1]}},
        ],
        "components": {
            "particle_systems": [{"component_id": "p0000", "node_id": "n0001", "parameters": {"duration_seconds": 1.0, "looping": False, "max_particles": 8, "start_lifetime_max": 0.5, "start_speed_max": 1.0, "start_size_max": 0.2, "start_color_rgba": [0, 0, 1, 1], "end_color_rgba": [0, 0, 1, 0], "simulation_space": "Local", "emission_enabled": True, "emission_rate_over_time_max": 0, "burst_particle_count": 2, "shape_enabled": True, "shape_type": "Sphere", "shape_radius": 0.2, "color_over_lifetime_enabled": True, "size_over_lifetime_enabled": True, "end_size_multiplier": 0, "renderer_mode": "Billboard", "sorting_order": 0, "serialized_modules": {}, "shader_profile": None, "texture_profile": None, "material_template_path": "Assets/old.mat", "texture_asset_path": "Assets/old.png", "texture_property_name": "_MainTex"}, "material_paths": [], "mesh_paths": []}],
            "renderers": [{"component_id": "r0000", "node_id": "n0001", "renderer_type": "ParticleSystemRenderer", "enabled": True, "parameters": {"particle_render_mode": "Billboard", "sorting_order": 0}, "material_paths": [], "mesh_paths": []}],
            "animations": [],
        },
        "asset_bindings": {"materials": [], "meshes": []},
        "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []},
        "training": {"eligible_tasks": [], "excluded_tasks": [], "aesthetic_label_source": "ai_hypothesis"},
        "provenance": {"source_dataset_id": "test", "source_run_id": None, "exporter": "prefab_graph_constrained.v1", "assumptions": []},
    }


class ProfessionalTeacherGuidedGenerationTests(unittest.TestCase):
    def test_verified_lightning_core_support_rule_is_loadable(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            reference = graph()
            reference["condition"]["effect_family"] = "lightning"
            reference_path = root / "reference.json"
            report_path = root / "report.json"
            ready_path = root / "teacher_ready.jsonl"
            reference_path.write_text(json.dumps(reference), encoding="utf-8")
            report_path.write_text(json.dumps({
                "status": "verified",
                "validated_controller_prior": {
                    "status": "eligible",
                    "effect_family": "lightning",
                    "target_role": "core_support",
                    "reference_graph_path": reference_path.as_posix(),
                },
            }), encoding="utf-8")
            ready_path.write_text(json.dumps({
                "record_id": "lightning-rule",
                "teacher_training_eligible": True,
                "allowed_use": "aesthetic_teacher_training",
                "unity_reproduction_report": report_path.as_posix(),
            }) + "\n", encoding="utf-8")

            record, report, loaded = _load_teacher_rule(ready_path, "lightning-rule")

        self.assertEqual(record["record_id"], "lightning-rule")
        self.assertEqual(report["validated_controller_prior"]["target_role"], "core_support")
        self.assertEqual(loaded["condition"]["effect_family"], "lightning")

    def test_verified_support_and_hit_rules_are_loadable(self) -> None:
        for role in ("support", "hit", "multi_layer"):
            with self.subTest(role=role), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                root = Path(temp)
                reference_path = root / "reference.json"
                report_path = root / "report.json"
                ready_path = root / "teacher_ready.jsonl"
                reference_path.write_text(json.dumps(graph()), encoding="utf-8")
                report_path.write_text(json.dumps({
                    "status": "verified",
                    "validated_controller_prior": {
                        "status": "eligible",
                        "effect_family": "explosion",
                        "target_role": role,
                        "reference_graph_path": reference_path.as_posix(),
                    },
                }), encoding="utf-8")
                ready_path.write_text(json.dumps({
                    "record_id": f"{role}-rule",
                    "teacher_training_eligible": True,
                    "allowed_use": "aesthetic_teacher_training",
                    "unity_reproduction_report": report_path.as_posix(),
                }) + "\n", encoding="utf-8")

                record, report, reference = _load_teacher_rule(ready_path, f"{role}-rule")

            self.assertEqual(record["record_id"], f"{role}-rule")
            self.assertEqual(report["validated_controller_prior"]["target_role"], role)
            self.assertEqual(reference["condition"]["effect_family"], "explosion")

    def test_verified_core_prior_changes_only_target_role_and_provenance(self) -> None:
        source = graph()
        reference = copy.deepcopy(source)
        reference_core = reference["components"]["particle_systems"][0]["parameters"]
        reference_core.update({
            "material_template_path": "Assets/core.mat",
            "texture_asset_path": "Assets/core.png",
            "start_size_max": 0.9,
            "sorting_order": 10,
        })
        reference["components"]["renderers"][0]["parameters"]["sorting_order"] = 10

        guided, changed = apply_explosion_core_prior(source, reference, "professional-rule")

        core = guided["components"]["particle_systems"][0]["parameters"]
        self.assertEqual(core["material_template_path"], "Assets/core.mat")
        self.assertEqual(core["texture_asset_path"], "Assets/core.png")
        self.assertEqual(core["start_size_max"], 0.9)
        self.assertEqual(guided["components"]["renderers"][0]["parameters"]["sorting_order"], 10)
        self.assertIn("Assets/core.mat", guided["asset_bindings"]["materials"])
        self.assertIn("core.parameters.material_template_path", changed)
        self.assertEqual(source["components"]["particle_systems"][0]["parameters"]["material_template_path"], "Assets/old.mat")
        self.assertNotEqual(guided["graph_id"], source.get("graph_id"))

    def test_non_explosion_graph_is_rejected(self) -> None:
        source = graph()
        source["condition"]["effect_family"] = "slash"
        with self.assertRaisesRegex(ValueError, "requires an explosion"):
            apply_explosion_core_prior(source, graph(), "professional-rule")


if __name__ == "__main__":
    unittest.main()
