"""Build a controlled Unity reproduction for explosion residual persistence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .prefab_graph import assign_graph_id
from .professional_teacher_guided_generation import _single_role_component, _validate_graph
from .professional_teacher_reproduction import _capture_summary, _difference_paths, _read, _repo_root, _write, _write_jsonl, _portable


SCHEMA_VERSION = "vfx_professional_residual_teacher_reproduction.v1"
RULE_ID = "professional_explosion_residual_persistence_r001"
SHARED_CAPTURE_SEED_ID = "professional_explosion_residual_pair_r001"


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = json.loads(json.dumps(source, ensure_ascii=False))
    graph.pop("graph_id", None)
    residual = _single_role_component(graph, "particle_systems", "residual")
    parameters = residual["parameters"]
    color = list(parameters.get("start_color_rgba") or [0.48, 0.2, 0.08, 0.7])
    if variant == "abrupt_no_residual":
        color[3] = 0.0
    elif variant == "staged_residual":
        if color[3] <= 0.0:
            color[3] = 0.7
    else:
        raise ValueError(f"unsupported residual reproduction variant: {variant}")
    parameters["start_color_rgba"] = color
    graph["condition"] = {
        "prompt": "专业爆炸残留持续性对照实验",
        "effect_family": "explosion",
        "style_family": "cartoon",
        "seed": 20261004,
        "parent_prefab_path": None,
    }
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {
        "source_dataset_id": "professional_residual_teacher_reproduction_r001",
        "source_run_id": RULE_ID,
        "exporter": "prefab_graph_constrained.v1",
        "assumptions": [
            "Both variants share topology, Core, Shockwave, Debris, materials, timing and capture seed.",
            "Only the Residual ParticleSystem start alpha differs.",
            "The experiment validates post-peak persistence, not global aesthetic quality.",
        ],
    }
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _controlled_graph_comparison(empty_graph: dict[str, Any], residual_graph: dict[str, Any]) -> dict[str, Any]:
    empty = json.loads(json.dumps(empty_graph, ensure_ascii=False))
    residual = json.loads(json.dumps(residual_graph, ensure_ascii=False))
    empty.pop("graph_id", None)
    residual.pop("graph_id", None)
    paths = _difference_paths(empty, residual)
    particles = (empty.get("components") or {}).get("particle_systems") or []
    residual_particle = _single_role_component(empty, "particle_systems", "residual")
    residual_index = next(index for index, row in enumerate(particles) if row is residual_particle)
    expected = f"components.particle_systems[{residual_index}].parameters.start_color_rgba[3]"
    return {"difference_paths": paths, "expected_difference_path": expected, "only_residual_alpha_differs": paths == [expected]}


def _non_residual_end_seconds(graph: dict[str, Any]) -> float:
    roles = {str(node["node_id"]): str(node.get("role") or "") for node in graph.get("nodes") or []}
    values = []
    for particle in (graph.get("components") or {}).get("particle_systems") or []:
        if roles.get(str(particle.get("node_id"))) == "residual":
            continue
        parameters = particle.get("parameters") or {}
        values.append(float(parameters.get("start_delay_max") or 0.0) + float(parameters.get("start_lifetime_max") or 0.0))
    if not values:
        raise ValueError("non-residual layers are required")
    return max(values)


def prepare(source_graph: Path, output_root: Path, asset_root: str = "Assets/Generated/ProfessionalTeacherExplosionResidualR001") -> dict[str, Path]:
    source_graph = source_graph.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional residual output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    late_start = _non_residual_end_seconds(source) + 0.05
    variants = []
    compile_requests = []
    for variant in ("abrupt_no_residual", "staged_residual"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append({
            "variant": variant, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab,
            "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result),
        })
        compile_requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    manifest_path = _write(output_root / "experiment_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "source_graph_path": _portable(source_graph),
        "professional_source": {
            "source_id": "SRC-2026-001",
            "title": "20260415点评-一定要练基本功",
            "author": "三生路_王先生特效",
            "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md: 作者页面说明为网易资深特效师",
            "source_url": "https://www.bilibili.com/video/BV1xmQnBaE6b/",
            "license_scope": "internal_learning_only_no_redistribution",
            "timecodes": ["00:57:40-00:58:47"],
            "frame_paths": [
                "knowledge/sources/SRC-2026-001/visual_review_44-66/evidence/00-57-48.jpg",
                "knowledge/sources/SRC-2026-001/visual_review_44-66/evidence/00-57-55.jpg",
                "knowledge/sources/SRC-2026-001/visual_review_44-66/evidence/00-58-48.jpg",
            ],
            "expert_judgment": "爆炸后应有残留，不应在峰值后瞬间清空。",
            "judgment_axes": ["rhythm", "layer_separation"],
        },
        "controlled_variables": {"changed": ["residual.start_color_rgba.alpha"], "held_constant": ["graph topology", "core parameters", "shockwave parameters", "debris parameters", "material paths", "texture paths", "shader paths", "timing", "capture seed"]},
        "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID,
        "late_window_start_seconds": late_start,
        "variants": variants,
        "status": "prepared",
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
        requests.append({
            "candidate_id": experiment["shared_capture_seed_id"], "prefab_path": result["output_prefab_path"],
            "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts",
            "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion",
        })
    return _write(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_path.resolve().parent.name,
        "scene": "ProfessionalTeacherExplosionResidual", "camera": "ProfessionalTeacherExplosionResidualCamera", "width": 640, "height": 360,
        "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 32, "short_effect_target_intervals": 32, "min_interval_seconds": 0.01, "max_interval_seconds": 0.05, "max_duration_seconds": 2.5, "include_zero": True, "duration_sources": ["particle_system"]},
        "capture_material_timeline": True, "requests": requests,
    })


def _late_metrics(summary: dict[str, Any], late_start: float) -> dict[str, float]:
    frames = [row for row in summary["frames"] if float(row["time_seconds"]) >= late_start]
    visible = [row for row in frames if float(row["visible_area_ratio"]) >= 0.001]
    return {
        "frame_count": float(len(frames)),
        "active_frame_ratio": len(visible) / max(1, len(frames)),
        "visible_area_mean": float(np.mean([float(row["visible_area_ratio"]) for row in frames])) if frames else 0.0,
        "last_visible_time_seconds": max((float(row["time_seconds"]) for row in visible), default=0.0),
    }


def _early_pair_mae(empty: dict[str, Any], residual: dict[str, Any], cutoff: float) -> float:
    empty_by_time = {round(float(row["time_seconds"]), 6): row for row in empty["frames"] if float(row["time_seconds"]) < cutoff}
    residual_by_time = {round(float(row["time_seconds"]), 6): row for row in residual["frames"] if float(row["time_seconds"]) < cutoff}
    values = []
    for time_seconds in sorted(set(empty_by_time) & set(residual_by_time)):
        with Image.open(_repo_root() / empty_by_time[time_seconds]["path"]) as left_image, Image.open(_repo_root() / residual_by_time[time_seconds]["path"]) as right_image:
            left = np.asarray(left_image.convert("RGB"), dtype=np.float32) / 255.0
            right = np.asarray(right_image.convert("RGB"), dtype=np.float32) / 255.0
        values.append(float(np.abs(left - right).mean()))
    return max(values, default=0.0)


def finalize(experiment_path: Path, output_path: Path) -> dict[str, Path]:
    experiment = _read(experiment_path.resolve())
    graphs = {variant["variant"]: _read(_repo_root() / variant["graph_path"]) for variant in experiment["variants"]}
    graph_comparison = _controlled_graph_comparison(graphs["abrupt_no_residual"], graphs["staged_residual"])
    compile_results = {variant["variant"]: _read(_repo_root() / variant["compile_result_path"]) for variant in experiment["variants"]}
    readback_results = {variant["variant"]: _read(_repo_root() / variant["readback_result_path"]) for variant in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _capture_summary(runtime_root / variant / "capture_manifest.json") for variant in ("abrupt_no_residual", "staged_residual")}
    empty, residual = summaries["abrupt_no_residual"], summaries["staged_residual"]
    late_start = float(experiment["late_window_start_seconds"])
    empty_late, residual_late = _late_metrics(empty, late_start), _late_metrics(residual, late_start)
    gains = {
        "late_active_frame_ratio_gain": residual_late["active_frame_ratio"] - empty_late["active_frame_ratio"],
        "late_visible_area_mean_gain": residual_late["visible_area_mean"] - empty_late["visible_area_mean"],
        "last_visible_time_gain_seconds": residual_late["last_visible_time_seconds"] - empty_late["last_visible_time_seconds"],
        "early_frame_max_mae": _early_pair_mae(empty, residual, min(late_start, 0.18)),
    }
    gates = {
        "controlled_graph_difference_only_residual_alpha": graph_comparison["only_residual_alpha_differs"],
        "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()),
        "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()),
        "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()),
        "both_runtime_eligible": all(row["image_sequence_training_eligible"] for row in summaries.values()),
        "no_material_render_errors": all(row["material_render_error_frame_count"] == 0 for row in summaries.values()),
        "same_camera_view": bool(empty["selected_camera_view"]) and empty["selected_camera_view"] == residual["selected_camera_view"],
        "equal_nonzero_frame_count": empty["valid_frame_count"] > 0 and empty["valid_frame_count"] == residual["valid_frame_count"],
        "early_frames_unchanged": gains["early_frame_max_mae"] <= 0.002,
        "late_active_ratio_gain": gains["late_active_frame_ratio_gain"] >= 0.15,
        "late_visible_area_gain": gains["late_visible_area_mean_gain"] >= 0.0005,
        "last_visible_time_gain": gains["last_visible_time_gain_seconds"] >= 0.3,
    }
    verified = all(gates.values())
    report = {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "rule_id": RULE_ID,
        "professional_source": experiment["professional_source"], "controlled_variables": experiment["controlled_variables"], "experiment_manifest_path": _portable(experiment_path.resolve()),
        "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"},
        "graph_comparison": graph_comparison, "variants": summaries, "late_window_start_seconds": late_start,
        "late_metrics": {"abrupt_no_residual": empty_late, "staged_residual": residual_late}, "comparison": gains, "quality_gates": gates,
        "validated_controller_prior": {"status": "eligible" if verified else "blocked", "effect_family": "explosion", "target_role": "residual", "judgment_axis": "rhythm", "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "staged_residual"), "minimum_late_active_ratio_gain": 0.15, "minimum_late_visible_area_gain": 0.0005, "minimum_last_visible_time_gain_seconds": 0.3, "allowed_use": "explosion_residual_rule_controller_only" if verified else "knowledge_prior_only"},
        "conclusion": "Unity reproduction supports the professional rule that a delayed Residual layer preserves post-peak continuity." if verified else "Unity reproduction did not meet the residual-persistence gates; keep the rule as a knowledge prior only.",
        "status": "verified" if verified else "blocked",
    }
    report_path = _write(output_path.resolve(), report)
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {
        "schema_version": "course_knowledge_record.v1", "record_id": RULE_ID, "source_path": "knowledge/sources/SRC-2026-001/visual_review_back.md", "heading": "爆炸残留与冰霜", "line_start": 44, "line_end": 49,
        "excerpt": experiment["professional_source"]["expert_judgment"], "record_type": "tutorial_fact", "status": "verified" if verified else "pending", "effect_family": "explosion", "evidence_level": "high" if verified else "medium",
        "timecodes": experiment["professional_source"]["timecodes"], "frame_paths": experiment["professional_source"]["frame_paths"], "judgment_axes": experiment["professional_source"]["judgment_axes"],
        "source_expertise_status": "verified_professional", "unity_reproduction_status": "verified" if verified else "blocked", "unity_reproduction_report": _portable(report_path), "eligible_for_vfxspec_prior": verified,
        "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "reason": "Teacher rule may supervise the explosion residual/rhythm axis only; it is not a global quality label."},
    }
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_explosion_residual_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a controlled professional explosion residual reproduction.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--source-graph", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--asset-root", default="Assets/Generated/ProfessionalTeacherExplosionResidualR001")
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
