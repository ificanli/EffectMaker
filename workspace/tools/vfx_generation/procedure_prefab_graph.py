"""Compile a verified tutorial procedure into an asset-neutral PrefabGraph proposal."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .material_plan import apply_material_plan, load_registry
from .prefab_graph import assign_graph_id
from .professional_teacher_reproduction import _capture_summary
from .procedure_spec import validate_procedure_spec
from .proposal_asset_router import build_proposal_asset_plan
from .proposal_plan import parse_prompt_intent
from .prompt_execution_controls import apply_prompt_controls


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


def _parameter(step_rows: list[dict[str, Any]], name: str, default: Any) -> Any:
    for step in step_rows:
        for parameter in step.get("parameter_ranges") or []:
            if parameter.get("name") != name:
                continue
            if parameter.get("value") is not None:
                return parameter["value"]
            minimum = parameter.get("minimum")
            maximum = parameter.get("maximum")
            if minimum is not None and maximum is not None:
                return (float(minimum) + float(maximum)) * 0.5
    return default


def _has_parameter(step_rows: list[dict[str, Any]], name: str) -> bool:
    return any(parameter.get("name") == name for step in step_rows for parameter in step.get("parameter_ranges") or [])


def _color(value: Any) -> list[float]:
    if not isinstance(value, str) or len(value) not in {7, 9} or not value.startswith("#"):
        return [1.0, 1.0, 1.0, 1.0]
    encoded = value[1:] + ("FF" if len(value) == 7 else "")
    return [round(int(encoded[index:index + 2], 16) / 255.0, 6) for index in range(0, 8, 2)]


def _node(node_id: str, name: str, role: str, sibling: int) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "name": name,
        "role": role,
        "sibling_index": sibling,
        "depth": 1,
        "parent_node_id": "n0000",
        "hierarchy_path": f"GeneratedRoot[0]/{name}[{sibling}]",
        "active_self": True,
        "component_types": ["UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer", "UnityEngine.Transform"],
        "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]},
    }


def build_procedure_prefab_graph(spec: dict[str, Any], prompt: str, effect_family: str, seed: int) -> dict[str, Any]:
    return build_procedure_execution(spec, prompt, effect_family, seed)[0]


def build_procedure_execution(spec: dict[str, Any], prompt: str, effect_family: str, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_procedure_spec(spec)
    if effect_family not in spec["applicability"]["effect_families"]:
        raise ValueError(f"ProcedureSpec {spec['procedure_id']} does not apply to {effect_family}")
    intent = parse_prompt_intent(prompt, effect_family)
    layer_sequence = spec["output_contract"]["layer_sequence"]
    layer_roles = spec["output_contract"]["layer_roles"]
    steps_by_layer: dict[str, list[dict[str, Any]]] = {}
    for step in spec["steps"]:
        steps_by_layer.setdefault(step["target_layer"], []).append(step)
    rng = random.Random(seed)
    nodes = [{
        "node_id": "n0000",
        "name": "GeneratedRoot",
        "role": "root",
        "sibling_index": 0,
        "depth": 0,
        "parent_node_id": None,
        "hierarchy_path": "GeneratedRoot[0]",
        "active_self": True,
        "component_types": ["UnityEngine.Transform"],
        "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]},
    }]
    particles = []
    renderers = []
    for index, layer_name in enumerate(layer_sequence, start=1):
        if layer_name not in layer_roles:
            raise ValueError(f"ProcedureSpec layer role is missing: {layer_name}")
        role = layer_roles[layer_name]
        layer_steps = steps_by_layer.get(layer_name, [])
        if not layer_steps:
            raise ValueError(f"ProcedureSpec has no executable step for layer: {layer_name}")
        duration = float(_parameter(layer_steps, "duration_seconds", 0.8))
        delay = float(_parameter(layer_steps, "start_delay_seconds", 0.0))
        lifetime = float(_parameter(layer_steps, "start_lifetime_seconds", max(0.1, duration * 0.5)))
        speed = float(_parameter(layer_steps, "start_speed", 0.0))
        size = float(_parameter(layer_steps, "start_size", 0.25))
        size_3d = any(_has_parameter(layer_steps, name) for name in ("start_size_x", "start_size_y", "start_size_z"))
        size_x = float(_parameter(layer_steps, "start_size_x", size))
        size_y = float(_parameter(layer_steps, "start_size_y", size))
        size_z = float(_parameter(layer_steps, "start_size_z", size))
        burst = max(1, int(round(float(_parameter(layer_steps, "burst_count", 1)))))
        shape_type = str(_parameter(layer_steps, "shape_type", "disabled"))
        start_color = _color(_parameter(layer_steps, "color", "#FFFFFFFF"))
        lifetime_gradient = _parameter(layer_steps, "color_over_lifetime_gradient", {
            "mode": str(_parameter(layer_steps, "gradient_mode", "Blend")),
            "color_keys": [{"time": 0.0, "rgb": [1.0, 1.0, 1.0]}, {"time": 1.0, "rgb": [1.0, 1.0, 1.0]}],
            "alpha_keys": [{"time": 0.0, "alpha": 1.0}, {"time": 1.0, "alpha": 0.0}],
        })
        node_id = f"n{index:04d}"
        component_id = f"p{index - 1:04d}"
        nodes.append(_node(node_id, layer_name, role, index - 1))
        end_size = float(_parameter(layer_steps, "end_size_multiplier", {"core": 0.15, "support": 0.35, "hit": 0.1, "residual": 0.55}[role]))
        start_rotation = float(_parameter(layer_steps, "start_rotation_radians", rng.uniform(0.0, 6.283185307179586)))
        particle = {
            "component_id": component_id,
            "node_id": node_id,
            "parameters": {
                "serialized_modules": {
                    "profile": "tutorial_procedure_particle_v1",
                    "layer_role": role,
                    "procedure_id": spec["procedure_id"],
                    "procedure_step_ids": [step["step_id"] for step in layer_steps],
                },
                "duration_seconds": max(0.05, duration),
                "start_delay_max": max(0.0, delay),
                "looping": False,
                "simulation_space": "Local",
                "max_particles": max(16, burst * 2),
                "start_lifetime_max": max(0.01, lifetime),
                "start_speed_max": speed,
                "start_size_max": max(0.001, size * rng.uniform(0.96, 1.04)),
                "start_size_3d": size_3d,
                "start_size_x_max": max(0.001, size_x),
                "start_size_y_max": max(0.001, size_y),
                "start_size_z_max": max(0.001, size_z),
                "start_rotation_max": start_rotation,
                "gravity_modifier_max": 0.0,
                "start_color_rgba": start_color,
                "end_color_rgba": list(lifetime_gradient["color_keys"][-1]["rgb"]) + [lifetime_gradient["alpha_keys"][-1]["alpha"]],
                "color_over_lifetime_gradient": lifetime_gradient,
                "material_color_mode": "preserve_template",
                "emission_enabled": True,
                "emission_rate_over_time_max": 0.0,
                "burst_particle_count": burst,
                "shape_enabled": shape_type != "disabled",
                "shape_type": shape_type,
                "shape_radius": 0.35 if shape_type != "disabled" else 0.0,
                "color_over_lifetime_enabled": True,
                "size_over_lifetime_enabled": True,
                "end_size_multiplier": end_size,
                "renderer_mode": "Billboard",
                "sorting_order": {"core": 12, "support": 8, "hit": 10, "residual": 4}[role],
                "texture_profile": None,
                "shader_profile": None,
                "material_template_path": None,
                "texture_asset_path": None,
                "texture_property_name": None,
            },
            "material_paths": [],
            "mesh_paths": [],
        }
        particles.append(particle)
        renderers.append({
            "component_id": f"r{index - 1:04d}",
            "node_id": node_id,
            "renderer_type": "ParticleSystemRenderer",
            "enabled": True,
            "parameters": {"particle_render_mode": "Billboard", "sorting_order": particle["parameters"]["sorting_order"], "active_vertex_streams": ["Position", "Color", "UV"]},
            "material_paths": [],
            "mesh_paths": [],
        })
    graph = {
        "schema_version": "vfx_prefab_graph.v1",
        "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None},
        "condition": {"prompt": prompt, "effect_family": effect_family, "style_family": intent["style_family"], "seed": seed, "parent_prefab_path": None},
        "root_node_id": "n0000",
        "nodes": nodes,
        "components": {"particle_systems": particles, "renderers": renderers, "animations": []},
        "asset_bindings": {"materials": [], "meshes": []},
        "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []},
        "training": {"eligible_tasks": ["component_prediction", "hierarchy_modeling", "particle_parameter_modeling", "full_reconstruction"], "excluded_tasks": ["aesthetic_preference", "prompt_condition"], "aesthetic_label_source": "ai_hypothesis"},
        "provenance": {
            "source_dataset_id": "tutorial_procedure_generation_r001",
            "source_run_id": spec["procedure_id"],
            "exporter": "prefab_graph_constrained.v1",
            "assumptions": [
                "Layer order and bounded parameters come from a traceable ProcedureSpec.",
                "Material, Shader and Texture remain unbound until contract-aware asset routing passes.",
                "Technical execution does not imply professional visual acceptance.",
            ],
        },
    }
    graph, control_report = apply_prompt_controls(graph, prompt)
    control_report["inferred_parameter_step_ids"] = [step["step_id"] for step in spec["steps"] if step["evidence_status"] == "inferred" and step["parameter_ranges"]]
    graph = assign_graph_id(graph)
    schema = json.loads((_repo_root() / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(graph), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"procedure PrefabGraph schema error at {location}: {errors[0].message}")
    return graph, control_report


def generate_procedure_candidate(
    procedure_path: Path,
    registry_root: Path,
    prompt: str,
    effect_family: str,
    seed: int,
    output_root: Path,
    asset_root: str,
) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"procedure generation output already exists and is not empty: {output_root}")
    procedure = _read(procedure_path.resolve())
    registry = load_registry(registry_root.resolve())
    from .proposal_plan import build_proposal_plan

    proposal = build_proposal_plan(prompt, effect_family, seed, procedure_specs=[procedure])
    asset_neutral, control_report = build_procedure_execution(procedure, prompt, effect_family, seed)
    material_plan = build_proposal_asset_plan(asset_neutral, registry, proposal)
    if material_plan["status"] != "pass":
        raise ValueError("procedure asset routing is blocked")
    graph = apply_material_plan(asset_neutral, material_plan)
    candidate_id = f"tutorial_{effect_family}_{graph['graph_id']}"
    proposal_path = _write(output_root / "proposal_plan.json", proposal)
    procedure_snapshot_path = _write(output_root / "procedure_snapshot.json", procedure)
    neutral_path = _write(output_root / "asset_neutral_graph.json", asset_neutral)
    control_path = _write(output_root / "execution_control_report.json", control_report)
    material_plan_path = _write(output_root / "material_plan.json", material_plan)
    graph_path = _write(output_root / "candidates" / candidate_id / "graph.json", graph)
    output_prefab_path = f"{asset_root.rstrip('/')}/{candidate_id}/GeneratedRoot.prefab"
    compile_result_path = output_root / "compile_results" / f"{candidate_id}.json"
    compile_request_path = _write(output_root / "compile_request.json", {
        "schema_version": "vfx_prefab_graph_batch_compile_request.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requests": [{"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab_path, "result_path": compile_result_path.as_posix()}],
    })
    manifest_path = _write(output_root / "generation_manifest.json", {
        "schema_version": "vfx_tutorial_guided_generation.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "prompt": prompt,
        "effect_family": effect_family,
        "procedure_id": procedure["procedure_id"],
        "procedure_path": _portable(procedure_path),
        "procedure_snapshot_path": _portable(procedure_snapshot_path),
        "proposal_plan_path": _portable(proposal_path),
        "asset_neutral_graph_path": _portable(neutral_path),
        "execution_control_report_path": _portable(control_path),
        "material_plan_path": _portable(material_plan_path),
        "candidate": {
            "candidate_id": candidate_id,
            "graph_id": graph["graph_id"],
            "graph_path": _portable(graph_path),
            "output_prefab_path": output_prefab_path,
            "compile_result_path": _portable(compile_result_path),
            "seed": seed,
        },
        "training_eligibility": {
            "controller_sft": False,
            "positive_generation_supervision": False,
            "procedure_retrieval": True,
            "reason": "Target-project Unity reproduction and professional visual acceptance are pending.",
        },
        "status": "prepared_for_target_project_reproduction",
    })
    return {
        "manifest": manifest_path,
        "proposal_plan": proposal_path,
        "execution_control_report": control_path,
        "material_plan": material_plan_path,
        "graph": graph_path,
        "compile_request": compile_request_path,
    }


def prepare_runtime(
    manifest_path: Path,
    output_path: Path,
    *,
    capture_variant: str = "runtime_capture",
    forced_camera_view: str | None = None,
    forced_orthographic_size: float = 0.0,
) -> Path:
    manifest = _read(manifest_path.resolve())
    candidate = manifest["candidate"]
    compile_result = _read(_repo_root() / candidate["compile_result_path"])
    if compile_result.get("status") != "pass":
        raise ValueError("passing Unity compile result required before runtime capture")
    runtime_root = output_path.resolve().parent / capture_variant
    request = {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "scene": "TutorialProcedureRuntimeCapture",
        "camera": "TutorialProcedureRuntimeCamera",
        "width": 640,
        "height": 640,
        "sampling_mode": "adaptive_runtime",
        "sampling": {
            "target_intervals": 32,
            "short_effect_target_intervals": 24,
            "min_interval_seconds": 0.02,
            "max_interval_seconds": 0.1,
            "max_duration_seconds": 3.2,
            "include_zero": True,
            "duration_sources": ["particle_system"],
        },
        "capture_material_timeline": True,
        "requests": [{
            "candidate_id": candidate["candidate_id"],
            "prefab_path": compile_result["output_prefab_path"],
            "capture_dir": (runtime_root / "captures").as_posix(),
            "capture_manifest_path": (runtime_root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (runtime_root / "material_timeline.json").as_posix(),
            "source_script_fidelity": "generated_from_tutorial_procedure",
            "ignored_script_dependency_count": 0,
            "missing_script_count": 0,
            "capture_category": manifest["effect_family"],
            "forced_camera_view": forced_camera_view,
            "force_orthographic": forced_orthographic_size > 0.0,
            "forced_orthographic_size": max(0.0, forced_orthographic_size),
        }],
    }
    return _write(output_path.resolve(), request)


def finalize_reproduction(manifest_path: Path, output_path: Path, capture_manifest_path: Path | None = None) -> Path:
    manifest = _read(manifest_path.resolve())
    candidate = manifest["candidate"]
    compile_result = _read(_repo_root() / candidate["compile_result_path"])
    run_root = manifest_path.resolve().parent
    readback_result_path = run_root / "readback_results" / f"{candidate['candidate_id']}.json"
    capture_manifest_path = capture_manifest_path.resolve() if capture_manifest_path is not None else run_root / "runtime_capture" / "capture_manifest.json"
    readback = _read(readback_result_path)
    capture = _capture_summary(capture_manifest_path)
    gates = {
        "compile_pass": compile_result.get("status") == "pass",
        "prefab_api_readback_pass": readback.get("status") == "pass" and not readback.get("differences"),
        "runtime_eligible": capture["image_sequence_training_eligible"],
        "has_frames": capture["valid_frame_count"] > 0,
        "no_material_render_errors": capture["material_render_error_frame_count"] == 0,
    }
    technical_pass = all(gates.values())
    report = {
        "schema_version": "vfx_tutorial_reproduction_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "procedure_id": manifest["procedure_id"],
        "candidate_id": candidate["candidate_id"],
        "prefab_path": candidate["output_prefab_path"],
        "quality_gates": gates,
        "valid_frame_count": capture["valid_frame_count"],
        "selected_camera_view": capture["selected_camera_view"],
        "peak_center_luminance": capture["peak_center_luminance"],
        "target_project_reproduction_status": "verified" if technical_pass else "blocked",
        "visual_quality_status": "pending",
        "training_eligibility": {
            "procedure_retrieval": True,
            "planner_constraint": technical_pass,
            "controller_sft": False,
            "positive_generation_supervision": False,
            "reason": "Technical target-project reproduction passed; professional visual acceptance remains pending." if technical_pass else "Target-project technical reproduction failed.",
        },
        "status": "technical_reproduction_pass_visual_pending" if technical_pass else "blocked",
    }
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an asset-routed PrefabGraph from a tutorial ProcedureSpec.")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--procedure", type=Path, required=True)
    generate.add_argument("--registry", type=Path, required=True)
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--effect-family", required=True)
    generate.add_argument("--seed", type=int, default=0)
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--asset-root", required=True)
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--manifest", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    runtime.add_argument("--capture-variant", default="runtime_capture")
    runtime.add_argument("--forced-camera-view")
    runtime.add_argument("--forced-orthographic-size", type=float, default=0.0)
    finish = commands.add_parser("finalize")
    finish.add_argument("--manifest", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    finish.add_argument("--capture-manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            paths = generate_procedure_candidate(args.procedure, args.registry, args.prompt, args.effect_family, args.seed, args.output_root, args.asset_root)
        elif args.command == "prepare-runtime":
            paths = {"runtime_request": prepare_runtime(args.manifest, args.output, capture_variant=args.capture_variant, forced_camera_view=args.forced_camera_view, forced_orthographic_size=args.forced_orthographic_size)}
        else:
            paths = {"report": finalize_reproduction(args.manifest, args.output, args.capture_manifest)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
