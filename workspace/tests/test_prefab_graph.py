from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prefab_graph import (
    build_prefab_graph,
    export_prefab_graph_dataset,
    parse_hierarchy_path,
    tokenize_prefab_graph,
)
from workspace.tools.vfx_generation.prefab_graph_seed import create_explosion_seed


ROOT = Path(__file__).parents[2]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def source_example() -> dict:
    return {
        "example_id": "source_fx_burst",
        "candidate_id": "fx_burst",
        "run_id": "audit_r1",
        "inputs": {"prefab_path": "Assets/FX/Fx_burst.prefab"},
        "outputs": {
            "prefab_graph": [
                {"hierarchy_path": "Fx_burst[0]/Core[0]", "active_self": True, "component_types": ["UnityEngine.Transform", "UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer"]},
                {"hierarchy_path": "Fx_burst[0]", "active_self": True, "component_types": ["UnityEngine.Transform"]},
            ],
            "particle_systems": [{
                "hierarchy_path": "Fx_burst[0]/Core[0]",
                "simulation_space": "Local",
                "looping": False,
                "shape_type": "Sphere",
                "renderer_mode": "Billboard",
                "start_lifetime_max": 0.5,
                "start_size_max": 2.0,
                "start_speed_max": 1.0,
                "material_paths": ["Assets/FX/Core.mat"],
                "mesh_paths": [],
            }],
            "renderers": [{
                "hierarchy_path": "Fx_burst[0]/Core[0]",
                "renderer_type": "ParticleSystemRenderer",
                "enabled": True,
                "particle_render_mode": "Billboard",
                "material_paths": ["Assets/FX/Core.mat"],
                "mesh_paths": [],
            }],
            "animations": [],
        },
        "split_group": {"prefab_group": "prefab-a", "source_group": "source-a"},
    }


class PrefabGraphTest(unittest.TestCase):
    def test_parse_hierarchy_path(self) -> None:
        self.assertEqual(parse_hierarchy_path("Root[0]/Particle System[3]"), [("Root", 0), ("Particle System", 3)])
        with self.assertRaisesRegex(ValueError, "invalid hierarchy"):
            parse_hierarchy_path("Root/Child[0]")

    def test_build_is_deterministic_and_structure_only(self) -> None:
        first = build_prefab_graph(source_example(), "source-dataset")
        second = build_prefab_graph(source_example(), "source-dataset")
        self.assertEqual(first, second)
        self.assertEqual(first["graph_id"], second["graph_id"])
        self.assertEqual(first["root_node_id"], "n0000")
        self.assertEqual(first["nodes"][1]["parent_node_id"], "n0000")
        self.assertEqual(first["components"]["particle_systems"][0]["node_id"], "n0001")
        self.assertEqual(first["reconstruction"]["status"], "structure_only")
        self.assertIn("nodes[].transform", first["reconstruction"]["missing_fields"])
        self.assertEqual(first["training"]["aesthetic_label_source"], "none")
        self.assertNotIn("full_reconstruction", first["training"]["eligible_tasks"])
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(first)), [])

    def test_tokenizer_is_stable_and_excludes_asset_paths(self) -> None:
        graph = build_prefab_graph(source_example(), "source-dataset")
        first = tokenize_prefab_graph(graph)
        second = tokenize_prefab_graph(graph)
        self.assertEqual(first, second)
        self.assertIn("COMP_PARTICLESYSTEM", first)
        self.assertIn("RENDER_BILLBOARD", first)
        self.assertFalse(any("Assets/" in token for token in first))

    def test_rejects_missing_parent(self) -> None:
        example = source_example()
        example["outputs"]["prefab_graph"] = [
            {"hierarchy_path": "Fx_burst[0]", "component_types": ["UnityEngine.Transform"]},
            {"hierarchy_path": "Fx_burst[0]/Missing[0]/Core[0]", "component_types": ["UnityEngine.Transform"]},
        ]
        with self.assertRaisesRegex(ValueError, "parent hierarchy path is missing"):
            build_prefab_graph(example, "source-dataset")

    def test_accepts_rect_transform_as_transform_subtype(self) -> None:
        example = source_example()
        example["outputs"]["prefab_graph"][1]["component_types"] = ["UnityEngine.RectTransform"]
        graph = build_prefab_graph(example, "source-dataset")
        self.assertIn("nodes[].rect_transform", graph["reconstruction"]["missing_fields"])

    def test_export_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source_root = temp_root / "source"
            output_root = temp_root / "output"
            write_json(source_root / "dataset_manifest.json", {"dataset_id": "source-dataset", "status": "pass"})
            write_jsonl(source_root / "examples.jsonl", [source_example()])
            paths = export_prefab_graph_dataset(source_root, output_root, "graph-dataset")
            manifest = json.loads(paths["dataset_manifest"].read_text(encoding="utf-8"))
            self.assertEqual(manifest["example_count"], 1)
            self.assertEqual(manifest["reconstruction_status_counts"], {"structure_only": 1})
            self.assertEqual(manifest["quality_gates"]["aesthetic_labels_consumed"], 0)
            self.assertGreater(manifest["token_count"], 0)

    def test_generated_seed_is_reconstructable_and_has_no_parent(self) -> None:
        graph = create_explosion_seed("卡通蓝色能量冲击", 7)
        self.assertEqual(graph["source"]["source_kind"], "generated")
        self.assertIsNone(graph["condition"]["parent_prefab_path"])
        self.assertEqual(graph["reconstruction"]["status"], "reconstructable")
        self.assertEqual(graph["reconstruction"]["missing_fields"], [])
        self.assertEqual(graph["training"]["aesthetic_label_source"], "ai_hypothesis")
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(graph)), [])

    def test_visible_burst_profile_is_deterministic_and_denser_than_baseline(self) -> None:
        baseline = create_explosion_seed("蓝色爆发", 7, "baseline_r001")
        first = create_explosion_seed("蓝色爆发", 7, "visible_burst_r002")
        second = create_explosion_seed("蓝色爆发", 7, "visible_burst_r002")
        self.assertEqual(first, second)
        self.assertGreater(first["components"]["particle_systems"][0]["parameters"]["start_size_max"], baseline["components"]["particle_systems"][0]["parameters"]["start_size_max"])
        self.assertEqual(first["components"]["particle_systems"][0]["parameters"]["texture_profile"], "soft_disc")

    def test_visible_burst_r003_increases_core_scale(self) -> None:
        previous = create_explosion_seed("蓝色爆发", 7, "visible_burst_r002")
        current = create_explosion_seed("蓝色爆发", 7, "visible_burst_r003")
        self.assertGreater(current["components"]["particle_systems"][0]["parameters"]["start_size_max"], previous["components"]["particle_systems"][0]["parameters"]["start_size_max"])
        self.assertGreater(current["components"]["particle_systems"][2]["parameters"]["burst_particle_count"], previous["components"]["particle_systems"][2]["parameters"]["burst_particle_count"])

    def test_visible_burst_r004_increases_core_scale(self) -> None:
        previous = create_explosion_seed("蓝色爆发", 7, "visible_burst_r003")
        current = create_explosion_seed("蓝色爆发", 7, "visible_burst_r004")
        self.assertGreater(current["components"]["particle_systems"][0]["parameters"]["start_size_max"], previous["components"]["particle_systems"][0]["parameters"]["start_size_max"])

    def test_template_glow_profile_routes_all_layers_to_a_real_material_template(self) -> None:
        graph = create_explosion_seed("蓝色爆发", 7, "template_glow_r005")
        template_paths = {particle["parameters"]["material_template_path"] for particle in graph["components"]["particle_systems"]}
        self.assertEqual(template_paths, {"Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_S_fozu/mat/Mat_fozu_03.mat"})


if __name__ == "__main__":
    unittest.main()
