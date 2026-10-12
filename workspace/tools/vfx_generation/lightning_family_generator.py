"""Generate layered lightning PrefabGraphs with audited project assets."""

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


SCHEMA_VERSION = "vfx_lightning_family_generation.v1"
GENERATOR_VERSION = "lightning_family_adapter.v4"
LIGHTNING_MATERIAL = "Assets/QFX/ProjectilesFX/VFX_Resources/Materials/Nature/MFX_Flare_4.mat"
MAIN_BOLT_TEXTURE = "Assets/Epic Toon FX/Textures/lightning2.png"
BRANCH_TEXTURE = "Assets/Epic Toon FX/Textures/lightning1.png"
HIT_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Other/FX_Hit_1.png"
SPARK_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Other/FX_Spark_1.png"


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
        raise ValueError(f"lightning PrefabGraph schema error at {location}: {errors[0].message}")


def _node(node_id: str, name: str, role: str, sibling: int, position: list[float] | None = None) -> dict[str, Any]:
    return {"node_id": node_id, "name": name, "role": role, "sibling_index": sibling, "depth": 1, "parent_node_id": "n0000", "hierarchy_path": f"GeneratedRoot[0]/{name}[{sibling}]", "active_self": True, "component_types": ["UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer", "UnityEngine.Transform"], "transform": {"local_position": position or [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}}


def _particle(component_id: str, node_id: str, layer_role: str, texture: str, size: float, alpha: float, delay: float, lifetime: float, sorting: int) -> dict[str, Any]:
    return {"component_id": component_id, "node_id": node_id, "parameters": {"serialized_modules": {"profile": "layered_lightning_v1", "layer_role": layer_role}, "duration_seconds": 0.55, "start_delay_max": delay, "looping": False, "simulation_space": "Local", "max_particles": 16, "start_lifetime_max": lifetime, "start_speed_max": 0.0, "start_size_max": size, "start_rotation_max": 0.0, "gravity_modifier_max": 0.0, "start_color_rgba": [0.55, 0.9, 1.0, alpha], "end_color_rgba": [0.12, 0.32, 1.0, 0.0], "emission_enabled": True, "emission_rate_over_time_max": 0.0, "burst_particle_count": 1, "shape_enabled": False, "shape_type": "disabled", "shape_radius": 0.0, "color_over_lifetime_enabled": True, "size_over_lifetime_enabled": True, "end_size_multiplier": 0.2, "renderer_mode": "Billboard", "sorting_order": sorting, "texture_profile": None, "shader_profile": None, "material_template_path": LIGHTNING_MATERIAL, "texture_asset_path": texture, "texture_property_name": "_MainTex"}, "material_paths": [], "mesh_paths": []}


def create_layered_lightning(prompt: str, seed: int, variation_index: int) -> dict[str, Any]:
    rng = random.Random(seed)
    nodes = [
        {"node_id": "n0000", "name": "GeneratedRoot", "role": "root", "sibling_index": 0, "depth": 0, "parent_node_id": None, "hierarchy_path": "GeneratedRoot[0]", "active_self": True, "component_types": ["UnityEngine.Transform"], "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]}},
        _node("n0001", "MainBolt", "core", 0),
        _node("n0002", "BranchSupport", "support", 1),
        _node("n0003", "ImpactFlash", "hit", 2, [1.35, 0.0, 0.0]),
        _node("n0004", "ResidualSpark", "residual", 3, [1.3, 0.0, 0.0]),
    ]
    main = _particle("p0000", "n0001", "main_bolt", MAIN_BOLT_TEXTURE, 2.5 + 0.08 * (variation_index % 3), 1.0, 0.0, 0.14 + 0.01 * (variation_index % 2), 10)
    support = _particle("p0001", "n0002", "branch_support", BRANCH_TEXTURE, 1.55 + 0.04 * (variation_index % 4), 0.38, 0.015, 0.13, 9)
    support["parameters"].update({"burst_particle_count": 2, "start_rotation_max": rng.uniform(-0.45, 0.45), "end_size_multiplier": 0.65})
    hit = _particle("p0002", "n0003", "impact_flash", HIT_TEXTURE, 0.72 + 0.04 * (variation_index % 3), 1.0, 0.07, 0.12, 12)
    hit["parameters"].update({"start_color_rgba": [0.88, 0.98, 1.0, 1.0], "end_size_multiplier": 0.25})
    residual = _particle("p0003", "n0004", "residual_spark", SPARK_TEXTURE, 0.16 + 0.01 * (variation_index % 3), 0.48, 0.12, 0.24 + 0.02 * (variation_index % 2), 7)
    residual["parameters"].update({"max_particles": 24, "start_speed_max": 1.3 + 0.1 * (variation_index % 3), "burst_particle_count": 7 + variation_index % 3, "shape_enabled": True, "shape_type": "Cone", "shape_radius": 0.06})
    particles = [main, support, hit, residual]
    renderers = [{"component_id": f"r{index:04d}", "node_id": particle["node_id"], "renderer_type": "ParticleSystemRenderer", "enabled": True, "parameters": {"particle_render_mode": "Billboard", "sorting_order": particle["parameters"]["sorting_order"]}, "material_paths": [], "mesh_paths": []} for index, particle in enumerate(particles)]
    graph = {"schema_version": "vfx_prefab_graph.v1", "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None}, "condition": {"prompt": prompt, "effect_family": "lightning", "style_family": "stylized", "seed": seed, "parent_prefab_path": None}, "root_node_id": "n0000", "nodes": nodes, "components": {"particle_systems": particles, "renderers": renderers, "animations": []}, "asset_bindings": {"materials": [LIGHTNING_MATERIAL], "meshes": []}, "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []}, "training": {"eligible_tasks": ["component_prediction", "full_reconstruction", "hierarchy_modeling", "particle_parameter_modeling"], "excluded_tasks": ["aesthetic_preference"], "aesthetic_label_source": "ai_hypothesis"}, "provenance": {"source_dataset_id": "lightning_family_adapter_r001", "source_run_id": None, "exporter": "prefab_graph_constrained.v1", "assumptions": ["MainBolt, BranchSupport, ImpactFlash and ResidualSpark use independent particle roles.", "All textures and the material template are existing audited EffectDemo assets.", "The topology is a technical hypothesis until professional lightning Teacher reproduction passes."]}}
    graph = assign_graph_id(graph)
    _validate(graph)
    return graph


def generate_batch(prompt: str, output_root: Path, asset_root: str, candidate_count: int = 8, seed: int = 20262400) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"lightning generation output already exists and is not empty: {output_root}")
    candidates, requests = [], []
    for index in range(max(1, candidate_count)):
        graph = create_layered_lightning(prompt, seed + index, index)
        candidate_id = f"layered_lightning_{index:03d}_{graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / candidate_id / "graph.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{candidate_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{candidate_id}.json"
        readback_graph = output_root / "readback" / f"{candidate_id}.json"
        readback_result = output_root / "readback_results" / f"{candidate_id}.json"
        capture_manifest = output_root / "runtime_captures" / candidate_id / "capture_manifest.json"
        candidates.append({"candidate_id": candidate_id, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result), "capture_manifest_path": _portable(capture_manifest), "seed": seed + index})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "generation_manifest.json", {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name, "prompt": prompt, "effect_family": "lightning", "style_family": "stylized", "generator": {"name": "lightning.adapter", "version": GENERATOR_VERSION, "teacher_rule_ids": ["professional_lightning_main_branch_hierarchy_r001", "professional_lightning_impact_focus_r001", "professional_lightning_instant_pulse_r001"], "structure_model_role": "four_layer_bolt_branch_hit_residual_hypothesis", "parameter_source": "bounded deterministic sampling"}, "asset_plan": {"material_template": LIGHTNING_MATERIAL, "main_bolt_texture": MAIN_BOLT_TEXTURE, "branch_texture": BRANCH_TEXTURE, "hit_texture": HIT_TEXTURE, "spark_texture": SPARK_TEXTURE, "shader_and_texture_dependencies": "explicit_material_texture_binding"}, "candidate_count": len(candidates), "candidates": candidates, "status": "prepared_pending_unity"})
    return {"manifest": manifest_path, "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_repo_root() / candidate["compile_result_path"])
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {candidate['candidate_id']}")
        root = output_path.resolve().parent / "runtime_captures" / candidate["candidate_id"]
        requests.append({"candidate_id": candidate["candidate_id"], "prefab_path": compile_result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "lightning"})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "scene": "LayeredLightningRuntimeCapture", "camera": "LayeredLightningRuntimeCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 24, "short_effect_target_intervals": 24, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 0.6, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def finalize(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_repo_root() / candidate["compile_result_path"])
        readback_result = _read(_repo_root() / candidate["readback_result_path"])
        capture = _capture_summary(_repo_root() / candidate["capture_manifest_path"])
        gates = {"compile_pass": compile_result.get("status") == "pass", "prefab_api_readback_pass": readback_result.get("status") == "pass", "runtime_eligible": capture["image_sequence_training_eligible"], "no_material_render_errors": capture["material_render_error_frame_count"] == 0, "has_frames": capture["valid_frame_count"] > 0}
        records.append({"candidate_id": candidate["candidate_id"], "graph_id": candidate["graph_id"], "output_prefab_path": candidate["output_prefab_path"], "quality_gates": gates, "technical_pass": all(gates.values()), "valid_frame_count": capture["valid_frame_count"], "selected_camera_view": capture["selected_camera_view"], "peak_center_luminance": capture["peak_center_luminance"], "capture_manifest_path": candidate["capture_manifest_path"], "training_scope": "technical_success_four_layer_lightning_ai_hypothesis"})
    return _write(output_path.resolve(), {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "records": records, "status": "pass_technical_family_adapter_unscored" if records and all(row["technical_pass"] for row in records) else "blocked", "limitations": ["The four-layer lightning topology is an AI hypothesis until professional Teacher reproduction passes.", "Technical visibility is not aesthetic quality."]})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and validate four-layer Lightning PrefabGraphs.")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--asset-root", required=True)
    generate.add_argument("--candidate-count", type=int, default=8)
    generate.add_argument("--seed", type=int, default=20262400)
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
