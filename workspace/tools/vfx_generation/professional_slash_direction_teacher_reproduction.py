"""Build a controlled Unity reproduction for slash trail direction."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .prefab_graph import assign_graph_id
from .professional_teacher_guided_generation import _single_role_component, _validate_graph
from .professional_teacher_reproduction import _capture_summary, _difference_paths, _portable, _read, _repo_root, _write, _write_jsonl


SCHEMA_VERSION = "vfx_professional_slash_direction_teacher_reproduction.v1"
RULE_ID = "professional_slash_directional_trail_r001"
SHARED_CAPTURE_SEED_ID = "professional_slash_direction_pair_r001"


def _role_node(graph: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [node for node in graph.get("nodes") or [] if node.get("role") == role]
    if len(matches) != 1:
        raise ValueError(f"exactly one {role} node expected, found {len(matches)}")
    return matches[0]


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = copy.deepcopy(source)
    graph.pop("graph_id", None)
    _role_node(graph, "core")["active_self"] = False
    _role_node(graph, "support")["active_self"] = False
    hit_nodes = [node for node in graph.get("nodes") or [] if node.get("role") == "hit"]
    for node in hit_nodes:
        node["active_self"] = False
    trail_node = _role_node(graph, "residual")
    trail = _single_role_component(graph, "particle_systems", "residual")
    trail["parameters"].update({"start_delay_max": 0.0, "start_lifetime_max": 0.28, "start_speed_max": 2.8, "start_size_max": 0.34, "burst_particle_count": 9, "shape_radius": 0.03, "start_color_rgba": [0.35, 0.85, 1.0, 0.8]})
    if variant == "depth_misaligned":
        trail_node["transform"]["local_rotation"] = [0.0, 0.0, 0.0, 1.0]
    elif variant == "attack_aligned":
        trail_node["transform"]["local_rotation"] = [0.0, 0.7071068, 0.0, 0.7071068]
    else:
        raise ValueError(f"unsupported slash direction variant: {variant}")
    graph["condition"] = {"prompt": "专业刀光方向拖带对照", "effect_family": "slash", "style_family": "cartoon", "seed": 20262013, "parent_prefab_path": None}
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {"source_dataset_id": "professional_slash_direction_teacher_r001", "source_run_id": RULE_ID, "exporter": "prefab_graph_constrained.v1", "assumptions": ["OuterBlade, InnerSupport and optional ContactHit are disabled in both variants.", "Only DirectionTrail transform rotation differs.", "The experiment validates screen-space attack-axis motion, not global slash quality."]}
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _graph_comparison(depth: dict[str, Any], aligned: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(depth), copy.deepcopy(aligned)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    node_index = next(index for index, node in enumerate(left["nodes"]) if node.get("role") == "residual")
    prefix = f"nodes[{node_index}].transform.local_rotation"
    return {"difference_paths": paths, "expected_difference_prefix": prefix, "only_trail_rotation_differs": bool(paths) and all(path.startswith(prefix) for path in paths)}


def prepare(source_graph: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional slash direction output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, requests = [], []
    for variant in ("depth_misaligned", "attack_aligned"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append({"variant": variant, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result)})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    experiment = _write(output_root / "experiment_manifest.json", {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID, "source_graph_path": _portable(source_graph), "professional_source": {"source_id": "SRC-2026-SERIES-001-EP003", "title": "第03集作业点评：重复模板、动态方向与刀光能量", "author": "三生路_王先生特效", "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md", "license_scope": "internal_learning_only_no_redistribution", "timecodes": ["01:02:00-01:12:03", "01:38:09-02:02:00"], "frame_paths": ["knowledge/sources/SRC-2026-SERIES-001/ep003/visual_check/07_template_reuse/", "knowledge/sources/SRC-2026-SERIES-001/ep003/visual_check/09_flying_attack/"], "expert_judgment": "刀光拖带与能量扩散应沿攻击方向真正离开原位置，不能朝镜头运动或停在原地堆叠。", "judgment_axes": ["composition", "rhythm", "layer_separation"]}, "controlled_variables": {"changed": ["direction_trail.transform.local_rotation"], "held_constant": ["trail material", "trail texture", "speed", "lifetime", "size", "burst count", "camera", "capture seed"]}, "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID, "variants": variants, "status": "prepared"})
    return {"experiment": experiment, "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})}


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment = _read(experiment_path.resolve())
    requests = []
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        if result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        root = output_path.resolve().parent / "runtime_captures" / variant["variant"]
        requests.append({"candidate_id": experiment["shared_capture_seed_id"], "prefab_path": result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "slash", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 1.4})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_path.resolve().parent.name, "scene": "ProfessionalTeacherSlashDirection", "camera": "ProfessionalTeacherSlashDirectionCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 24, "short_effect_target_intervals": 24, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 0.6, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def _centroid_metrics(path: Path) -> dict[str, float]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    corners = np.concatenate((rgb[:5, :5].reshape(-1, 3), rgb[:5, -5:].reshape(-1, 3), rgb[-5:, :5].reshape(-1, 3), rgb[-5:, -5:].reshape(-1, 3)))
    background = np.median(corners, axis=0)
    delta = np.max(np.abs(rgb - background), axis=2)
    visible = delta > 8
    if not visible.any():
        return {"visible_area_ratio": 0.0, "centroid_x": 0.5, "centroid_y": 0.5}
    yy, xx = np.nonzero(visible)
    weights = delta[visible].astype(np.float64)
    return {"visible_area_ratio": float(visible.mean()), "centroid_x": float(np.average(xx, weights=weights) / max(1, visible.shape[1] - 1)), "centroid_y": float(np.average(yy, weights=weights) / max(1, visible.shape[0] - 1))}


def _summary(manifest_path: Path) -> dict[str, Any]:
    capture = _capture_summary(manifest_path)
    frames = [{"time_seconds": row["time_seconds"], "path": row["path"], **_centroid_metrics(_repo_root() / row["path"])} for row in capture["frames"]]
    active = [row for row in frames if row["visible_area_ratio"] >= 0.00005]
    xs, ys = [row["centroid_x"] for row in active], [row["centroid_y"] for row in active]
    return {"capture": capture, "frames": frames, "active_frame_count": len(active), "horizontal_centroid_span": max(xs, default=0.5) - min(xs, default=0.5), "vertical_centroid_span": max(ys, default=0.5) - min(ys, default=0.5), "start_centroid_x": xs[0] if xs else 0.5, "end_centroid_x": xs[-1] if xs else 0.5}


def _contact_sheet(summaries: dict[str, dict[str, Any]], output: Path) -> Path:
    targets = [0.0, 0.075, 0.15, 0.225, 0.3]
    tw, th = 220, 205
    canvas = Image.new("RGB", (tw * len(targets), th * 2 + 34), "#101418")
    draw = ImageDraw.Draw(canvas)
    for row_index, variant in enumerate(("depth_misaligned", "attack_aligned")):
        top = 34 + row_index * th
        draw.text((8, top + 4), variant, fill="#ffba6a" if row_index else "#aeb8c2")
        frames = summaries[variant]["frames"]
        for column, target in enumerate(targets):
            frame = min(frames, key=lambda row: abs(float(row["time_seconds"]) - target))
            with Image.open(_repo_root() / frame["path"]) as source:
                tile = ImageOps.contain(source.convert("RGB"), (tw - 8, th - 24))
            left = column * tw
            canvas.paste(tile, (left + 4, top + 20))
            draw.text((left + 5, 8), f"{float(frame['time_seconds']):.3f}s", fill="#e4e7ea")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def finalize(experiment_path: Path, output_path: Path) -> dict[str, Path]:
    experiment = _read(experiment_path.resolve())
    graphs = {row["variant"]: _read(_repo_root() / row["graph_path"]) for row in experiment["variants"]}
    graph_comparison = _graph_comparison(graphs["depth_misaligned"], graphs["attack_aligned"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _summary(runtime_root / variant / "capture_manifest.json") for variant in ("depth_misaligned", "attack_aligned")}
    depth, aligned = summaries["depth_misaligned"], summaries["attack_aligned"]
    comparison = {"horizontal_span_gain": aligned["horizontal_centroid_span"] - depth["horizontal_centroid_span"], "aligned_horizontal_vertical_ratio": aligned["horizontal_centroid_span"] / max(aligned["vertical_centroid_span"], 1e-6), "aligned_signed_x_displacement": aligned["end_centroid_x"] - aligned["start_centroid_x"]}
    left, right = depth["capture"], aligned["capture"]
    gates = {"controlled_graph_difference_only_trail_rotation": graph_comparison["only_trail_rotation_differs"], "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()), "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()), "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()), "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"], "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0, "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front", "aligned_has_motion_frames": aligned["active_frame_count"] >= 5, "aligned_moves_horizontally": aligned["horizontal_centroid_span"] >= 0.05, "aligned_motion_is_axis_dominant": comparison["aligned_horizontal_vertical_ratio"] >= 2.0, "aligned_exceeds_depth_projection": comparison["horizontal_span_gain"] >= 0.04}
    verified = all(gates.values())
    report = {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID, "professional_source": experiment["professional_source"], "controlled_variables": experiment["controlled_variables"], "experiment_manifest_path": _portable(experiment_path.resolve()), "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"}, "graph_comparison": graph_comparison, "variants": summaries, "comparison": comparison, "quality_gates": gates, "validated_controller_prior": {"status": "eligible" if verified else "blocked", "effect_family": "slash", "target_role": "residual", "judgment_axis": "directional_trail", "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "attack_aligned"), "minimum_horizontal_centroid_span": 0.05, "minimum_horizontal_span_gain": 0.04, "allowed_use": "slash_directional_trail_controller_only" if verified else "knowledge_prior_only"}, "conclusion": "Unity reproduction supports aligning slash trail motion with the screen-space attack axis." if verified else "Unity reproduction did not satisfy directional trail motion gates.", "status": "verified" if verified else "blocked"}
    report_path = _write(output_path.resolve(), report)
    sheet_path = _contact_sheet(summaries, output_path.resolve().parent / "slash_direction_pair_contact_sheet.png")
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {"schema_version": "course_knowledge_record.v1", "record_id": RULE_ID, "source_path": "knowledge/sources/SRC-2026-SERIES-001/ep003/visual_review_back.md", "heading": "重复模板、动态方向与刀光能量", "line_start": 5, "line_end": 12, "excerpt": experiment["professional_source"]["expert_judgment"], "record_type": "tutorial_fact", "status": "verified" if verified else "pending", "effect_family": "slash", "evidence_level": "high" if verified else "medium", "timecodes": experiment["professional_source"]["timecodes"], "frame_paths": experiment["professional_source"]["frame_paths"], "judgment_axes": experiment["professional_source"]["judgment_axes"], "source_expertise_status": "verified_professional", "unity_reproduction_status": "verified" if verified else "blocked", "unity_reproduction_report": _portable(report_path), "eligible_for_vfxspec_prior": verified, "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "reason": "Teacher rule may supervise slash directional trail only; it is not a global quality label."}}
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_slash_direction_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "contact_sheet": sheet_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a controlled slash direction Teacher reproduction.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--source-graph", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--asset-root", required=True)
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--experiment", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--experiment", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            paths = prepare(args.source_graph, args.output_root, args.asset_root)
        elif args.command == "prepare-runtime":
            paths = {"runtime_request": prepare_runtime(args.experiment, args.output)}
        else:
            paths = finalize(args.experiment, args.output)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
