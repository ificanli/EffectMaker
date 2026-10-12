"""Build a controlled Unity reproduction for outward shockwave motion."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .explosion_family_generator import CORE_MATERIAL, SHOCKWAVE_TEXTURE
from .prefab_graph import assign_graph_id
from .professional_teacher_guided_generation import _single_role_component, _validate_graph
from .professional_teacher_reproduction import _difference_paths, _read, _repo_root, _write, _write_jsonl, _portable


SCHEMA_VERSION = "vfx_professional_shockwave_teacher_reproduction.v1"
RULE_ID = "professional_explosion_shockwave_expansion_r001"
SHARED_CAPTURE_SEED_ID = "professional_explosion_shockwave_pair_r001"


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = json.loads(json.dumps(source, ensure_ascii=False))
    graph.pop("graph_id", None)
    for node in graph.get("nodes") or []:
        if node.get("role") in {"core", "hit", "residual"}:
            node["active_self"] = False
    support = _single_role_component(graph, "particle_systems", "support")
    parameters = support["parameters"]
    parameters.update({
        "duration_seconds": 0.8,
        "start_delay_max": 0.05,
        "looping": False,
        "max_particles": 8,
        "start_lifetime_max": 0.55,
        "start_speed_max": 0.0,
        "start_size_max": 0.6,
        "start_rotation_max": 0.0,
        "gravity_modifier_max": 0.0,
        "start_color_rgba": [1.0, 0.42, 0.05, 1.0],
        "end_color_rgba": [0.8, 0.06, 0.01, 0.0],
        "emission_enabled": True,
        "emission_rate_over_time_max": 0.0,
        "burst_particle_count": 1,
        "shape_enabled": True,
        "shape_type": "Circle",
        "shape_radius": 0.0,
        "color_over_lifetime_enabled": True,
        "size_over_lifetime_enabled": True,
        "end_size_multiplier": 1.0 if variant == "static_ring" else 4.5 if variant == "expanding_ring" else None,
        "renderer_mode": "Billboard",
        "sorting_order": 7,
        "texture_profile": None,
        "shader_profile": None,
        "material_template_path": CORE_MATERIAL,
        "texture_asset_path": SHOCKWAVE_TEXTURE,
        "texture_property_name": "_MainTex",
        "serialized_modules": {"profile": "professional_shockwave_reproduction", "professional_rule_id": RULE_ID},
    })
    if parameters["end_size_multiplier"] is None:
        raise ValueError(f"unsupported shockwave reproduction variant: {variant}")
    renderer = _single_role_component(graph, "renderers", "support")
    renderer.setdefault("parameters", {})["sorting_order"] = 7
    graph["condition"] = {"prompt": "专业爆炸冲击环外扩对照实验", "effect_family": "explosion", "style_family": "cartoon", "seed": 20261005, "parent_prefab_path": None}
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {"source_dataset_id": "professional_shockwave_teacher_reproduction_r001", "source_run_id": RULE_ID, "exporter": "prefab_graph_constrained.v1", "assumptions": ["Core, Hit and Residual are disabled in both variants.", "Only Shockwave end_size_multiplier differs.", "The experiment validates outward radial motion, not global aesthetic quality."]}
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _controlled_graph_comparison(static_graph: dict[str, Any], expanding_graph: dict[str, Any]) -> dict[str, Any]:
    static = json.loads(json.dumps(static_graph, ensure_ascii=False))
    expanding = json.loads(json.dumps(expanding_graph, ensure_ascii=False))
    static.pop("graph_id", None)
    expanding.pop("graph_id", None)
    paths = _difference_paths(static, expanding)
    particles = (static.get("components") or {}).get("particle_systems") or []
    support = _single_role_component(static, "particle_systems", "support")
    support_index = next(index for index, row in enumerate(particles) if row is support)
    expected = f"components.particle_systems[{support_index}].parameters.end_size_multiplier"
    return {"difference_paths": paths, "expected_difference_path": expected, "only_shockwave_scale_curve_differs": paths == [expected]}


def prepare(source_graph: Path, output_root: Path, asset_root: str = "Assets/Generated/ProfessionalTeacherExplosionShockwaveR001") -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional shockwave output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, compile_requests = [], []
    for variant in ("static_ring", "expanding_ring"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append({"variant": variant, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result)})
        compile_requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "experiment_manifest.json", {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID, "source_graph_path": _portable(source_graph),
        "professional_source": {
            "source_id": "SRC-2026-SERIES-001-EP004", "title": "第04集作业点评：连续打击的爆点、扩散线和分层消失", "author": "三生路_王先生特效",
            "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md: 作者页面说明为网易资深特效师", "license_scope": "internal_learning_only_no_redistribution", "timecodes": ["00:24:34-00:34:10"],
            "frame_paths": [
                "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/01_start_24-35.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/02_problem_25-00.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/03_modified_25-35.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/04_peak_26-30.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/05_end_29-00.jpg",
            ],
            "expert_judgment": "冲击层应在命中亮点之后从中心向外扩张，不能只是停在原地的单贴图。", "judgment_axes": ["rhythm", "layer_separation", "composition"],
        },
        "controlled_variables": {"changed": ["shockwave.end_size_multiplier"], "held_constant": ["shockwave material", "shockwave texture", "start size", "lifetime", "start delay", "color", "camera", "capture seed"]},
        "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID, "variants": variants, "status": "prepared",
    })
    compile_path = _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": compile_requests})
    return {"experiment": manifest_path, "compile_request": compile_path}


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment = _read(experiment_path.resolve())
    requests = []
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        if result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        root = output_path.resolve().parent / "runtime_captures" / variant["variant"]
        requests.append({"candidate_id": experiment["shared_capture_seed_id"], "prefab_path": result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 3.0})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_path.resolve().parent.name, "scene": "ProfessionalTeacherExplosionShockwave", "camera": "ProfessionalTeacherExplosionShockwaveCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 32, "short_effect_target_intervals": 32, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 1.5, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def _radial_frame_metrics(path: Path) -> dict[str, float]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    corners = np.concatenate((rgb[:5, :5].reshape(-1, 3), rgb[:5, -5:].reshape(-1, 3), rgb[-5:, :5].reshape(-1, 3), rgb[-5:, -5:].reshape(-1, 3)))
    background = np.median(corners, axis=0)
    delta = np.max(np.abs(rgb - background), axis=2)
    visible = delta > 8
    if not visible.any():
        return {"visible_area_ratio": 0.0, "visible_radius_p90": 0.0, "visible_radius_mean": 0.0}
    height, width = visible.shape
    yy, xx = np.nonzero(visible)
    radius = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (height - 1) / 2.0) ** 2) / (min(width, height) / 2.0)
    weights = delta[visible].astype(np.float64)
    return {"visible_area_ratio": float(visible.mean()), "visible_radius_p90": float(np.percentile(radius, 90)), "visible_radius_mean": float(np.average(radius, weights=weights))}


def _radial_summary(manifest_path: Path) -> dict[str, Any]:
    manifest = _read(manifest_path)
    capture_root = Path(str(manifest["capture_root"])).resolve()
    frames = []
    for frame in manifest.get("frames") or []:
        if frame.get("valid") and frame.get("path"):
            frames.append({"time_seconds": float(frame.get("requested_time_seconds") or 0.0), "path": _portable(capture_root / str(frame["path"])), **_radial_frame_metrics(capture_root / str(frame["path"]))})
    return {"manifest_path": _portable(manifest_path), "visual_evidence_status": manifest.get("visual_evidence_status"), "image_sequence_training_eligible": bool(manifest.get("image_sequence_training_eligible")), "material_render_error_frame_count": int(manifest.get("material_render_error_frame_count") or 0), "selected_camera_view": (manifest.get("camera_selection") or {}).get("selected_view"), "camera_mode": (manifest.get("camera_selection") or {}).get("mode"), "valid_frame_count": int(manifest.get("valid_frame_count") or 0), "frames": frames}


def _window_metrics(summary: dict[str, Any], start: float, end: float) -> dict[str, float]:
    frames = [row for row in summary["frames"] if start <= float(row["time_seconds"]) <= end and row["visible_area_ratio"] >= 0.0001]
    radii = [row["visible_radius_p90"] for row in frames]
    growth = 0.0 if len(radii) < 2 else max(radii) - radii[0]
    nondecreasing = 0.0 if len(radii) < 2 else sum(radii[index] + 0.005 >= radii[index - 1] for index in range(1, len(radii))) / (len(radii) - 1)
    return {"frame_count": float(len(frames)), "initial_radius_p90": radii[0] if radii else 0.0, "peak_radius_p90": max(radii, default=0.0), "radius_growth": growth, "nondecreasing_step_ratio": nondecreasing}


def finalize(experiment_path: Path, output_path: Path) -> dict[str, Path]:
    experiment = _read(experiment_path.resolve())
    graphs = {row["variant"]: _read(_repo_root() / row["graph_path"]) for row in experiment["variants"]}
    graph_comparison = _controlled_graph_comparison(graphs["static_ring"], graphs["expanding_ring"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _radial_summary(runtime_root / variant / "capture_manifest.json") for variant in ("static_ring", "expanding_ring")}
    static, expanding = summaries["static_ring"], summaries["expanding_ring"]
    window = (0.075, 0.55)
    static_window, expanding_window = _window_metrics(static, *window), _window_metrics(expanding, *window)
    static_by_time = {round(row["time_seconds"], 6): row for row in static["frames"]}
    expanding_by_time = {round(row["time_seconds"], 6): row for row in expanding["frames"]}
    paired_gains = [expanding_by_time[t]["visible_radius_p90"] - static_by_time[t]["visible_radius_p90"] for t in sorted(set(static_by_time) & set(expanding_by_time)) if window[0] <= t <= window[1]]
    peak_radius_gain = max(paired_gains, default=0.0)
    gates = {
        "controlled_graph_difference_only_shockwave_scale": graph_comparison["only_shockwave_scale_curve_differs"],
        "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()),
        "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()),
        "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()),
        "both_runtime_eligible": all(row["image_sequence_training_eligible"] for row in summaries.values()),
        "no_material_render_errors": all(row["material_render_error_frame_count"] == 0 for row in summaries.values()),
        "same_forced_camera": static["selected_camera_view"] == expanding["selected_camera_view"] == "front" and static["camera_mode"] == expanding["camera_mode"] == "forced_request_view_fixed_frame",
        "equal_nonzero_frame_count": static["valid_frame_count"] > 0 and static["valid_frame_count"] == expanding["valid_frame_count"],
        "static_ring_stays_local": static_window["radius_growth"] <= 0.08,
        "expanding_ring_grows": expanding_window["radius_growth"] >= 0.2,
        "expanding_ring_is_mostly_outward": expanding_window["nondecreasing_step_ratio"] >= 0.65,
        "paired_radius_gain": peak_radius_gain >= 0.15,
    }
    verified = all(gates.values())
    report = {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID, "professional_source": experiment["professional_source"], "controlled_variables": experiment["controlled_variables"], "experiment_manifest_path": _portable(experiment_path.resolve()),
        "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"},
        "graph_comparison": graph_comparison, "variants": summaries, "measurement_window_seconds": list(window), "window_metrics": {"static_ring": static_window, "expanding_ring": expanding_window}, "comparison": {"peak_paired_radius_gain": peak_radius_gain}, "quality_gates": gates,
        "validated_controller_prior": {"status": "eligible" if verified else "blocked", "effect_family": "explosion", "target_role": "support", "judgment_axis": "shockwave_expansion", "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "expanding_ring"), "minimum_radius_growth": 0.2, "minimum_paired_radius_gain": 0.15, "allowed_use": "explosion_shockwave_rule_controller_only" if verified else "knowledge_prior_only"},
        "conclusion": "Unity reproduction supports the professional rule that a shockwave should expand outward from the impact center." if verified else "Unity reproduction did not meet the radial expansion gates; keep the rule as a knowledge prior only.", "status": "verified" if verified else "blocked",
    }
    report_path = _write(output_path.resolve(), report)
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {"schema_version": "course_knowledge_record.v1", "record_id": RULE_ID, "source_path": "knowledge/sources/SRC-2026-SERIES-001/ep004/visual_review_middle.md", "heading": "连续打击：爆点、扩散线和分层消失", "line_start": 25, "line_end": 32, "excerpt": experiment["professional_source"]["expert_judgment"], "record_type": "tutorial_fact", "status": "verified" if verified else "pending", "effect_family": "explosion", "evidence_level": "high" if verified else "medium", "timecodes": experiment["professional_source"]["timecodes"], "frame_paths": experiment["professional_source"]["frame_paths"], "judgment_axes": experiment["professional_source"]["judgment_axes"], "source_expertise_status": "verified_professional", "unity_reproduction_status": "verified" if verified else "blocked", "unity_reproduction_report": _portable(report_path), "eligible_for_vfxspec_prior": verified, "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "reason": "Teacher rule may supervise the explosion shockwave axis only; it is not a global quality label."}}
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_explosion_shockwave_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a controlled professional explosion shockwave reproduction.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--source-graph", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--asset-root", default="Assets/Generated/ProfessionalTeacherExplosionShockwaveR001")
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
