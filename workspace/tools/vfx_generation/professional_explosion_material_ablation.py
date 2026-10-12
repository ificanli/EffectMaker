"""Build same-topology flat/structured Core texture pairs."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .explosion_family_generator import CORE_TEXTURE
from .prefab_graph import assign_graph_id
from .professional_explosion_material_teacher_reproduction import _controlled_graph_comparison, _variant_summary
from .professional_teacher_guided_generation import _load_teacher_rule, _single_role_component, _validate_graph


SCHEMA_VERSION = "vfx_professional_explosion_material_ablation_batch.v1"
RULE_ID = "professional_explosion_core_texture_structure_r001"


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


def create_flat_texture_ablation(graph: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "explosion":
        raise ValueError("material ablation requires an explosion PrefabGraph")
    core = _single_role_component(result, "particle_systems", "core")
    core["parameters"]["texture_asset_path"] = CORE_TEXTURE
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, ["core.parameters.texture_asset_path"]


def prepare(source_manifest_path: Path, teacher_ready_path: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"material ablation output already exists and is not empty: {output_root}")
    source_manifest = _read(source_manifest_path.resolve())
    teacher, report, _ = _load_teacher_rule(teacher_ready_path.resolve(), RULE_ID)
    candidates, requests = [], []
    for index, source_candidate in enumerate(source_manifest["candidates"]):
        source_graph_path = _resolve(source_candidate["graph_path"])
        structured_graph = _read(source_graph_path)
        flat_graph, changed_fields = create_flat_texture_ablation(structured_graph)
        pair_id = f"layered_material_pair_{index:03d}_{structured_graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / pair_id / "flat_graph.json", flat_graph)
        output_prefab = f"{asset_root.rstrip('/')}/{pair_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{pair_id}.json"
        readback_graph = output_root / "readback" / f"{pair_id}.json"
        readback_result = output_root / "readback_results" / f"{pair_id}.json"
        source_compile = _read(_resolve(source_candidate["compile_result_path"]))
        source_readback = _read(_resolve(source_candidate["readback_result_path"]))
        if source_compile.get("status") != "pass" or source_readback.get("status") != "pass":
            raise ValueError(f"source layered explosion is not technically valid: {source_candidate['candidate_id']}")
        candidates.append({"candidate_id": pair_id, "source_candidate_id": source_candidate["candidate_id"], "guided_graph_id": structured_graph["graph_id"], "guided_graph_path": _portable(source_graph_path), "guided_prefab_path": source_compile["output_prefab_path"], "baseline_graph_id": flat_graph["graph_id"], "baseline_graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result), "baseline_capture_manifest_path": _portable(output_root / "runtime_baselines" / pair_id / "capture_manifest.json"), "capture_manifest_path": _portable(output_root / "runtime_captures" / pair_id / "capture_manifest.json"), "changed_fields": changed_fields})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "guided_generation_manifest.json", {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name, "source_manifest_path": _portable(source_manifest_path.resolve()), "teacher_ready_path": _portable(teacher_ready_path.resolve()), "teacher_rule": {"record_id": RULE_ID, "effect_family": "explosion", "judgment_axes": teacher["judgment_axes"], "expert_judgment": teacher["expert_judgment"], "reproduction_report": teacher["unity_reproduction_report"], "controller_prior": report["validated_controller_prior"]}, "candidate_count": len(candidates), "candidates": candidates, "status": "prepared_pending_unity"})
    compile_path = _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})
    return {"manifest": manifest_path, "compile_request": compile_path}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing flat Core compile result required: {candidate['candidate_id']}")
        for prefab_path, root_name in ((compile_result["output_prefab_path"], "runtime_baselines"), (candidate["guided_prefab_path"], "runtime_captures")):
            root = output_path.resolve().parent / root_name / candidate["candidate_id"]
            requests.append({"candidate_id": candidate["source_candidate_id"], "prefab_path": prefab_path, "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 1.5})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "scene": "LayeredExplosionMaterialAblation", "camera": "LayeredExplosionMaterialAblationCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 0.8, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def finalize(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    prior = manifest["teacher_rule"]["controller_prior"]
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        readback_result = _read(_resolve(candidate["readback_result_path"]))
        flat_graph = _read(_resolve(candidate["baseline_graph_path"]))
        structured_graph = _read(_resolve(candidate["guided_graph_path"]))
        graph_comparison = _controlled_graph_comparison(flat_graph, structured_graph)
        support = _single_role_component(structured_graph, "particle_systems", "support")
        core_only_window_end = max(0.025, float(support["parameters"].get("start_delay_max") or 0.05) - 0.005)
        flat_summary = _variant_summary(_resolve(candidate["baseline_capture_manifest_path"]), core_only_window_end)
        structured_summary = _variant_summary(_resolve(candidate["capture_manifest_path"]), core_only_window_end)
        flat, structured = flat_summary["peak"], structured_summary["peak"]
        comparison = {"bbox_fill_reduction": flat["bbox_fill_ratio"] - structured["bbox_fill_ratio"], "visible_luma_std_gain": structured["visible_luma_std"] - flat["visible_luma_std"], "edge_density_gain": structured["edge_density"] - flat["edge_density"], "center_luminance_ratio": structured["center_luminance"] / max(flat["center_luminance"], 1e-6)}
        left, right = flat_summary["capture"], structured_summary["capture"]
        technical_gates = {"controlled_graph_difference_only_core_texture": graph_comparison["only_core_texture_differs"], "flat_compile_pass": compile_result.get("status") == "pass", "flat_texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")), "flat_prefab_api_readback_pass": readback_result.get("status") == "pass", "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"], "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0, "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front", "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"]}
        technical_pass = all(technical_gates.values())
        rule_gates = {"structured_core_remains_visible": structured["visible_area_ratio"] >= 0.001 and comparison["center_luminance_ratio"] >= float(prior["minimum_center_luminance_ratio"]), "structured_core_has_more_edge_structure": comparison["edge_density_gain"] >= 0.02, "structured_core_breaks_flat_fill": comparison["bbox_fill_reduction"] >= float(prior["minimum_bbox_fill_reduction"])}
        rule_pass = technical_pass and all(rule_gates.values())
        records.append({"candidate_id": candidate["candidate_id"], "source_candidate_id": candidate["source_candidate_id"], "guided_graph_id": candidate["guided_graph_id"], "core_only_window_end_seconds": core_only_window_end, "graph_comparison": graph_comparison, "technical_gates": technical_gates, "rule_gates": rule_gates, "technical_pass": technical_pass, "professional_rule_transfer_pass": rule_pass, **comparison, "baseline_peak": flat, "guided_peak": structured, "training_eligibility": {"eligible_tasks": ["explosion_core_texture_structure_rule_controller"] if rule_pass else [], "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"], "label_scope": "relative_core_texture_structure_within_verified_pair"}})
    report = {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "teacher_rule": manifest["teacher_rule"], "candidate_count": len(records), "technical_pass_count": sum(row["technical_pass"] for row in records), "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records), "records": records, "status": "pass" if records and all(row["technical_pass"] for row in records) and all(row["professional_rule_transfer_pass"] for row in records) else "blocked", "training_scope": "same-topology explosion Core texture pairs only"}
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build same-topology explosion Core material pairs.")
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
