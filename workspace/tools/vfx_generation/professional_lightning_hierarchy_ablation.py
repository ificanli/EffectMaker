"""Build same-topology equal/dominant lightning hierarchy pairs."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .prefab_graph import assign_graph_id
from .professional_lightning_hierarchy_teacher_reproduction import _graph_comparison, _summary
from .professional_teacher_guided_generation import _load_teacher_rule, _single_role_component, _validate_graph


SCHEMA_VERSION = "vfx_professional_lightning_hierarchy_ablation_batch.v1"
RULE_ID = "professional_lightning_main_branch_hierarchy_r001"


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


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def create_equal_branch_ablation(graph: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "lightning":
        raise ValueError("lightning hierarchy ablation requires a lightning PrefabGraph")
    main = _single_role_component(result, "particle_systems", "core")
    branch = _single_role_component(result, "particle_systems", "support")
    branch["parameters"]["start_size_max"] = float(main["parameters"]["start_size_max"])
    color = list(branch["parameters"]["start_color_rgba"])
    color[3] = float(main["parameters"]["start_color_rgba"][3])
    branch["parameters"]["start_color_rgba"] = color
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, ["support.parameters.start_size_max", "support.parameters.start_color_rgba[3]"]


def _paired_visual_metrics(equal: dict[str, Any], dominant: dict[str, Any]) -> dict[str, float]:
    equal_by_time = {round(float(row["time_seconds"]), 6): row for row in equal["frames"]}
    dominant_by_time = {round(float(row["time_seconds"]), 6): row for row in dominant["frames"]}
    reductions = []
    retentions = []
    for time_seconds in sorted(set(equal_by_time) & set(dominant_by_time)):
        left, right = equal_by_time[time_seconds], dominant_by_time[time_seconds]
        if float(left["visible_area_ratio"]) <= 0.00005:
            continue
        reductions.append(float(left["high_luma_width_ratio"]) - float(right["high_luma_width_ratio"]))
        if float(left["visible_width_ratio"]) > 0.0:
            retentions.append(float(right["visible_width_ratio"]) / float(left["visible_width_ratio"]))
    return {
        "paired_frame_count": float(len(reductions)),
        "paired_max_high_luma_width_reduction": max(reductions, default=0.0),
        "paired_median_visible_width_retained": float(np.median(retentions)) if retentions else 0.0,
    }


def prepare(source_manifest_path: Path, teacher_ready_path: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"lightning hierarchy ablation output already exists and is not empty: {output_root}")
    source_manifest = _read(source_manifest_path.resolve())
    teacher, report, _ = _load_teacher_rule(teacher_ready_path.resolve(), RULE_ID)
    if source_manifest.get("effect_family") != "lightning":
        raise ValueError("lightning hierarchy ablation source manifest must be a lightning family batch")
    candidates, requests = [], []
    for index, source_candidate in enumerate(source_manifest["candidates"]):
        source_graph_path = _resolve(source_candidate["graph_path"])
        dominant_graph = _read(source_graph_path)
        equal_graph, changed_fields = create_equal_branch_ablation(dominant_graph)
        pair_id = f"lightning_hierarchy_pair_{index:03d}_{dominant_graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / pair_id / "equal_graph.json", equal_graph)
        output_prefab = f"{asset_root.rstrip('/')}/{pair_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{pair_id}.json"
        readback_graph = output_root / "readback" / f"{pair_id}.json"
        readback_result = output_root / "readback_results" / f"{pair_id}.json"
        source_compile = _read(_resolve(source_candidate["compile_result_path"]))
        source_readback = _read(_resolve(source_candidate["readback_result_path"]))
        if source_compile.get("status") != "pass" or source_readback.get("status") != "pass":
            raise ValueError(f"source lightning is not technically valid: {source_candidate['candidate_id']}")
        candidates.append({"candidate_id": pair_id, "source_candidate_id": source_candidate["candidate_id"], "guided_graph_id": dominant_graph["graph_id"], "guided_graph_path": _portable(source_graph_path), "guided_prefab_path": source_compile["output_prefab_path"], "baseline_graph_id": equal_graph["graph_id"], "baseline_graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result), "baseline_capture_manifest_path": _portable(output_root / "runtime_baselines" / pair_id / "capture_manifest.json"), "capture_manifest_path": _portable(output_root / "runtime_captures" / pair_id / "capture_manifest.json"), "changed_fields": changed_fields})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "guided_generation_manifest.json", {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name, "source_manifest_path": _portable(source_manifest_path.resolve()), "teacher_ready_path": _portable(teacher_ready_path.resolve()), "teacher_rule": {"record_id": RULE_ID, "effect_family": "lightning", "judgment_axes": teacher["judgment_axes"], "expert_judgment": teacher["expert_judgment"], "reproduction_report": teacher["unity_reproduction_report"], "controller_prior": report["validated_controller_prior"]}, "candidate_count": len(candidates), "candidates": candidates, "status": "prepared_pending_unity"})
    return {"manifest": manifest_path, "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing equal-layer compile result required: {candidate['candidate_id']}")
        for prefab_path, root_name in ((compile_result["output_prefab_path"], "runtime_baselines"), (candidate["guided_prefab_path"], "runtime_captures")):
            root = output_path.resolve().parent / root_name / candidate["candidate_id"]
            requests.append({"candidate_id": candidate["source_candidate_id"], "prefab_path": prefab_path, "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "lightning", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 2.2})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "scene": "LightningHierarchyAblation", "camera": "LightningHierarchyAblationCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.02, "max_duration_seconds": 0.4, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def finalize(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    prior = manifest["teacher_rule"]["controller_prior"]
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        readback_result = _read(_resolve(candidate["readback_result_path"]))
        equal_graph = _read(_resolve(candidate["baseline_graph_path"]))
        dominant_graph = _read(_resolve(candidate["guided_graph_path"]))
        graph_comparison = _graph_comparison(equal_graph, dominant_graph)
        equal = _summary(_resolve(candidate["baseline_capture_manifest_path"]))
        dominant = _summary(_resolve(candidate["capture_manifest_path"]))
        equal_peak, dominant_peak = equal["peak"], dominant["peak"]
        main = _single_role_component(dominant_graph, "particle_systems", "core")["parameters"]
        branch = _single_role_component(dominant_graph, "particle_systems", "support")["parameters"]
        paired = _paired_visual_metrics(equal, dominant)
        comparison = {"visible_width_ratio_retained": paired["paired_median_visible_width_retained"], "overexposed_visible_reduction": equal_peak["overexposed_visible_ratio"] - dominant_peak["overexposed_visible_ratio"], "high_luma_width_reduction": paired["paired_max_high_luma_width_reduction"], **paired}
        left, right = equal["capture"], dominant["capture"]
        technical_gates = {"controlled_graph_difference_only_branch_size_alpha": graph_comparison["only_branch_size_and_alpha_differ"], "equal_compile_pass": compile_result.get("status") == "pass", "equal_texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")), "equal_prefab_api_readback_pass": readback_result.get("status") == "pass", "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"], "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0, "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front", "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"]}
        technical_pass = all(technical_gates.values())
        rule_gates = {"main_is_thicker": float(main["start_size_max"]) >= float(branch["start_size_max"]) * float(prior["minimum_main_branch_size_ratio"]), "main_is_brighter": float(main["start_color_rgba"][3]) >= float(branch["start_color_rgba"][3]) * float(prior["minimum_main_branch_alpha_ratio"]), "main_silhouette_is_preserved": comparison["visible_width_ratio_retained"] >= 0.75, "hierarchy_reduces_full_length_highlight": comparison["high_luma_width_reduction"] >= float(prior["minimum_high_luma_width_reduction"])}
        rule_pass = technical_pass and all(rule_gates.values())
        records.append({"candidate_id": candidate["candidate_id"], "source_candidate_id": candidate["source_candidate_id"], "guided_graph_id": candidate["guided_graph_id"], "graph_comparison": graph_comparison, "technical_gates": technical_gates, "rule_gates": rule_gates, "technical_pass": technical_pass, "professional_rule_transfer_pass": rule_pass, "main_size": float(main["start_size_max"]), "branch_size": float(branch["start_size_max"]), "main_alpha": float(main["start_color_rgba"][3]), "branch_alpha": float(branch["start_color_rgba"][3]), **comparison, "baseline_peak": equal_peak, "guided_peak": dominant_peak, "training_eligibility": {"eligible_tasks": ["lightning_main_branch_hierarchy_controller"] if rule_pass else [], "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"], "label_scope": "relative_lightning_main_branch_hierarchy_within_verified_pair"}})
    report = {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "teacher_rule": manifest["teacher_rule"], "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records), "records": records, "status": "pass" if records and all(row["technical_pass"] for row in records) and all(row["professional_rule_transfer_pass"] for row in records) else "blocked", "training_scope": "same-topology lightning main/branch hierarchy pairs only"}
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build same-topology lightning main/branch hierarchy pairs.")
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
