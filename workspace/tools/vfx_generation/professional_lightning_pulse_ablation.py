"""Build same-topology slow/instant lightning pulse pairs."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prefab_graph import assign_graph_id
from .professional_lightning_pulse_teacher_reproduction import ORTHOGRAPHIC_SIZE, _graph_comparison, _summary
from .professional_teacher_guided_generation import _load_teacher_rule, _single_role_component, _validate_graph


SCHEMA_VERSION = "vfx_professional_lightning_pulse_ablation_batch.v1"
RULE_ID = "professional_lightning_instant_pulse_r001"


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


def create_slow_pulse_ablation(graph: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "lightning":
        raise ValueError("pulse ablation requires a lightning PrefabGraph")
    core = _single_role_component(result, "particle_systems", "core")
    for node in result.get("nodes") or []:
        if node.get("role") in {"support", "hit", "residual"}:
            node["active_self"] = False
    core["parameters"]["start_lifetime_max"] = 0.36
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, ["core.parameters.start_lifetime_max"]


def create_instant_isolated(graph: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(graph)
    for node in result.get("nodes") or []:
        if node.get("role") in {"support", "hit", "residual"}:
            node["active_self"] = False
    _single_role_component(result, "particle_systems", "core")["parameters"]["start_lifetime_max"] = 0.14
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result


def prepare(source_manifest_path: Path, teacher_ready_path: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"lightning pulse ablation output already exists and is not empty: {output_root}")
    source_manifest = _read(source_manifest_path.resolve())
    teacher, report, _ = _load_teacher_rule(teacher_ready_path.resolve(), RULE_ID)
    candidates, requests = [], []
    for index, source_candidate in enumerate(source_manifest["candidates"]):
        source_graph_path = _resolve(source_candidate["graph_path"])
        instant_graph = create_instant_isolated(_read(source_graph_path))
        slow_graph, changed_fields = create_slow_pulse_ablation(instant_graph)
        pair_id = f"lightning_pulse_pair_{index:03d}_{instant_graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / pair_id / "slow_graph.json", slow_graph)
        guided_graph_path = _write(output_root / "candidates" / pair_id / "instant_graph.json", instant_graph)
        output_prefab = f"{asset_root.rstrip('/')}/{pair_id}/GeneratedRoot.prefab"
        guided_prefab = f"{asset_root.rstrip('/')}/{pair_id}/Instant/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{pair_id}.json"
        guided_compile_result = output_root / "compile_results" / f"{pair_id}_instant.json"
        readback_graph = output_root / "readback" / f"{pair_id}.json"
        readback_result = output_root / "readback_results" / f"{pair_id}.json"
        guided_readback_graph = output_root / "readback" / f"{pair_id}_instant.json"
        guided_readback_result = output_root / "readback_results" / f"{pair_id}_instant.json"
        source_compile = _read(_resolve(source_candidate["compile_result_path"]))
        source_readback = _read(_resolve(source_candidate["readback_result_path"]))
        if source_compile.get("status") != "pass" or source_readback.get("status") != "pass":
            raise ValueError(f"source lightning is not technically valid: {source_candidate['candidate_id']}")
        candidates.append({"candidate_id": pair_id, "source_candidate_id": source_candidate["candidate_id"], "guided_graph_id": instant_graph["graph_id"], "guided_graph_path": _portable(guided_graph_path), "guided_prefab_path": guided_prefab, "guided_compile_result_path": _portable(guided_compile_result), "guided_readback_graph_path": _portable(guided_readback_graph), "guided_readback_result_path": _portable(guided_readback_result), "baseline_graph_id": slow_graph["graph_id"], "baseline_graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result), "baseline_capture_manifest_path": _portable(output_root / "runtime_baselines" / pair_id / "capture_manifest.json"), "capture_manifest_path": _portable(output_root / "runtime_captures" / pair_id / "capture_manifest.json"), "changed_fields": changed_fields})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
        requests.append({"graph_path": guided_graph_path.as_posix(), "output_prefab_path": guided_prefab, "result_path": guided_compile_result.as_posix()})
    manifest_path = _write(output_root / "guided_generation_manifest.json", {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name, "source_manifest_path": _portable(source_manifest_path.resolve()), "teacher_ready_path": _portable(teacher_ready_path.resolve()), "teacher_rule": {"record_id": RULE_ID, "effect_family": "lightning", "judgment_axes": teacher["judgment_axes"], "expert_judgment": teacher["expert_judgment"], "reproduction_report": teacher["unity_reproduction_report"], "controller_prior": report["validated_controller_prior"]}, "candidate_count": len(candidates), "candidates": candidates, "status": "prepared_pending_unity"})
    return {"manifest": manifest_path, "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        guided_compile_result = _read(_resolve(candidate["guided_compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing slow-pulse compile result required: {candidate['candidate_id']}")
        if guided_compile_result.get("status") != "pass":
            raise ValueError(f"passing instant-pulse compile result required: {candidate['candidate_id']}")
        for prefab_path, root_name in ((compile_result["output_prefab_path"], "runtime_baselines"), (guided_compile_result["output_prefab_path"], "runtime_captures")):
            root = output_path.resolve().parent / root_name / candidate["candidate_id"]
            requests.append({"candidate_id": candidate["source_candidate_id"], "prefab_path": prefab_path, "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "lightning", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": ORTHOGRAPHIC_SIZE})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "scene": "LightningPulseAblation", "camera": "LightningPulseAblationCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 24, "short_effect_target_intervals": 24, "min_interval_seconds": 0.01, "max_interval_seconds": 0.02, "max_duration_seconds": 0.5, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def finalize(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    prior = manifest["teacher_rule"]["controller_prior"]
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        guided_compile_result = _read(_resolve(candidate["guided_compile_result_path"]))
        readback_result = _read(_resolve(candidate["readback_result_path"]))
        guided_readback_result = _read(_resolve(candidate["guided_readback_result_path"]))
        slow_graph = _read(_resolve(candidate["baseline_graph_path"]))
        instant_graph = _read(_resolve(candidate["guided_graph_path"]))
        graph_comparison = _graph_comparison(slow_graph, instant_graph)
        slow = _summary(_resolve(candidate["baseline_capture_manifest_path"]))
        instant = _summary(_resolve(candidate["capture_manifest_path"]))
        comparison = {"early_peak_retained": instant["early_peak_visible_area"] / max(slow["early_peak_visible_area"], 1e-6), "last_visible_time_reduction_seconds": slow["last_visible_time_seconds"] - instant["last_visible_time_seconds"], "active_frame_count_reduction": slow["active_frame_count"] - instant["active_frame_count"]}
        left, right = slow["capture"], instant["capture"]
        technical_gates = {"controlled_graph_difference_only_core_lifetime": graph_comparison["only_core_lifetime_differs"], "both_compile_pass": compile_result.get("status") == guided_compile_result.get("status") == "pass", "both_texture_readbacks_match_plan": bool(compile_result.get("planned_texture_readback_match")) and bool(guided_compile_result.get("planned_texture_readback_match")), "both_prefab_api_readbacks_pass": readback_result.get("status") == guided_readback_result.get("status") == "pass", "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"], "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0, "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front", "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"]}
        technical_pass = all(technical_gates.values())
        rule_gates = {"early_peak_is_retained": comparison["early_peak_retained"] >= float(prior["minimum_early_peak_retained"]), "instant_pulse_exits_earlier": comparison["last_visible_time_reduction_seconds"] >= float(prior["minimum_last_visible_time_reduction_seconds"]), "instant_pulse_uses_fewer_active_frames": comparison["active_frame_count_reduction"] >= int(prior["minimum_active_frame_count_reduction"])}
        rule_pass = technical_pass and all(rule_gates.values())
        records.append({"candidate_id": candidate["candidate_id"], "source_candidate_id": candidate["source_candidate_id"], "guided_graph_id": candidate["guided_graph_id"], "graph_comparison": graph_comparison, "technical_gates": technical_gates, "rule_gates": rule_gates, "technical_pass": technical_pass, "professional_rule_transfer_pass": rule_pass, **comparison, "training_eligibility": {"eligible_tasks": ["lightning_instant_pulse_controller"] if rule_pass else [], "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"], "label_scope": "relative_lightning_instant_pulse_within_verified_pair"}})
    return _write(output_path.resolve(), {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "teacher_rule": manifest["teacher_rule"], "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records), "records": records, "status": "pass" if records and all(row["technical_pass"] for row in records) and all(row["professional_rule_transfer_pass"] for row in records) else "blocked", "training_scope": "same-topology lightning instant-pulse pairs only"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build same-topology lightning pulse pairs.")
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
