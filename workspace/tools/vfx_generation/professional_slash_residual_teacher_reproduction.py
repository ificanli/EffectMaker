"""Build a controlled Unity reproduction for slash residual timing."""

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


SCHEMA_VERSION = "vfx_professional_slash_residual_teacher_reproduction.v1"
RULE_ID = "professional_slash_readable_then_fade_r001"
SHARED_CAPTURE_SEED_ID = "professional_slash_residual_pair_r001"
ORTHOGRAPHIC_SIZE = 1.4


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = copy.deepcopy(source)
    graph.pop("graph_id", None)
    residual = _single_role_component(graph, "particle_systems", "residual")
    parameters = residual["parameters"]
    parameters.update(
        {
            "start_speed_max": 2.1,
            "start_size_max": 0.24,
            "burst_particle_count": 8,
            "start_color_rgba": [0.35, 0.85, 1.0, 0.42],
            "end_size_multiplier": 0.2,
        }
    )
    if variant == "premature_residual":
        parameters["start_delay_max"] = 0.0
        parameters["start_lifetime_max"] = 0.12
    elif variant == "staged_residual":
        parameters["start_delay_max"] = 0.18
        parameters["start_lifetime_max"] = 0.30
    else:
        raise ValueError(f"unsupported slash residual variant: {variant}")
    graph["condition"] = {
        "prompt": "专业刀光可读峰值后残留收尾对照",
        "effect_family": "slash",
        "style_family": "cartoon",
        "seed": 20262360,
        "parent_prefab_path": None,
    }
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {
        "source_dataset_id": "professional_slash_residual_teacher_r001",
        "source_run_id": RULE_ID,
        "exporter": "prefab_graph_constrained.v1",
        "assumptions": [
            "Core, Support, Hit, assets, color, speed, size and camera remain identical.",
            "Only DirectionTrail start delay and lifetime differ.",
            "The experiment validates readable-then-fade timing, not global slash quality.",
        ],
    }
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _graph_comparison(premature: dict[str, Any], staged: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(premature), copy.deepcopy(staged)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    particles = (left.get("components") or {}).get("particle_systems") or []
    residual = _single_role_component(left, "particle_systems", "residual")
    index = next(index for index, row in enumerate(particles) if row is residual)
    expected = {
        f"components.particle_systems[{index}].parameters.start_delay_max",
        f"components.particle_systems[{index}].parameters.start_lifetime_max",
    }
    return {"difference_paths": paths, "expected_difference_paths": sorted(expected), "only_residual_timing_differs": set(paths) == expected}


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


def _role_end_seconds(graph: dict[str, Any], role: str) -> float:
    parameters = _single_role_component(graph, "particle_systems", role)["parameters"]
    return float(parameters.get("start_delay_max") or 0.0) + float(parameters.get("start_lifetime_max") or 0.0)


def prepare(source_graph: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional slash residual output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, requests = [], []
    for variant in ("premature_residual", "staged_residual"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append(
            {
                "variant": variant,
                "graph_id": graph["graph_id"],
                "graph_path": _portable(graph_path),
                "output_prefab_path": output_prefab,
                "compile_result_path": _portable(compile_result),
                "readback_graph_path": _portable(readback_graph),
                "readback_result_path": _portable(readback_result),
            }
        )
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    staged = _variant(source, "staged_residual")
    experiment = _write(
        output_root / "experiment_manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rule_id": RULE_ID,
            "source_graph_path": _portable(source_graph),
            "professional_source": {
                "source_id": "SRC-2026-UP389578709",
                "title": "刀光特效制作的底层逻辑（公开课）",
                "author": "特效Orange",
                "author_expertise_evidence": "knowledge/sources/SRC-2026-UP389578709_source.md",
                "license_scope": "internal_learning_only_no_redistribution",
                "timecodes": ["01:00:13-01:01:24"],
                "frame_paths": [
                    "knowledge/sources/SRC-2026-UP389578709/frames/BV1mjvxBgESJ/60-70/60-48_to_61-04_contact_sheet.jpg"
                ],
                "expert_judgment": "刀光应先保留可读的关键瞬间，再进入慢速消失；过早结束或从出现到消失同速都会削弱收尾。",
                "judgment_axes": ["rhythm", "readability", "layer_separation"],
            },
            "controlled_variables": {
                "changed": ["residual.start_delay_max", "residual.start_lifetime_max"],
                "held_constant": ["graph topology", "Core", "Support", "Hit", "assets", "residual color", "residual speed", "residual size", "camera", "capture seed"],
            },
            "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID,
            "non_residual_end_seconds": _non_residual_end_seconds(staged),
            "staged_residual_end_seconds": _role_end_seconds(staged, "residual"),
            "variants": variants,
            "status": "prepared",
        },
    )
    return {
        "experiment": experiment,
        "compile_request": _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests}),
    }


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment = _read(experiment_path.resolve())
    requests = []
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        if result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        root = output_path.resolve().parent / "runtime_captures" / variant["variant"]
        requests.append(
            {
                "candidate_id": experiment["shared_capture_seed_id"],
                "prefab_path": result["output_prefab_path"],
                "capture_dir": (root / "captures").as_posix(),
                "capture_manifest_path": (root / "capture_manifest.json").as_posix(),
                "material_timeline_path": (root / "material_timeline.json").as_posix(),
                "source_script_fidelity": "generated_graph_no_source_scripts",
                "ignored_script_dependency_count": 0,
                "missing_script_count": 0,
                "capture_category": "slash",
                "forced_camera_view": "front",
                "force_orthographic": True,
                "forced_orthographic_size": ORTHOGRAPHIC_SIZE,
            }
        )
    return _write(
        output_path.resolve(),
        {
            "schema_version": "effectdemo_source_render_requests.v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": output_path.resolve().parent.name,
            "scene": "ProfessionalTeacherSlashResidual",
            "camera": "ProfessionalTeacherSlashResidualCamera",
            "width": 640,
            "height": 640,
            "sampling_mode": "adaptive_runtime",
            "sampling": {"target_intervals": 30, "short_effect_target_intervals": 30, "min_interval_seconds": 0.01, "max_interval_seconds": 0.02, "max_duration_seconds": 0.6, "include_zero": True, "duration_sources": ["particle_system"]},
            "capture_material_timeline": True,
            "requests": requests,
        },
    )


def _late_metrics(summary: dict[str, Any], late_start: float) -> dict[str, float]:
    frames = [row for row in summary["frames"] if float(row["time_seconds"]) >= late_start]
    visible = [row for row in frames if float(row["visible_area_ratio"]) >= 0.00005]
    return {
        "frame_count": float(len(frames)),
        "active_frame_ratio": len(visible) / max(1, len(frames)),
        "visible_area_mean": float(np.mean([float(row["visible_area_ratio"]) for row in frames])) if frames else 0.0,
        "last_visible_time_seconds": max((float(row["time_seconds"]) for row in visible), default=0.0),
    }


def _contact_sheet(summaries: dict[str, dict[str, Any]], output: Path) -> Path:
    targets = [0.08, 0.18, 0.28, 0.38, 0.48]
    tile_width, tile_height = 220, 205
    canvas = Image.new("RGB", (tile_width * len(targets), tile_height * 2 + 34), "#101418")
    draw = ImageDraw.Draw(canvas)
    for row_index, variant in enumerate(("premature_residual", "staged_residual")):
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
    graph_comparison = _graph_comparison(graphs["premature_residual"], graphs["staged_residual"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _capture_summary(runtime_root / variant / "capture_manifest.json") for variant in ("premature_residual", "staged_residual")}
    late_start = float(experiment["non_residual_end_seconds"]) + 0.02
    premature_late = _late_metrics(summaries["premature_residual"], late_start)
    staged_late = _late_metrics(summaries["staged_residual"], late_start)
    gains = {
        "late_active_frame_ratio_gain": staged_late["active_frame_ratio"] - premature_late["active_frame_ratio"],
        "late_visible_area_mean_gain": staged_late["visible_area_mean"] - premature_late["visible_area_mean"],
        "last_visible_time_gain_seconds": staged_late["last_visible_time_seconds"] - premature_late["last_visible_time_seconds"],
        "residual_end_after_core_seconds": float(experiment["staged_residual_end_seconds"]) - float(experiment["non_residual_end_seconds"]),
    }
    left, right = summaries["premature_residual"], summaries["staged_residual"]
    gates = {
        "controlled_graph_difference_only_residual_timing": graph_comparison["only_residual_timing_differs"],
        "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()),
        "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()),
        "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()),
        "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"],
        "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0,
        "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front",
        "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"],
        "residual_extends_beyond_core": gains["residual_end_after_core_seconds"] >= 0.08,
        "late_active_ratio_gain": gains["late_active_frame_ratio_gain"] >= 0.15,
        "late_visible_area_gain": gains["late_visible_area_mean_gain"] >= 0.00005,
        "last_visible_time_gain": gains["last_visible_time_gain_seconds"] >= 0.06,
    }
    verified = all(gates.values())
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "professional_source": experiment["professional_source"],
        "controlled_variables": experiment["controlled_variables"],
        "experiment_manifest_path": _portable(experiment_path.resolve()),
        "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"},
        "graph_comparison": graph_comparison,
        "variants": summaries,
        "late_window_start_seconds": late_start,
        "late_metrics": {"premature_residual": premature_late, "staged_residual": staged_late},
        "comparison": gains,
        "quality_gates": gates,
        "validated_controller_prior": {
            "status": "eligible" if verified else "blocked",
            "effect_family": "slash",
            "target_role": "residual",
            "judgment_axis": "readable_then_fade",
            "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "staged_residual"),
            "minimum_late_active_ratio_gain": 0.15,
            "minimum_late_visible_area_gain": 0.00005,
            "minimum_last_visible_time_gain_seconds": 0.06,
            "allowed_use": "slash_residual_timing_controller_only" if verified else "knowledge_prior_only",
        },
        "conclusion": "Unity reproduction supports preserving a readable slash peak before a delayed residual fade." if verified else "Unity reproduction did not satisfy slash residual timing gates.",
        "status": "verified" if verified else "blocked",
    }
    report_path = _write(output_path.resolve(), report)
    sheet_path = _contact_sheet(summaries, output_path.resolve().parent / "slash_residual_pair_contact_sheet.png")
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {
        "schema_version": "course_knowledge_record.v1",
        "record_id": RULE_ID,
        "source_path": "knowledge/sources/SRC-2026-UP389578709/visual_review_BV1mjvxBgESJ_60-70.md",
        "heading": "先保证瞬间可读，再安排后续消失",
        "line_start": 12,
        "line_end": 20,
        "excerpt": experiment["professional_source"]["expert_judgment"],
        "record_type": "tutorial_fact",
        "status": "verified" if verified else "pending",
        "effect_family": "slash",
        "evidence_level": "high" if verified else "medium",
        "timecodes": experiment["professional_source"]["timecodes"],
        "frame_paths": experiment["professional_source"]["frame_paths"],
        "judgment_axes": experiment["professional_source"]["judgment_axes"],
        "source_expertise_status": "verified_professional",
        "unity_reproduction_status": "verified" if verified else "blocked",
        "unity_reproduction_report": _portable(report_path),
        "eligible_for_vfxspec_prior": verified,
        "training_eligibility": {
            "controller_sft": False,
            "prompt_condition_supervision": False,
            "positive_generation_supervision": False,
            "preference_training": False,
            "reason": "Teacher rule may supervise slash residual timing only; it is not a global quality label.",
        },
    }
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_slash_residual_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "contact_sheet": sheet_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a controlled slash residual-timing Teacher reproduction.")
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
