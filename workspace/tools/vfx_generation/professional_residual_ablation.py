"""Build same-topology Residual-off pairs for the verified explosion Teacher rule."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prefab_graph import assign_graph_id
from .professional_residual_teacher_reproduction import _early_pair_mae, _late_metrics, _non_residual_end_seconds
from .professional_teacher_guided_generation import _load_teacher_rule, _single_role_component, _validate_graph
from .professional_teacher_reproduction import _capture_summary, _paired_frame_comparison


SCHEMA_VERSION = "vfx_professional_residual_ablation_batch.v1"
RULE_ID = "professional_explosion_residual_persistence_r001"


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


def create_residual_ablation(graph: dict[str, Any], rule_id: str = RULE_ID) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "explosion":
        raise ValueError("residual ablation requires an explosion PrefabGraph")
    residual = _single_role_component(result, "particle_systems", "residual")
    parameters = residual["parameters"]
    start_color = list(parameters.get("start_color_rgba") or [1.0, 1.0, 1.0, 1.0])
    start_color[3] = 0.0
    parameters["start_color_rgba"] = start_color
    end_color = list(parameters.get("end_color_rgba") or start_color)
    end_color[3] = 0.0
    parameters["end_color_rgba"] = end_color
    modules = dict(parameters.get("serialized_modules") or {})
    modules.update({"professional_teacher_rule_id": rule_id, "ablation": "residual_alpha_zero"})
    parameters["serialized_modules"] = modules
    result.setdefault("provenance", {}).setdefault("assumptions", []).append(
        f"Residual alpha ablation for verified professional Teacher rule: {rule_id}."
    )
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, ["residual.parameters.start_color_rgba[3]"]


def prepare(source_manifest_path: Path, teacher_ready_path: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"residual ablation output already exists and is not empty: {output_root}")
    source_manifest = _read(source_manifest_path.resolve())
    teacher, report, _ = _load_teacher_rule(teacher_ready_path.resolve(), RULE_ID)
    if source_manifest.get("effect_family") != "explosion":
        raise ValueError("residual ablation source manifest must be an explosion family batch")
    candidates = []
    requests = []
    for index, source_candidate in enumerate(source_manifest["candidates"]):
        source_graph_path = _resolve(source_candidate["graph_path"])
        source_graph = _read(source_graph_path)
        ablation_graph, changed_fields = create_residual_ablation(source_graph)
        pair_id = f"layered_residual_pair_{index:03d}_{source_graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / pair_id / "residual_off_graph.json", ablation_graph)
        output_prefab = f"{asset_root.rstrip('/')}/{pair_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{pair_id}.json"
        readback_graph = output_root / "readback" / f"{pair_id}.json"
        readback_result = output_root / "readback_results" / f"{pair_id}.json"
        source_compile = _read(_resolve(source_candidate["compile_result_path"]))
        source_readback = _read(_resolve(source_candidate["readback_result_path"]))
        if source_compile.get("status") != "pass" or source_readback.get("status") != "pass":
            raise ValueError(f"source layered explosion is not technically valid: {source_candidate['candidate_id']}")
        candidates.append({
            "candidate_id": pair_id, "source_candidate_id": source_candidate["candidate_id"], "source_graph_id": source_graph["graph_id"],
            "source_graph_path": _portable(source_graph_path), "guided_graph_id": source_graph["graph_id"], "guided_graph_path": _portable(source_graph_path),
            "guided_prefab_path": source_compile["output_prefab_path"], "baseline_graph_id": ablation_graph["graph_id"], "baseline_graph_path": _portable(graph_path),
            "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result),
            "baseline_capture_manifest_path": _portable(output_root / "runtime_baselines" / pair_id / "capture_manifest.json"),
            "capture_manifest_path": _portable(output_root / "runtime_captures" / pair_id / "capture_manifest.json"),
            "late_window_start_seconds": _non_residual_end_seconds(source_graph) + 0.05, "changed_fields": changed_fields,
        })
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "guided_generation_manifest.json", {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name,
        "source_manifest_path": _portable(source_manifest_path.resolve()), "teacher_ready_path": _portable(teacher_ready_path.resolve()),
        "teacher_rule": {"record_id": RULE_ID, "effect_family": "explosion", "judgment_axes": teacher["judgment_axes"], "expert_judgment": teacher["expert_judgment"], "reproduction_report": teacher["unity_reproduction_report"], "controller_prior": report["validated_controller_prior"]},
        "candidate_count": len(candidates), "candidates": candidates, "status": "prepared_pending_unity",
    })
    compile_path = _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})
    return {"manifest": manifest_path, "compile_request": compile_path}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        ablation_compile = _read(_resolve(candidate["compile_result_path"]))
        if ablation_compile.get("status") != "pass":
            raise ValueError(f"passing Residual-off compile result required: {candidate['candidate_id']}")
        for prefab_path, root_name in ((ablation_compile["output_prefab_path"], "runtime_baselines"), (candidate["guided_prefab_path"], "runtime_captures")):
            case_root = output_path.resolve().parent / root_name / candidate["candidate_id"]
            requests.append({
                "candidate_id": candidate["source_candidate_id"], "prefab_path": prefab_path,
                "capture_dir": (case_root / "captures").as_posix(), "capture_manifest_path": (case_root / "capture_manifest.json").as_posix(),
                "material_timeline_path": (case_root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts",
                "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion",
                "forced_camera_view": "front",
            })
    return _write(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"],
        "scene": "LayeredExplosionResidualAblation", "camera": "LayeredExplosionResidualAblationCamera", "width": 512, "height": 512,
        "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 32, "short_effect_target_intervals": 32, "min_interval_seconds": 0.01, "max_interval_seconds": 0.05, "max_duration_seconds": 2.5, "include_zero": True, "duration_sources": ["particle_system"]},
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
        paired = _paired_frame_comparison(baseline, guided)
        late_start = float(candidate["late_window_start_seconds"])
        baseline_late, guided_late = _late_metrics(baseline, late_start), _late_metrics(guided, late_start)
        comparison = {
            "late_active_frame_ratio_gain": guided_late["active_frame_ratio"] - baseline_late["active_frame_ratio"],
            "late_visible_area_mean_gain": guided_late["visible_area_mean"] - baseline_late["visible_area_mean"],
            "last_visible_time_gain_seconds": guided_late["last_visible_time_seconds"] - baseline_late["last_visible_time_seconds"],
            "early_frame_max_mae": _early_pair_mae(baseline, guided, min(late_start, 0.18)),
        }
        technical_gates = {
            "residual_off_compile_pass": compile_result.get("status") == "pass",
            "residual_off_texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")),
            "residual_off_prefab_api_readback_pass": readback_result.get("status") == "pass",
            "both_runtime_eligible": baseline["image_sequence_training_eligible"] and guided["image_sequence_training_eligible"],
            "no_material_render_errors": baseline["material_render_error_frame_count"] == guided["material_render_error_frame_count"] == 0,
            "same_camera_view": bool(baseline["selected_camera_view"]) and baseline["selected_camera_view"] == guided["selected_camera_view"],
            "equal_nonzero_frame_count": baseline["valid_frame_count"] > 0 and baseline["valid_frame_count"] == guided["valid_frame_count"],
            "all_frames_matched_by_time": paired["matched_frame_count"] == baseline["valid_frame_count"] == guided["valid_frame_count"],
            "early_frames_unchanged": comparison["early_frame_max_mae"] <= 0.002,
        }
        technical_pass = all(technical_gates.values())
        rule_pass = technical_pass and comparison["late_active_frame_ratio_gain"] >= float(prior["minimum_late_active_ratio_gain"]) and comparison["late_visible_area_mean_gain"] >= float(prior["minimum_late_visible_area_gain"]) and comparison["last_visible_time_gain_seconds"] >= float(prior["minimum_last_visible_time_gain_seconds"])
        records.append({
            "candidate_id": candidate["candidate_id"], "source_candidate_id": candidate["source_candidate_id"], "guided_graph_id": candidate["guided_graph_id"],
            "technical_gates": technical_gates, "technical_pass": technical_pass, "professional_rule_transfer_pass": rule_pass,
            "late_window_start_seconds": late_start, "baseline_late_metrics": baseline_late, "guided_late_metrics": guided_late, **comparison,
            "training_eligibility": {"eligible_tasks": ["explosion_residual_rhythm_rule_controller"] if rule_pass else [], "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"], "label_scope": "relative_residual_persistence_within_verified_pair"},
        })
    report = {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "teacher_rule": manifest["teacher_rule"],
        "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records),
        "records": records, "status": "pass" if records and all(row["technical_pass"] for row in records) and all(row["professional_rule_transfer_pass"] for row in records) else "blocked",
        "training_scope": "same-topology explosion residual-persistence ablation pairs only",
    }
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build same-topology explosion Residual-off pairs.")
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
