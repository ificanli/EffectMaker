"""Create deterministic no-parent PrefabGraph seeds for Unity compiler smoke runs."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .prefab_graph import GRAPH_SCHEMA, EXPORTER, _read_json, _schema_root, _write_json, assign_graph_id


def _particle(
    component_id: str,
    node_id: str,
    color: list[float],
    end_color: list[float],
    size: float,
    lifetime: float,
    speed: float,
    burst_count: int,
    radius: float,
    sorting_order: int,
    texture_profile: str,
    material_template_path: str | None = None,
) -> dict[str, Any]:
    parameters = {
        "serialized_modules": {"profile": "generated_particle_v1"},
        "duration_seconds": 0.8,
        "looping": False,
        "simulation_space": "Local",
        "max_particles": max(32, burst_count * 2),
        "start_lifetime_max": lifetime,
        "start_speed_max": speed,
        "start_size_max": size,
        "start_color_rgba": color,
        "end_color_rgba": end_color,
        "emission_enabled": True,
        "emission_rate_over_time_max": 0.0,
        "burst_particle_count": burst_count,
        "shape_enabled": True,
        "shape_type": "Sphere",
        "shape_radius": radius,
        "color_over_lifetime_enabled": True,
        "size_over_lifetime_enabled": True,
        "end_size_multiplier": 0.05,
        "renderer_mode": "Billboard",
        "sorting_order": sorting_order,
        "texture_profile": texture_profile,
    }
    if material_template_path:
        parameters["material_template_path"] = material_template_path
    return {
        "component_id": component_id,
        "node_id": node_id,
        "parameters": parameters,
        "material_paths": [],
        "mesh_paths": [],
    }


def create_explosion_seed(prompt: str, seed: int, profile: str = "baseline_r001") -> dict[str, Any]:
    rng = random.Random(seed)
    energy = 0.92 + rng.random() * 0.08
    profiles = {
        "baseline_r001": {
            "core": (0.72, 0.32, 0.35, 18, 0.04, 3, "soft_disc"),
            "support": (0.38, 0.55, 1.2, 28, 0.12, 2, "soft_disc"),
            "sparks": (0.09, 0.65, 3.2, 42, 0.08, 4, "spark"),
        },
        "visible_burst_r002": {
            "core": (1.85, 0.38, 0.42, 42, 0.05, 3, "soft_disc"),
            "support": (0.82, 0.62, 1.85, 64, 0.18, 2, "soft_disc"),
            "sparks": (0.16, 0.70, 4.1, 96, 0.12, 4, "spark"),
        },
        "visible_burst_r003": {
            "core": (3.4, 0.42, 0.48, 56, 0.06, 3, "soft_disc"),
            "support": (1.5, 0.66, 2.15, 88, 0.22, 2, "soft_disc"),
            "sparks": (0.20, 0.74, 4.6, 128, 0.16, 4, "spark"),
        },
        "visible_burst_r004": {
            "core": (4.8, 0.44, 0.50, 72, 0.08, 3, "soft_disc"),
            "support": (2.1, 0.70, 2.4, 112, 0.28, 2, "soft_disc"),
            "sparks": (0.24, 0.78, 5.0, 160, 0.20, 4, "spark"),
        },
        "template_glow_r005": {
            "core": (4.8, 0.44, 0.50, 72, 0.08, 3, "soft_disc"),
            "support": (2.1, 0.70, 2.4, 112, 0.28, 2, "soft_disc"),
            "sparks": (0.24, 0.78, 5.0, 160, 0.20, 4, "spark"),
        },
    }
    if profile not in profiles:
        raise ValueError(f"unsupported PrefabGraph seed profile: {profile}")
    values = profiles[profile]
    core_size, core_lifetime, core_speed, core_burst, core_radius, core_sorting, core_texture = values["core"]
    support_size, support_lifetime, support_speed, support_burst, support_radius, support_sorting, support_texture = values["support"]
    spark_size, spark_lifetime, spark_speed, spark_burst, spark_radius, spark_sorting, spark_texture = values["sparks"]
    material_template_path = (
        "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_S_fozu/mat/Mat_fozu_03.mat"
        if profile == "template_glow_r005"
        else None
    )
    graph = {
        "schema_version": GRAPH_SCHEMA,
        "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None},
        "condition": {
            "prompt": prompt,
            "effect_family": "explosion",
            "style_family": "cartoon",
            "seed": seed,
            "parent_prefab_path": None,
        },
        "root_node_id": "n0000",
        "nodes": [
            {"node_id": "n0000", "name": "GeneratedBlueImpact", "role": "root", "sibling_index": 0, "depth": 0, "parent_node_id": None, "hierarchy_path": "GeneratedBlueImpact[0]", "active_self": True, "component_types": ["UnityEngine.Transform"], "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}},
            {"node_id": "n0001", "name": "Core", "role": "core", "sibling_index": 0, "depth": 1, "parent_node_id": "n0000", "hierarchy_path": "GeneratedBlueImpact[0]/Core[0]", "active_self": True, "component_types": ["UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer", "UnityEngine.Transform"], "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}},
            {"node_id": "n0002", "name": "Support", "role": "support", "sibling_index": 1, "depth": 1, "parent_node_id": "n0000", "hierarchy_path": "GeneratedBlueImpact[0]/Support[1]", "active_self": True, "component_types": ["UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer", "UnityEngine.Transform"], "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}},
            {"node_id": "n0003", "name": "Sparks", "role": "hit", "sibling_index": 2, "depth": 1, "parent_node_id": "n0000", "hierarchy_path": "GeneratedBlueImpact[0]/Sparks[2]", "active_self": True, "component_types": ["UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer", "UnityEngine.Transform"], "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}},
        ],
        "components": {
            "particle_systems": [
                _particle("p0000", "n0001", [0.55, 0.9, 1.0, energy], [0.05, 0.35, 1.0, 0.0], core_size, core_lifetime, core_speed, core_burst, core_radius, core_sorting, core_texture, material_template_path),
                _particle("p0001", "n0002", [0.05, 0.42, 1.0, 0.72], [0.02, 0.08, 0.35, 0.0], support_size, support_lifetime, support_speed, support_burst, support_radius, support_sorting, support_texture, material_template_path),
                _particle("p0002", "n0003", [0.72, 0.95, 1.0, 0.92], [0.1, 0.45, 1.0, 0.0], spark_size, spark_lifetime, spark_speed, spark_burst, spark_radius, spark_sorting, spark_texture, material_template_path),
            ],
            "renderers": [
                {"component_id": "r0000", "node_id": "n0001", "renderer_type": "ParticleSystemRenderer", "enabled": True, "parameters": {"particle_render_mode": "Billboard", "sorting_order": 3}, "material_paths": [], "mesh_paths": []},
                {"component_id": "r0001", "node_id": "n0002", "renderer_type": "ParticleSystemRenderer", "enabled": True, "parameters": {"particle_render_mode": "Billboard", "sorting_order": 2}, "material_paths": [], "mesh_paths": []},
                {"component_id": "r0002", "node_id": "n0003", "renderer_type": "ParticleSystemRenderer", "enabled": True, "parameters": {"particle_render_mode": "Billboard", "sorting_order": 4}, "material_paths": [], "mesh_paths": []},
            ],
            "animations": [],
        },
        "asset_bindings": {"materials": [], "meshes": []},
        "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []},
        "training": {"eligible_tasks": ["component_prediction", "full_reconstruction", "hierarchy_modeling", "particle_parameter_modeling"], "excluded_tasks": ["aesthetic_preference", "prompt_condition"], "aesthetic_label_source": "ai_hypothesis"},
        "provenance": {"source_dataset_id": "generated_seed", "source_run_id": None, "exporter": EXPORTER, "assumptions": [f"Seed profile {profile} is an AI hypothesis for compiler validation.", "No source or parent Prefab is read by this seed."]},
    }
    return assign_graph_id(graph)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a no-parent PrefabGraph compiler seed.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="卡通蓝色能量冲击，快速爆发，不要长拖尾")
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--profile", choices=["baseline_r001", "visible_burst_r002", "visible_burst_r003", "visible_burst_r004", "template_glow_r005"], default="baseline_r001")
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise FileExistsError(f"seed output already exists: {args.output}")
        graph = create_explosion_seed(args.prompt, args.seed, args.profile)
        schema = _read_json(_schema_root() / "prefab_graph.schema.json")
        errors = list(Draft202012Validator(schema).iter_errors(graph))
        if errors:
            raise ValueError(f"PrefabGraph seed schema error: {errors[0].message}")
        path = _write_json(args.output.resolve(), graph)
    except (FileExistsError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "graph_id": graph["graph_id"], "output": path.as_posix(), "parent_prefab_path": None, "profile": args.profile}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
