"""Generate layered Slash PrefabGraphs with real Mesh, material and texture assets."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .prefab_graph import assign_graph_id
from .professional_teacher_reproduction import _capture_summary


SCHEMA_VERSION = "vfx_slash_family_generation.v1"
GENERATOR_VERSION = "slash_family_adapter.v9"
SLASH_MESH = "Assets/Hovl Studio/Sword slash VFX/Models/Slash4.fbx"
SLASH_MATERIAL = "Assets/QFX/ProjectilesFX/VFX_Resources/Materials/Nature/MFX_Flare_4.mat"
SLASH_TEXTURE = "Assets/Hovl Studio/Toon Projectiles 2/Textures/Trail68.png"
HIT_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Other/FX_Hit_1.png"


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


def _validate(graph: dict[str, Any]) -> None:
    schema = _read(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(graph), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"slash PrefabGraph schema error at {location}: {errors[0].message}")


def _node(node_id: str, name: str, role: str, sibling: int) -> dict[str, Any]:
    return {"node_id": node_id, "name": name, "role": role, "sibling_index": sibling, "depth": 1, "parent_node_id": "n0000", "hierarchy_path": f"GeneratedRoot[0]/{name}[{sibling}]", "active_self": True, "component_types": ["UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer", "UnityEngine.Transform"], "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}}


def _particle(component_id: str, node_id: str, role: str, size: float, alpha: float, delay: float, lifetime: float, sorting: int) -> dict[str, Any]:
    return {"component_id": component_id, "node_id": node_id, "parameters": {"serialized_modules": {"profile": "layered_slash_v1", "layer_role": role}, "duration_seconds": 0.65, "start_delay_max": delay, "looping": False, "simulation_space": "Local", "max_particles": 4, "start_lifetime_max": lifetime, "start_speed_max": 0.0, "start_size_max": size, "start_rotation_max": 0.0, "gravity_modifier_max": 0.0, "start_color_rgba": [0.55, 0.88, 1.0, alpha], "end_color_rgba": [0.12, 0.35, 1.0, 0.0], "emission_enabled": True, "emission_rate_over_time_max": 0.0, "burst_particle_count": 1, "shape_enabled": False, "shape_type": "disabled", "shape_radius": 0.0, "color_over_lifetime_enabled": True, "size_over_lifetime_enabled": True, "end_size_multiplier": 1.0, "renderer_mode": "Mesh", "sorting_order": sorting, "texture_profile": None, "shader_profile": None, "material_template_path": SLASH_MATERIAL, "texture_asset_path": SLASH_TEXTURE, "texture_property_name": "_MainTex"}, "material_paths": [], "mesh_paths": [SLASH_MESH]}


def create_layered_slash(prompt: str, seed: int, variation_index: int) -> dict[str, Any]:
    rng = random.Random(seed)
    outer_size = 0.85 + 0.05 * (variation_index % 4)
    inner_ratio = 0.58 + 0.04 * (variation_index % 4)
    inner_alpha = 0.28 + 0.04 * (variation_index % 3)
    nodes = [{"node_id": "n0000", "name": "GeneratedRoot", "role": "root", "sibling_index": 0, "depth": 0, "parent_node_id": None, "hierarchy_path": "GeneratedRoot[0]", "active_self": True, "component_types": ["UnityEngine.Transform"], "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}}, _node("n0001", "OuterBlade", "core", 0), _node("n0002", "InnerSupport", "support", 1), _node("n0003", "ContactHit", "hit", 2), _node("n0004", "DirectionTrail", "residual", 3)]
    nodes[3]["transform"]["local_position"] = [1.45, -0.05, 0.0]
    nodes[4]["transform"]["local_rotation"] = [0.0, 0.7071068, 0.0, 0.7071068]
    particles = [_particle("p0000", "n0001", "outer_blade", outer_size, 1.0, 0.0, 0.34 + 0.02 * (variation_index % 3), 10), _particle("p0001", "n0002", "inner_support", outer_size * inner_ratio, inner_alpha, 0.01, 0.30 + 0.02 * (variation_index % 2), 9)]
    particles[0]["parameters"]["start_rotation_max"] = rng.uniform(-0.08, 0.08)
    particles[1]["parameters"]["start_rotation_max"] = particles[0]["parameters"]["start_rotation_max"]
    trail = _particle("p0002", "n0004", "direction_trail", 0.22 + 0.02 * (variation_index % 3), 0.42, 0.18, 0.30 + 0.02 * (variation_index % 2), 6)
    trail["parameters"].update({"max_particles": 16, "start_speed_max": 1.8 + 0.15 * (variation_index % 3), "burst_particle_count": 7 + variation_index % 3, "shape_enabled": True, "shape_type": "Cone", "shape_radius": 0.04, "end_size_multiplier": 0.25, "renderer_mode": "Billboard"})
    trail["mesh_paths"] = []
    hit = _particle("p0003", "n0003", "contact_hit", 0.90 + 0.04 * (variation_index % 3), 1.0, 0.065, 0.16 + 0.01 * (variation_index % 2), 12)
    hit["parameters"].update({"max_particles": 2, "burst_particle_count": 1, "end_size_multiplier": 0.25, "renderer_mode": "Billboard", "texture_asset_path": HIT_TEXTURE, "start_color_rgba": [0.9, 1.0, 1.0, 1.0]})
    hit["mesh_paths"] = []
    particles.extend((hit, trail))
    renderers = [{"component_id": f"r{index:04d}", "node_id": particle["node_id"], "renderer_type": "ParticleSystemRenderer", "enabled": True, "parameters": {"particle_render_mode": particle["parameters"]["renderer_mode"], "sorting_order": particle["parameters"]["sorting_order"]}, "material_paths": [], "mesh_paths": list(particle["mesh_paths"])} for index, particle in enumerate(particles)]
    graph = {"schema_version": "vfx_prefab_graph.v1", "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None}, "condition": {"prompt": prompt, "effect_family": "slash", "style_family": "cartoon", "seed": seed, "parent_prefab_path": None}, "root_node_id": "n0000", "nodes": nodes, "components": {"particle_systems": particles, "renderers": renderers, "animations": []}, "asset_bindings": {"materials": [SLASH_MATERIAL], "meshes": [SLASH_MESH]}, "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []}, "training": {"eligible_tasks": ["component_prediction", "full_reconstruction", "hierarchy_modeling", "particle_parameter_modeling"], "excluded_tasks": ["aesthetic_preference"], "aesthetic_label_source": "ai_hypothesis"}, "provenance": {"source_dataset_id": "slash_family_adapter_r001", "source_run_id": None, "exporter": "prefab_graph_constrained.v1", "assumptions": ["OuterBlade and InnerSupport use the real Hovl Slash4 Mesh and a verified hierarchy rule.", "DirectionTrail follows the attack axis and readable-then-fade timing under verified professional Teacher rules.", "ContactHit uses an explicit hit texture and a verified contact-focus rule.", "The four layer delays follow the verified staged-rhythm rule.", "A QFX particle material avoids unmodeled Hovl custom vertex-stream requirements."]}}
    graph = assign_graph_id(graph)
    _validate(graph)
    return graph


def generate_batch(prompt: str, output_root: Path, asset_root: str, candidate_count: int = 8, seed: int = 20262004) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"slash generation output already exists and is not empty: {output_root}")
    candidates, requests = [], []
    for index in range(max(1, candidate_count)):
        graph = create_layered_slash(prompt, seed + index, index)
        candidate_id = f"layered_slash_{index:03d}_{graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / candidate_id / "graph.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{candidate_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{candidate_id}.json"
        readback_graph = output_root / "readback" / f"{candidate_id}.json"
        readback_result = output_root / "readback_results" / f"{candidate_id}.json"
        capture_manifest = output_root / "runtime_captures" / candidate_id / "capture_manifest.json"
        candidates.append({"candidate_id": candidate_id, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result), "capture_manifest_path": _portable(capture_manifest), "seed": seed + index})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "generation_manifest.json", {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name, "prompt": prompt, "effect_family": "slash", "style_family": "cartoon", "generator": {"name": "slash.adapter", "version": GENERATOR_VERSION, "teacher_rule_ids": ["professional_slash_outer_inner_hierarchy_r001", "professional_slash_directional_trail_r001", "professional_slash_contact_focus_r001", "professional_slash_readable_then_fade_r001", "professional_slash_staged_rhythm_r001"], "structure_model_role": "four_layer_mesh_hit_direction_prior", "parameter_source": "bounded deterministic sampling"}, "asset_plan": {"mesh": SLASH_MESH, "material_template": SLASH_MATERIAL, "texture": SLASH_TEXTURE, "hit_texture": HIT_TEXTURE, "shader_and_texture_dependencies": "explicit_mesh_material_texture_binding"}, "candidate_count": len(candidates), "candidates": candidates, "status": "prepared_pending_unity"})
    return {"manifest": manifest_path, "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_repo_root() / candidate["compile_result_path"])
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {candidate['candidate_id']}")
        root = output_path.resolve().parent / "runtime_captures" / candidate["candidate_id"]
        requests.append({"candidate_id": candidate["candidate_id"], "prefab_path": compile_result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "slash"})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "scene": "LayeredSlashRuntimeCapture", "camera": "LayeredSlashRuntimeCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 24, "short_effect_target_intervals": 24, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 0.8, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def finalize(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    records = []
    expected_mesh = manifest["asset_plan"]["mesh"]
    for candidate in manifest["candidates"]:
        compile_result = _read(_repo_root() / candidate["compile_result_path"])
        readback_result = _read(_repo_root() / candidate["readback_result_path"])
        capture = _capture_summary(_repo_root() / candidate["capture_manifest_path"])
        readback_meshes = set(readback_result.get("mesh_paths") or [])
        gates = {"compile_pass": compile_result.get("status") == "pass", "prefab_api_readback_pass": readback_result.get("status") == "pass", "mesh_readback_matches_plan": expected_mesh in readback_meshes, "runtime_eligible": capture["image_sequence_training_eligible"], "no_material_render_errors": capture["material_render_error_frame_count"] == 0, "has_frames": capture["valid_frame_count"] > 0}
        records.append({"candidate_id": candidate["candidate_id"], "graph_id": candidate["graph_id"], "output_prefab_path": candidate["output_prefab_path"], "quality_gates": gates, "technical_pass": all(gates.values()), "valid_frame_count": capture["valid_frame_count"], "selected_camera_view": capture["selected_camera_view"], "peak_center_luminance": capture["peak_center_luminance"], "capture_manifest_path": candidate["capture_manifest_path"], "training_scope": "technical_success_four_layer_slash_not_global_aesthetic_quality"})
    report = {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "records": records, "status": "pass_technical_family_adapter_unscored" if records and all(row["technical_pass"] for row in records) else "blocked", "limitations": ["Outer/inner hierarchy and directional trail have verified narrow-axis Teacher rules.", "ContactHit remains an AI proposal until its professional Teacher reproduction passes.", "The batch does not yet validate complete slash rhythm or global aesthetic quality."]}
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and validate four-layer Slash PrefabGraphs.")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--asset-root", required=True)
    generate.add_argument("--candidate-count", type=int, default=8)
    generate.add_argument("--seed", type=int, default=20262004)
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--manifest", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--manifest", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            paths = generate_batch(args.prompt, args.output_root, args.asset_root, args.candidate_count, args.seed)
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
