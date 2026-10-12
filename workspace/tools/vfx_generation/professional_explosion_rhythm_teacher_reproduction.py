"""Build a controlled Unity reproduction for staged four-layer explosion rhythm."""

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


SCHEMA_VERSION = "vfx_professional_explosion_rhythm_teacher_reproduction.v1"
RULE_ID = "professional_explosion_staged_rhythm_r001"
SHARED_CAPTURE_SEED_ID = "professional_explosion_rhythm_pair_r001"


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = copy.deepcopy(source)
    graph.pop("graph_id", None)
    if variant not in {"simultaneous_layers", "staged_layers"}:
        raise ValueError(f"unsupported rhythm variant: {variant}")
    if variant == "simultaneous_layers":
        for role in ("support", "hit", "residual"):
            _single_role_component(graph, "particle_systems", role)["parameters"]["start_delay_max"] = 0.0
    graph["condition"] = {"prompt": "专业爆炸四层节奏对照实验", "effect_family": "explosion", "style_family": "cartoon", "seed": 20261314, "parent_prefab_path": None}
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {"source_dataset_id": "professional_explosion_rhythm_teacher_r001", "source_run_id": RULE_ID, "exporter": "prefab_graph_constrained.v1", "assumptions": ["Only Support, Hit and Residual start delays differ.", "Materials, textures, particle counts, speeds, lifetimes and colors are held constant.", "The experiment validates staged layer rhythm, not global aesthetic quality."]}
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _controlled_graph_comparison(simultaneous: dict[str, Any], staged: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(simultaneous), copy.deepcopy(staged)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    expected = []
    particles = (left.get("components") or {}).get("particle_systems") or []
    for role in ("support", "hit", "residual"):
        component = _single_role_component(left, "particle_systems", role)
        index = next(i for i, row in enumerate(particles) if row is component)
        expected.append(f"components.particle_systems[{index}].parameters.start_delay_max")
    expected.sort()
    return {"difference_paths": paths, "expected_difference_paths": expected, "only_layer_delays_differ": paths == expected}


def prepare(source_graph: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional rhythm output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, requests = [], []
    for variant in ("simultaneous_layers", "staged_layers"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append({"variant": variant, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result)})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    experiment_path = _write(output_root / "experiment_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "source_graph_path": _portable(source_graph),
        "professional_source": {"source_id": "SRC-2026-SERIES-001-EP004-EP006", "title": "连续打击分层消失与短爆发快速收束", "author": "三生路_王先生特效", "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md: 作者页面说明为网易资深特效师", "license_scope": "internal_learning_only_no_redistribution", "timecodes": ["EP004 00:24:34-00:34:10", "EP006 00:10:00-00:20:00"], "frame_paths": ["knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/01_start_24-35.jpg", "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/03_modified_25-35.jpg", "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/04_peak_26-30.jpg", "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/05_end_29-00.jpg"], "expert_judgment": "完整爆炸应按中心亮点、扩散线与碎片、残光小元素的顺序分层出现，并在短爆发后快速收束而不是全部同时起播和消失。", "judgment_axes": ["rhythm", "layer_separation", "composition"]},
        "controlled_variables": {"changed": ["support.start_delay_max", "hit.start_delay_max", "residual.start_delay_max"], "held_constant": ["all materials", "all textures", "particle counts", "speeds", "lifetimes", "colors", "camera", "capture seed"]},
        "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID,
        "variants": variants,
        "status": "prepared",
    })
    return {"experiment": experiment_path, "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})}


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment = _read(experiment_path.resolve())
    requests = []
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        if result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        root = output_path.resolve().parent / "runtime_captures" / variant["variant"]
        requests.append({"candidate_id": experiment["shared_capture_seed_id"], "prefab_path": result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 3.0})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_path.resolve().parent.name, "scene": "ProfessionalTeacherExplosionRhythm", "camera": "ProfessionalTeacherExplosionRhythmCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 48, "short_effect_target_intervals": 48, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 1.5, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def _zone_metrics(path: Path) -> dict[str, float]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    corners = np.concatenate((rgb[:5, :5].reshape(-1, 3), rgb[:5, -5:].reshape(-1, 3), rgb[-5:, :5].reshape(-1, 3), rgb[-5:, -5:].reshape(-1, 3)))
    background = np.median(corners, axis=0)
    visible = np.max(np.abs(rgb - background), axis=2) > 8
    height, width = visible.shape
    yy, xx = np.ogrid[:height, :width]
    radius = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (height - 1) / 2.0) ** 2) / (min(width, height) / 2.0)
    center_zone, outer_zone = radius < 0.04, radius >= 0.06
    luma = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]) / 255.0
    return {"visible_area_ratio": float(visible.mean()), "center_visible_ratio": float(visible[center_zone].mean()), "outer_visible_ratio": float(visible[outer_zone].mean()), "center_luminance": float(luma[center_zone].mean())}


def _rhythm_summary(manifest_path: Path) -> dict[str, Any]:
    capture = _capture_summary(manifest_path)
    frames = [{"time_seconds": row["time_seconds"], "path": row["path"], **_zone_metrics(_repo_root() / row["path"])} for row in capture["frames"]]
    def onset(name: str, threshold: float) -> float:
        return next((float(row["time_seconds"]) for row in frames if float(row[name]) >= threshold), -1.0)
    early = [row for row in frames if row["time_seconds"] <= 0.05]
    late = [row for row in frames if 0.85 <= row["time_seconds"] <= 1.35]
    return {"capture": capture, "frames": frames, "center_onset_seconds": onset("center_visible_ratio", 0.005), "outer_onset_seconds": onset("outer_visible_ratio", 0.00005), "early_outer_visible_mean": float(np.mean([row["outer_visible_ratio"] for row in early])) if early else 0.0, "late_active_ratio": sum(row["visible_area_ratio"] >= 0.0001 for row in late) / max(1, len(late)), "last_visible_time_seconds": max((row["time_seconds"] for row in frames if row["visible_area_ratio"] >= 0.0001), default=0.0)}


def _contact_sheet(summaries: dict[str, dict[str, Any]], output: Path) -> Path:
    targets = [0.0, 0.05, 0.15, 0.35, 0.9, 1.2]
    tile_width, tile_height = 190, 185
    canvas = Image.new("RGB", (tile_width * len(targets), tile_height * 2 + 34), "#101418")
    draw = ImageDraw.Draw(canvas)
    for row_index, variant in enumerate(("simultaneous_layers", "staged_layers")):
        top = 34 + row_index * tile_height
        draw.text((8, top + 4), variant, fill="#ffba6a" if row_index else "#aeb8c2")
        frames = summaries[variant]["frames"]
        for column, target in enumerate(targets):
            frame = min(frames, key=lambda row: abs(float(row["time_seconds"]) - target))
            with Image.open(_repo_root() / frame["path"]) as source:
                tile = ImageOps.contain(source.convert("RGB"), (tile_width - 8, tile_height - 24))
            left = column * tile_width
            canvas.paste(tile, (left + 4, top + 20))
            draw.text((left + 5, 8), f"{float(frame['time_seconds']):.3f}s", fill="#e4e7ea")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def finalize(experiment_path: Path, output_path: Path) -> dict[str, Path]:
    experiment = _read(experiment_path.resolve())
    graphs = {row["variant"]: _read(_repo_root() / row["graph_path"]) for row in experiment["variants"]}
    graph_comparison = _controlled_graph_comparison(graphs["simultaneous_layers"], graphs["staged_layers"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _rhythm_summary(runtime_root / variant / "capture_manifest.json") for variant in ("simultaneous_layers", "staged_layers")}
    simultaneous, staged = summaries["simultaneous_layers"], summaries["staged_layers"]
    staged_delays = {role: float(_single_role_component(graphs["staged_layers"], "particle_systems", role)["parameters"].get("start_delay_max") or 0.0) for role in ("core", "support", "hit", "residual")}
    comparison = {"outer_onset_delay_gain_seconds": staged["outer_onset_seconds"] - simultaneous["outer_onset_seconds"], "early_outer_visible_reduction": simultaneous["early_outer_visible_mean"] - staged["early_outer_visible_mean"], "late_active_ratio_gain": staged["late_active_ratio"] - simultaneous["late_active_ratio"], "last_visible_time_gain_seconds": staged["last_visible_time_seconds"] - simultaneous["last_visible_time_seconds"]}
    left, right = simultaneous["capture"], staged["capture"]
    gates = {"controlled_graph_difference_only_layer_delays": graph_comparison["only_layer_delays_differ"], "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()), "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()), "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()), "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"], "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0, "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front", "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"], "staged_graph_orders_core_support_hit_residual": staged_delays["core"] < staged_delays["support"] < staged_delays["hit"] < staged_delays["residual"], "staging_reduces_early_outer_overlap": comparison["early_outer_visible_reduction"] >= 0.00005, "staging_preserves_late_residual": comparison["last_visible_time_gain_seconds"] >= 0.15}
    verified = all(gates.values())
    report = {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID, "professional_source": experiment["professional_source"], "controlled_variables": experiment["controlled_variables"], "experiment_manifest_path": _portable(experiment_path.resolve()), "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"}, "graph_comparison": graph_comparison, "staged_delays_seconds": staged_delays, "variants": summaries, "comparison": comparison, "quality_gates": gates, "validated_controller_prior": {"status": "eligible" if verified else "blocked", "effect_family": "explosion", "target_role": "multi_layer", "judgment_axis": "staged_rhythm", "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "staged_layers"), "minimum_early_outer_visible_reduction": 0.00005, "minimum_last_visible_time_gain_seconds": 0.15, "required_delay_order": ["core", "support", "hit", "residual"], "allowed_use": "explosion_staged_rhythm_controller_only" if verified else "knowledge_prior_only"}, "conclusion": "Unity reproduction supports staged Core, expansion/debris and residual timing." if verified else "Unity reproduction did not satisfy staged rhythm gates.", "status": "verified" if verified else "blocked"}
    report_path = _write(output_path.resolve(), report)
    sheet_path = _contact_sheet(summaries, output_path.resolve().parent / "rhythm_pair_contact_sheet.png")
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {"schema_version": "course_knowledge_record.v1", "record_id": RULE_ID, "source_path": "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_review_middle.md", "heading": "连续打击：爆点、扩散线和分层消失", "line_start": 25, "line_end": 32, "excerpt": experiment["professional_source"]["expert_judgment"], "record_type": "tutorial_fact", "status": "verified" if verified else "pending", "effect_family": "explosion", "evidence_level": "high" if verified else "medium", "timecodes": experiment["professional_source"]["timecodes"], "frame_paths": experiment["professional_source"]["frame_paths"], "judgment_axes": experiment["professional_source"]["judgment_axes"], "source_expertise_status": "verified_professional", "unity_reproduction_status": "verified" if verified else "blocked", "unity_reproduction_report": _portable(report_path), "eligible_for_vfxspec_prior": verified, "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "reason": "Teacher rule may supervise staged explosion rhythm only; it is not a global quality label."}}
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_explosion_rhythm_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "contact_sheet": sheet_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a controlled staged explosion rhythm Teacher reproduction.")
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
