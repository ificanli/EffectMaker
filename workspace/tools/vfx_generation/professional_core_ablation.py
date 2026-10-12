"""Create same-topology Core-off pairs for a verified explosion Teacher rule."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prefab_graph import assign_graph_id
from .professional_teacher_guided_generation import _load_teacher_rule, _single_role_component, _validate_graph
from .professional_teacher_reproduction import _capture_summary, _paired_frame_comparison


SCHEMA_VERSION = "vfx_professional_core_ablation_batch.v1"
RULE_ID = "professional_explosion_core_readability_r001"


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


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def create_core_ablation(graph: dict[str, Any], rule_id: str = RULE_ID) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "explosion":
        raise ValueError("core ablation requires an explosion PrefabGraph")
    core = _single_role_component(result, "particle_systems", "core")
    parameters = core.setdefault("parameters", {})
    start_color = list(parameters.get("start_color_rgba") or [1.0, 1.0, 1.0, 1.0])
    end_color = list(parameters.get("end_color_rgba") or start_color)
    start_color[3] = 0.0
    end_color[3] = 0.0
    parameters["start_color_rgba"] = start_color
    parameters["end_color_rgba"] = end_color
    modules = dict(parameters.get("serialized_modules") or {})
    modules.update({"professional_teacher_rule_id": rule_id, "ablation": "core_alpha_zero"})
    parameters["serialized_modules"] = modules
    result.setdefault("provenance", {}).setdefault("assumptions", []).append(
        f"Core alpha ablation for verified professional Teacher rule: {rule_id}."
    )
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, ["core.parameters.start_color_rgba[3]", "core.parameters.end_color_rgba[3]"]


def prepare(source_manifest_path: Path, teacher_ready_path: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"core ablation output already exists and is not empty: {output_root}")
    source_manifest = _read(source_manifest_path.resolve())
    teacher, report, _ = _load_teacher_rule(teacher_ready_path.resolve(), RULE_ID)
    if source_manifest.get("effect_family") != "explosion":
        raise ValueError("core ablation source manifest must be an explosion family batch")
    candidates = []
    requests = []
    for index, source_candidate in enumerate(source_manifest["candidates"]):
        source_graph_path = _resolve(source_candidate["graph_path"])
        source_graph = _read(source_graph_path)
        ablation_graph, changed_fields = create_core_ablation(source_graph)
        pair_id = f"layered_core_pair_{index:03d}_{source_graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / pair_id / "core_off_graph.json", ablation_graph)
        output_prefab = f"{asset_root.rstrip('/')}/{pair_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{pair_id}.json"
        readback_graph = output_root / "readback" / f"{pair_id}.json"
        readback_result = output_root / "readback_results" / f"{pair_id}.json"
        source_compile = _read(_resolve(source_candidate["compile_result_path"]))
        source_readback = _read(_resolve(source_candidate["readback_result_path"]))
        if source_compile.get("status") != "pass" or source_readback.get("status") != "pass":
            raise ValueError(f"source layered explosion is not technically valid: {source_candidate['candidate_id']}")
        candidates.append({
            "candidate_id": pair_id,
            "source_candidate_id": source_candidate["candidate_id"],
            "source_graph_id": source_graph["graph_id"],
            "source_graph_path": _portable(source_graph_path),
            "guided_graph_id": source_graph["graph_id"],
            "guided_graph_path": _portable(source_graph_path),
            "guided_prefab_path": source_compile["output_prefab_path"],
            "baseline_graph_id": ablation_graph["graph_id"],
            "baseline_graph_path": _portable(graph_path),
            "output_prefab_path": output_prefab,
            "compile_result_path": _portable(compile_result),
            "readback_graph_path": _portable(readback_graph),
            "readback_result_path": _portable(readback_result),
            "baseline_capture_manifest_path": _portable(output_root / "runtime_baselines" / pair_id / "capture_manifest.json"),
            "capture_manifest_path": _portable(output_root / "runtime_captures" / pair_id / "capture_manifest.json"),
            "changed_fields": changed_fields,
        })
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "guided_generation_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "source_manifest_path": _portable(source_manifest_path.resolve()),
        "teacher_ready_path": _portable(teacher_ready_path.resolve()),
        "teacher_rule": {"record_id": RULE_ID, "effect_family": "explosion", "judgment_axes": teacher["judgment_axes"], "expert_judgment": teacher["expert_judgment"], "reproduction_report": teacher["unity_reproduction_report"], "controller_prior": report["validated_controller_prior"]},
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
        ablation_compile = _read(_resolve(candidate["compile_result_path"]))
        if ablation_compile.get("status") != "pass":
            raise ValueError(f"passing Core-off compile result required: {candidate['candidate_id']}")
        for variant, prefab_path, root_name in (
            ("baseline", ablation_compile["output_prefab_path"], "runtime_baselines"),
            ("guided", candidate["guided_prefab_path"], "runtime_captures"),
        ):
            case_root = output_path.resolve().parent / root_name / candidate["candidate_id"]
            requests.append({
                "candidate_id": candidate["source_candidate_id"], "prefab_path": prefab_path,
                "capture_dir": (case_root / "captures").as_posix(), "capture_manifest_path": (case_root / "capture_manifest.json").as_posix(),
                "material_timeline_path": (case_root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts",
                "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion",
                "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 1.5,
            })
    return _write(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"],
        "scene": "LayeredExplosionCoreAblation", "camera": "LayeredExplosionCoreAblationCamera", "width": 640, "height": 640,
        "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 0.8, "include_zero": True, "duration_sources": ["particle_system"]},
        "capture_material_timeline": True, "requests": requests,
    })


def finalize(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    prior = manifest["teacher_rule"]["controller_prior"]
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        readback_result = _read(_resolve(candidate["readback_result_path"]))
        baseline = _capture_summary(_resolve(candidate["baseline_capture_manifest_path"]))
        guided = _capture_summary(_resolve(candidate["capture_manifest_path"]))
        comparison = _paired_frame_comparison(baseline, guided)
        technical_gates = {
            "core_off_compile_pass": compile_result.get("status") == "pass",
            "core_off_texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")),
            "core_off_prefab_api_readback_pass": readback_result.get("status") == "pass",
            "both_runtime_eligible": baseline["image_sequence_training_eligible"] and guided["image_sequence_training_eligible"],
            "no_material_render_errors": baseline["material_render_error_frame_count"] == guided["material_render_error_frame_count"] == 0,
            "same_camera_view": bool(baseline["selected_camera_view"]) and baseline["selected_camera_view"] == guided["selected_camera_view"],
            "equal_nonzero_frame_count": baseline["valid_frame_count"] > 0 and baseline["valid_frame_count"] == guided["valid_frame_count"],
            "all_frames_matched_by_time": comparison["matched_frame_count"] == baseline["valid_frame_count"] == guided["valid_frame_count"],
        }
        technical_pass = all(technical_gates.values())
        rule_pass = technical_pass and comparison["peak_center_luminance_gain"] >= float(prior["minimum_center_luminance_gain"]) and comparison["peak_center_local_contrast_gain"] >= float(prior["minimum_center_local_contrast_gain"])
        records.append({
            "candidate_id": candidate["candidate_id"], "source_candidate_id": candidate["source_candidate_id"], "guided_graph_id": candidate["guided_graph_id"],
            "technical_gates": technical_gates, "technical_pass": technical_pass, "professional_rule_transfer_pass": rule_pass,
            "peak_center_luminance_gain": comparison["peak_center_luminance_gain"], "peak_center_local_contrast_gain": comparison["peak_center_local_contrast_gain"],
            "best_time_seconds": comparison["best_time_seconds"], "best_baseline_frame_path": comparison["best_empty_frame_path"], "best_guided_frame_path": comparison["best_reinforced_frame_path"],
            "training_eligibility": {"eligible_tasks": ["explosion_core_rule_controller"] if rule_pass else [], "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"], "label_scope": "relative_core_readability_within_verified_pair"},
        })
    report = {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "teacher_rule": manifest["teacher_rule"],
        "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records),
        "records": records, "status": "pass" if records and all(row["technical_pass"] for row in records) and all(row["professional_rule_transfer_pass"] for row in records) else "blocked",
        "training_scope": "same-topology explosion core-readability ablation pairs only",
    }
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build same-topology explosion Core-off pairs.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--source-manifest", type=Path, required=True)
    build.add_argument("--teacher-ready", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--asset-root", required=True)
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--manifest", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--manifest", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            paths = prepare(args.source_manifest, args.teacher_ready, args.output_root, args.asset_root)
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
