"""Generate four-role explosion PrefabGraphs with explicit timing and assets."""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .prefab_graph import assign_graph_id


SCHEMA_VERSION = "vfx_explosion_family_generation.v1"
GENERATOR_VERSION = "explosion_family_adapter.v3"
CORE_MATERIAL = "Assets/QFX/ProjectilesFX/VFX_Resources/Materials/Nature/MFX_Flare_4.mat"
CORE_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Glow/FX_Glow_1.TGA"
CORE_TEXTURE_CANDIDATE = "Assets/VFXSourceIngest/Shared/Textures/0e/Tex_xingzhe_fire3_0e15be311470531b.png"
CORE_TEXTURE_PROFILES = {"flat_glow": CORE_TEXTURE, "structured_flame": CORE_TEXTURE_CANDIDATE}
SHOCKWAVE_MATERIAL = CORE_MATERIAL
SHOCKWAVE_TEXTURE = "Assets/Hovl Studio/Toon Projectiles 2/Textures/Glow2.png"
DEBRIS_MATERIAL = "Assets/QFX/ProjectilesFX/VFX_Resources/Materials/Magic/MFX_Spark_1.mat"
DEBRIS_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Other/FX_Spark_1.png"
RESIDUAL_MATERIAL = "Assets/QFX/ProjectilesFX/VFX_Resources/Materials/Dark Magic/MFX_Smoke_1.mat"
RESIDUAL_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Smoke/FX_Smoke_3.png"


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _validate(schema_name: str, value: dict[str, Any], label: str) -> None:
    schema = _read(_repo_root() / "workspace/data/vfx_generation/schemas" / schema_name)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _node(node_id: str, name: str, role: str, sibling: int) -> dict[str, Any]:
    root_name = "GeneratedRoot"
    return {
        "node_id": node_id,
        "name": name,
        "role": role,
        "sibling_index": sibling,
        "depth": 1,
        "parent_node_id": "n0000",
        "hierarchy_path": f"{root_name}[0]/{name}[{sibling}]",
        "active_self": True,
        "component_types": ["UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer", "UnityEngine.Transform"],
        "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]},
    }


def _particle(component_id: str, node_id: str, role: str, values: dict[str, Any]) -> dict[str, Any]:
    parameters = {
        "serialized_modules": {"profile": "layered_explosion_v1", "layer_role": role},
        "duration_seconds": values["duration"],
        "start_delay_max": values["delay"],
        "looping": False,
        "simulation_space": "Local",
        "max_particles": max(8, values["burst"] * 2),
        "start_lifetime_max": values["lifetime"],
        "start_speed_max": values["speed"],
        "start_size_max": values["size"],
        "start_rotation_max": values["rotation"],
        "gravity_modifier_max": values["gravity"],
        "start_color_rgba": values["color"],
        "end_color_rgba": values["end_color"],
        "emission_enabled": True,
        "emission_rate_over_time_max": 0.0,
        "burst_particle_count": values["burst"],
        "shape_enabled": True,
        "shape_type": values["shape"],
        "shape_radius": values["radius"],
        "color_over_lifetime_enabled": True,
        "size_over_lifetime_enabled": True,
        "end_size_multiplier": values["end_size"],
        "renderer_mode": "Billboard",
        "sorting_order": values["sorting"],
        "texture_profile": None,
        "shader_profile": None,
        "material_template_path": values["material"],
        "texture_asset_path": values["texture"],
        "texture_property_name": "_MainTex",
    }
    return {"component_id": component_id, "node_id": node_id, "parameters": parameters, "material_paths": [], "mesh_paths": []}


def create_layered_explosion(prompt: str, seed: int, variation_index: int, core_texture_profile: str = "flat_glow") -> dict[str, Any]:
    if core_texture_profile not in CORE_TEXTURE_PROFILES:
        raise ValueError(f"unsupported core texture profile: {core_texture_profile}")
    rng = random.Random(seed)
    warmth = min(1.0, 0.82 + 0.03 * (variation_index % 5))
    roles = [
        ("n0001", "CoreFlash", "core", {
            "duration": 0.8, "delay": 0.0, "lifetime": 0.32 + 0.02 * (variation_index % 3), "speed": 0.0,
            "size": 0.82 + 0.06 * (variation_index % 4), "rotation": 0.0, "gravity": 0.0, "burst": 1,
            "shape": "Sphere", "radius": 0.0, "end_size": 1.45,
            "color": [1.0, 0.96, 0.82, 1.0], "end_color": [1.0, 0.55, 0.08, 0.0],
            "sorting": 12, "material": CORE_MATERIAL, "texture": CORE_TEXTURE_PROFILES[core_texture_profile],
        }),
        ("n0002", "ShockwaveRing", "support", {
            "duration": 0.9, "delay": 0.04 + 0.01 * (variation_index % 3), "lifetime": 0.48 + 0.03 * (variation_index % 2), "speed": 0.0,
            "size": 0.9 + 0.06 * (variation_index % 4), "rotation": rng.uniform(0.0, math.tau), "gravity": 0.0, "burst": 1,
            "shape": "Circle", "radius": 0.0, "end_size": 4.8 + 0.3 * (variation_index % 4),
            "color": [1.0, 0.38 + 0.04 * (variation_index % 3), 0.05, 1.0], "end_color": [0.8, 0.08, 0.01, 0.0],
            "sorting": 7, "material": SHOCKWAVE_MATERIAL, "texture": SHOCKWAVE_TEXTURE,
        }),
        ("n0003", "DebrisBurst", "hit", {
            "duration": 0.9, "delay": 0.07 + 0.01 * (variation_index % 2), "lifetime": 0.52 + 0.04 * (variation_index % 3), "speed": 2.7 + 0.25 * (variation_index % 4),
            "size": 0.12 + 0.015 * (variation_index % 3), "rotation": rng.uniform(0.0, math.tau), "gravity": 0.55 + 0.08 * (variation_index % 3), "burst": 30 + 4 * (variation_index % 4),
            "shape": "Sphere", "radius": 0.1 + 0.02 * (variation_index % 3), "end_size": 0.15,
            "color": [1.0, warmth, 0.18, 0.95], "end_color": [0.5, 0.08, 0.01, 0.0],
            "sorting": 10, "material": DEBRIS_MATERIAL, "texture": DEBRIS_TEXTURE,
        }),
        ("n0004", "ResidualSmoke", "residual", {
            "duration": 1.6, "delay": 0.2 + 0.025 * (variation_index % 4), "lifetime": 1.0 + 0.08 * (variation_index % 3), "speed": 0.28 + 0.05 * (variation_index % 3),
            "size": 0.58 + 0.05 * (variation_index % 4), "rotation": rng.uniform(0.0, math.tau), "gravity": -0.08 - 0.02 * (variation_index % 3), "burst": 10 + 2 * (variation_index % 4),
            "shape": "Sphere", "radius": 0.22 + 0.025 * (variation_index % 3), "end_size": 2.2,
            "color": [0.48, 0.2, 0.08, 0.7], "end_color": [0.08, 0.04, 0.03, 0.0],
            "sorting": 2, "material": RESIDUAL_MATERIAL, "texture": RESIDUAL_TEXTURE,
        }),
    ]
    nodes = [{
        "node_id": "n0000", "name": "GeneratedRoot", "role": "root", "sibling_index": 0, "depth": 0,
        "parent_node_id": None, "hierarchy_path": "GeneratedRoot[0]", "active_self": True,
        "component_types": ["UnityEngine.Transform"],
        "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]},
    }]
    particles = []
    renderers = []
    for index, (node_id, name, role, values) in enumerate(roles):
        nodes.append(_node(node_id, name, role, index))
        particles.append(_particle(f"p{index:04d}", node_id, role, values))
        renderers.append({
            "component_id": f"r{index:04d}", "node_id": node_id, "renderer_type": "ParticleSystemRenderer", "enabled": True,
            "parameters": {"particle_render_mode": "Billboard", "sorting_order": values["sorting"]}, "material_paths": [], "mesh_paths": [],
        })
    graph = {
        "schema_version": "vfx_prefab_graph.v1",
        "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None},
        "condition": {"prompt": prompt, "effect_family": "explosion", "style_family": "cartoon", "seed": seed, "parent_prefab_path": None},
        "root_node_id": "n0000",
        "nodes": nodes,
        "components": {"particle_systems": particles, "renderers": renderers, "animations": []},
        "asset_bindings": {"materials": sorted({values["material"] for _, _, _, values in roles}), "meshes": []},
        "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []},
        "training": {"eligible_tasks": ["component_prediction", "full_reconstruction", "hierarchy_modeling", "particle_parameter_modeling"], "excluded_tasks": ["aesthetic_preference", "prompt_condition"], "aesthetic_label_source": "ai_hypothesis"},
        "provenance": {"source_dataset_id": "explosion_family_adapter_r001", "source_run_id": None, "exporter": "prefab_graph_constrained.v1", "assumptions": ["Four-role explosion topology is constrained by verified Core, Residual, Shockwave and Debris-branch Teacher evidence.", f"Core texture profile: {core_texture_profile}.", "Material quality, complete rhythm and overall aesthetic quality remain AI hypotheses."]},
    }
    graph = assign_graph_id(graph)
    _validate("prefab_graph.schema.json", graph, "layered explosion graph")
    return graph


def _vfxspec(graph: dict[str, Any], run_id: str, candidate_id: str) -> dict[str, Any]:
    roles = _role_map(graph)
    layers = []
    for particle in graph["components"]["particle_systems"]:
        parameters = particle["parameters"]
        role = roles[particle["node_id"]]
        layers.append({
            "role": {"core": "core_flash", "support": "shockwave_ring", "hit": "debris_burst", "residual": "residual_smoke"}[role],
            "status": "active",
            "topology": "layered_explosion_v1",
            "shape_parameters": {"shape_type": parameters["shape_type"], "shape_radius": parameters["shape_radius"], "start_size_max": parameters["start_size_max"], "start_speed_max": parameters["start_speed_max"], "gravity_modifier_max": parameters["gravity_modifier_max"]},
            "material_parameters": {"material_template_path": parameters["material_template_path"], "texture_asset_path": parameters["texture_asset_path"], "texture_property_name": parameters["texture_property_name"]},
            "timing_parameters": {"start_delay_max": parameters["start_delay_max"], "duration_seconds": parameters["duration_seconds"], "start_lifetime_max": parameters["start_lifetime_max"], "burst_particle_count": parameters["burst_particle_count"]},
            "constraints": ["unity_2022_compile_and_readback_required", "professional_teacher_axes_are_narrow_not_global_quality"],
        })
    spec = {
        "schema_version": "vfxspec.v1",
        "effect_family": "explosion",
        "effect_type": "explosion",
        "adapter": {"name": "explosion.adapter", "version": GENERATOR_VERSION, "generator_family": "radial_impact_fragments", "specialized_metrics": ["core_readability", "shockwave_readability", "debris_spread", "residual_timing"]},
        "prompt": graph["condition"]["prompt"],
        "negative_prompt": "不要中心空，不要四层同时出现，不要用同一贴图伪装不同职责",
        "generation": {"run_id": run_id, "candidate_id": candidate_id, "seed": graph["condition"]["seed"], "generator": "explosion_family_generator", "generator_version": GENERATOR_VERSION, "parent_candidate_id": None, "graph_id": graph["graph_id"]},
        "layers": layers,
        "render_plan": {"unity_project": "UnityDemo/EffectDemo", "scene": "LayeredExplosionRuntimeCapture", "camera": "LayeredExplosionRuntimeCamera", "resolution": "512x512", "time_points_seconds": []},
        "training_scope": "verified narrow Core/Residual/Shockwave/Debris priors; material candidate requires layer-isolated cross-axis validation",
    }
    _validate("vfxspec.schema.json", spec, "layered explosion VFXSpec")
    return spec


def _role_map(graph: dict[str, Any]) -> dict[str, str]:
    return {str(node["node_id"]): str(node.get("role") or "") for node in graph["nodes"]}


def generate_batch(prompt: str, output_root: Path, asset_root: str, candidate_count: int = 8, seed: int = 20260904, core_texture_profile: str = "flat_glow") -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"explosion generation output already exists and is not empty: {output_root}")
    candidates = []
    requests = []
    for index in range(max(1, candidate_count)):
        graph = create_layered_explosion(prompt, seed + index, index, core_texture_profile)
        candidate_id = f"layered_explosion_{index:03d}_{graph['graph_id']}"
        candidate_root = output_root / "candidates" / candidate_id
        graph_path = _write(candidate_root / "graph.json", graph)
        spec_path = _write(candidate_root / "vfxspec.json", _vfxspec(graph, output_root.name, candidate_id))
        output_prefab = f"{asset_root.rstrip('/')}/{candidate_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{candidate_id}.json"
        readback_graph = output_root / "readback" / f"{candidate_id}.json"
        readback_result = output_root / "readback_results" / f"{candidate_id}.json"
        capture_manifest = output_root / "runtime_captures" / candidate_id / "capture_manifest.json"
        candidates.append({
            "candidate_id": candidate_id,
            "graph_id": graph["graph_id"],
            "graph_path": _portable(graph_path),
            "vfxspec_path": _portable(spec_path),
            "output_prefab_path": output_prefab,
            "compile_result_path": _portable(compile_result),
            "readback_graph_path": _portable(readback_graph),
            "readback_result_path": _portable(readback_result),
            "capture_manifest_path": _portable(capture_manifest),
            "seed": seed + index,
        })
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    active_teacher_rule_ids = ["professional_explosion_core_readability_r001", "professional_explosion_residual_persistence_r001", "professional_explosion_shockwave_expansion_r001", "professional_explosion_debris_branches_r001", "professional_explosion_staged_rhythm_r001"]
    gated_teacher_rule_ids = []
    if core_texture_profile == "structured_flame":
        active_teacher_rule_ids.append("professional_explosion_core_texture_structure_r001")
    else:
        gated_teacher_rule_ids.append("professional_explosion_core_texture_structure_r001")
    manifest_path = _write(output_root / "generation_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "prompt": prompt,
        "effect_family": "explosion",
        "style_family": "cartoon",
        "core_texture_profile": core_texture_profile,
        "generator": {"name": "explosion.adapter", "version": GENERATOR_VERSION, "teacher_rule_ids": active_teacher_rule_ids, "gated_teacher_rule_ids": gated_teacher_rule_ids, "structure_model_role": "topology prior", "parameter_source": "bounded deterministic sampling"},
        "candidate_count": len(candidates),
        "candidates": candidates,
        "status": "prepared_pending_unity",
    })
    compile_path = _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})
    return {"manifest": manifest_path, "compile_request": compile_path}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_repo_root() / candidate["compile_result_path"])
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {candidate['candidate_id']}")
        case_root = output_path.resolve().parent / "runtime_captures" / candidate["candidate_id"]
        requests.append({
            "candidate_id": candidate["candidate_id"], "prefab_path": compile_result["output_prefab_path"],
            "capture_dir": (case_root / "captures").as_posix(), "capture_manifest_path": (case_root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (case_root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts",
            "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion",
        })
    return _write(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"],
        "scene": "LayeredExplosionRuntimeCapture", "camera": "LayeredExplosionRuntimeCamera", "width": 512, "height": 512,
        "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.05, "max_duration_seconds": 2.5, "include_zero": True, "duration_sources": ["particle_system"]},
        "capture_material_timeline": True, "requests": requests,
    })


def finalize(manifest_path: Path, output_path: Path) -> Path:
    from .professional_teacher_reproduction import _capture_summary

    manifest = _read(manifest_path.resolve())
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_repo_root() / candidate["compile_result_path"])
        readback_result = _read(_repo_root() / candidate["readback_result_path"])
        capture = _capture_summary(_repo_root() / candidate["capture_manifest_path"])
        gates = {
            "compile_pass": compile_result.get("status") == "pass",
            "texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")),
            "prefab_api_readback_pass": readback_result.get("status") == "pass",
            "runtime_eligible": capture["image_sequence_training_eligible"],
            "no_material_render_errors": capture["material_render_error_frame_count"] == 0,
            "has_frames": capture["valid_frame_count"] > 0,
        }
        records.append({
            "candidate_id": candidate["candidate_id"], "graph_id": candidate["graph_id"], "output_prefab_path": candidate["output_prefab_path"],
            "quality_gates": gates, "technical_pass": all(gates.values()), "valid_frame_count": capture["valid_frame_count"],
            "selected_camera_view": capture["selected_camera_view"], "peak_center_luminance": capture["peak_center_luminance"],
            "peak_center_local_contrast": capture["peak_center_local_contrast"], "capture_manifest_path": candidate["capture_manifest_path"],
            "training_scope": "technical_success_with_verified_core_residual_shockwave_priors_not_global_aesthetic_quality",
        })
    report = {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"],
        "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "records": records,
        "status": "pass_technical_family_adapter_unscored" if records and all(row["technical_pass"] for row in records) else "blocked",
        "limitations": [
            "Core readability, residual persistence, shockwave expansion and debris-branch presence have narrow professional Teacher evidence.",
            "The structured Core texture passed its isolated Teacher but is not the default because R010 exposed cross-axis feature entanglement.",
            "Debris variation, complete material composition, complete rhythm and overall aesthetic quality remain AI hypotheses.",
        ],
    }
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and validate four-role explosion PrefabGraphs.")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--asset-root", required=True)
    generate.add_argument("--candidate-count", type=int, default=8)
    generate.add_argument("--seed", type=int, default=20260904)
    generate.add_argument("--core-texture-profile", choices=sorted(CORE_TEXTURE_PROFILES), default="flat_glow")
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--manifest", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--manifest", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            paths = generate_batch(args.prompt, args.output_root, args.asset_root, args.candidate_count, args.seed, args.core_texture_profile)
        elif args.command == "prepare-runtime":
            paths = {"runtime_request": prepare_runtime(args.manifest, args.output)}
        else:
            paths = {"report": finalize(args.manifest, args.output)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
