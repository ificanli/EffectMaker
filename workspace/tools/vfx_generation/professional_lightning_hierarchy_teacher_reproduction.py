"""Build a controlled Unity reproduction for lightning main/branch hierarchy."""

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


SCHEMA_VERSION = "vfx_professional_lightning_hierarchy_teacher_reproduction.v1"
RULE_ID = "professional_lightning_main_branch_hierarchy_r001"
SHARED_CAPTURE_SEED_ID = "professional_lightning_hierarchy_pair_r001"


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = copy.deepcopy(source)
    graph.pop("graph_id", None)
    main = _single_role_component(graph, "particle_systems", "core")
    branch = _single_role_component(graph, "particle_systems", "support")
    roles = {str(node.get("role")): node for node in graph.get("nodes") or []}
    roles["hit"]["active_self"] = False
    roles["residual"]["active_self"] = False
    if variant == "equal_weight":
        branch["parameters"]["start_size_max"] = main["parameters"]["start_size_max"]
        branch_color = list(branch["parameters"]["start_color_rgba"])
        branch_color[3] = float(main["parameters"]["start_color_rgba"][3])
        branch["parameters"]["start_color_rgba"] = branch_color
    elif variant != "main_dominant":
        raise ValueError(f"unsupported lightning hierarchy variant: {variant}")
    graph["condition"] = {"prompt": "专业雷电主电流与外围分支层级对照", "effect_family": "lightning", "style_family": "stylized", "seed": 20262408, "parent_prefab_path": None}
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {"source_dataset_id": "professional_lightning_hierarchy_teacher_r001", "source_run_id": RULE_ID, "exporter": "prefab_graph_constrained.v1", "assumptions": ["ImpactFlash and ResidualSpark are disabled in both variants.", "Only BranchSupport size and alpha differ.", "MainBolt, textures, timing and camera are held constant.", "The experiment validates main/branch hierarchy, not global lightning quality."]}
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _graph_comparison(equal: dict[str, Any], dominant: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(equal), copy.deepcopy(dominant)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    particles = (left.get("components") or {}).get("particle_systems") or []
    branch = _single_role_component(left, "particle_systems", "support")
    index = next(i for i, row in enumerate(particles) if row is branch)
    expected = sorted([f"components.particle_systems[{index}].parameters.start_size_max", f"components.particle_systems[{index}].parameters.start_color_rgba[3]"])
    return {"difference_paths": paths, "expected_difference_paths": expected, "only_branch_size_and_alpha_differ": paths == expected}


def prepare(source_graph: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional lightning hierarchy output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, requests = [], []
    for variant in ("equal_weight", "main_dominant"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append({"variant": variant, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result)})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    experiment = _write(output_root / "experiment_manifest.json", {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID, "source_graph_path": _portable(source_graph), "professional_source": {"source_id": "SRC-2026-SERIES-001-EP004", "title": "第04集作业点评：闪电的粗细、可见性和短促收尾", "author": "三生路_王先生特效", "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md", "license_scope": "internal_learning_only_no_redistribution", "timecodes": ["00:17:10-00:24:34"], "frame_paths": ["knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/04_28_lightning/02_problem_18-00.jpg", "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/04_28_lightning/03_modified_18-35.jpg", "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/04_28_lightning/04_peak_19-40.jpg"], "expert_judgment": "雷电中心主电流应更粗，外围分支更细且数量克制，避免细碎线条与主电流同亮同重。", "judgment_axes": ["core_readability", "branch_readability", "layer_separation"]}, "controlled_variables": {"changed": ["branch.start_size_max", "branch.start_color_rgba.alpha"], "held_constant": ["MainBolt", "textures", "timing", "particle count", "camera", "capture seed"]}, "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID, "variants": variants, "status": "prepared"})
    return {"experiment": experiment, "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})}


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment = _read(experiment_path.resolve())
    requests = []
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        if result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        root = output_path.resolve().parent / "runtime_captures" / variant["variant"]
        requests.append({"candidate_id": experiment["shared_capture_seed_id"], "prefab_path": result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "lightning", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 2.2})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_path.resolve().parent.name, "scene": "ProfessionalTeacherLightningHierarchy", "camera": "ProfessionalTeacherLightningHierarchyCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.02, "max_duration_seconds": 0.4, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def _frame_metrics(path: Path) -> dict[str, float]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    corners = np.concatenate((rgb[:5, :5].reshape(-1, 3), rgb[:5, -5:].reshape(-1, 3), rgb[-5:, :5].reshape(-1, 3), rgb[-5:, -5:].reshape(-1, 3)))
    background = np.median(corners, axis=0)
    delta = np.max(np.abs(rgb - background), axis=2)
    visible = delta > 8
    if not visible.any():
        return {"visible_area_ratio": 0.0, "visible_width_ratio": 0.0, "overexposed_visible_ratio": 0.0, "high_luma_width_ratio": 0.0}
    yy, xx = np.nonzero(visible)
    luma = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]) / 255.0
    high = (luma >= 0.85) & visible
    high_width = (int(np.nonzero(high)[1].max()) - int(np.nonzero(high)[1].min()) + 1) if high.any() else 0
    return {"visible_area_ratio": float(visible.mean()), "visible_width_ratio": float((int(xx.max()) - int(xx.min()) + 1) / visible.shape[1]), "overexposed_visible_ratio": float((luma[visible] >= 0.95).mean()), "high_luma_width_ratio": float(high_width / visible.shape[1])}


def _summary(manifest_path: Path) -> dict[str, Any]:
    capture = _capture_summary(manifest_path)
    frames = [{"time_seconds": row["time_seconds"], "path": row["path"], **_frame_metrics(_repo_root() / row["path"])} for row in capture["frames"] if row["time_seconds"] <= 0.4]
    peak = max(frames, key=lambda row: row["visible_area_ratio"])
    return {"capture": capture, "frames": frames, "peak": peak}


def _contact_sheet(summaries: dict[str, dict[str, Any]], output: Path) -> Path:
    targets = [0.025, 0.075, 0.15, 0.25, 0.35]
    tw, th = 220, 205
    canvas = Image.new("RGB", (tw * len(targets), th * 2 + 34), "#101418")
    draw = ImageDraw.Draw(canvas)
    for row_index, variant in enumerate(("equal_weight", "main_dominant")):
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
    graph_comparison = _graph_comparison(graphs["equal_weight"], graphs["main_dominant"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _summary(runtime_root / variant / "capture_manifest.json") for variant in ("equal_weight", "main_dominant")}
    equal, dominant = summaries["equal_weight"]["peak"], summaries["main_dominant"]["peak"]
    main = _single_role_component(graphs["main_dominant"], "particle_systems", "core")["parameters"]
    branch = _single_role_component(graphs["main_dominant"], "particle_systems", "support")["parameters"]
    comparison = {"visible_width_ratio_retained": dominant["visible_width_ratio"] / max(equal["visible_width_ratio"], 1e-6), "overexposed_visible_reduction": equal["overexposed_visible_ratio"] - dominant["overexposed_visible_ratio"], "high_luma_width_reduction": equal["high_luma_width_ratio"] - dominant["high_luma_width_ratio"]}
    left, right = summaries["equal_weight"]["capture"], summaries["main_dominant"]["capture"]
    gates = {"controlled_graph_difference_only_branch_size_alpha": graph_comparison["only_branch_size_and_alpha_differ"], "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()), "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()), "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()), "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"], "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0, "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front", "main_is_thicker": float(main["start_size_max"]) >= float(branch["start_size_max"]) * 1.2, "main_is_brighter": float(main["start_color_rgba"][3]) >= float(branch["start_color_rgba"][3]) * 2.0, "main_silhouette_is_preserved": comparison["visible_width_ratio_retained"] >= 0.75, "hierarchy_reduces_full_length_highlight": comparison["high_luma_width_reduction"] >= 0.005}
    verified = all(gates.values())
    report = {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID, "professional_source": experiment["professional_source"], "controlled_variables": experiment["controlled_variables"], "experiment_manifest_path": _portable(experiment_path.resolve()), "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"}, "graph_comparison": graph_comparison, "variants": summaries, "comparison": comparison, "quality_gates": gates, "validated_controller_prior": {"status": "eligible" if verified else "blocked", "effect_family": "lightning", "target_role": "core_support", "judgment_axis": "main_branch_hierarchy", "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "main_dominant"), "minimum_main_branch_size_ratio": 1.2, "minimum_main_branch_alpha_ratio": 2.0, "minimum_high_luma_width_reduction": 0.005, "allowed_use": "lightning_main_branch_rule_controller_only" if verified else "knowledge_prior_only"}, "conclusion": "Unity reproduction supports a thicker/brighter main current and thinner/weaker branch support." if verified else "Unity reproduction did not satisfy lightning hierarchy gates.", "status": "verified" if verified else "blocked"}
    report_path = _write(output_path.resolve(), report)
    sheet_path = _contact_sheet(summaries, output_path.resolve().parent / "lightning_hierarchy_pair_contact_sheet.png")
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {"schema_version": "course_knowledge_record.v1", "record_id": RULE_ID, "source_path": "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_review_middle.md", "heading": "闪电的粗细、可见性和短促收尾", "line_start": 15, "line_end": 22, "excerpt": experiment["professional_source"]["expert_judgment"], "record_type": "tutorial_fact", "status": "verified" if verified else "pending", "effect_family": "lightning", "evidence_level": "high" if verified else "medium", "timecodes": experiment["professional_source"]["timecodes"], "frame_paths": experiment["professional_source"]["frame_paths"], "judgment_axes": experiment["professional_source"]["judgment_axes"], "source_expertise_status": "verified_professional", "unity_reproduction_status": "verified" if verified else "blocked", "unity_reproduction_report": _portable(report_path), "eligible_for_vfxspec_prior": verified, "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "reason": "Teacher rule may supervise lightning main/branch hierarchy only; it is not a global quality label."}}
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_lightning_hierarchy_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "contact_sheet": sheet_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a controlled lightning main/branch hierarchy Teacher reproduction.")
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
