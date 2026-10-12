"""Build a controlled Unity reproduction for readable explosion debris branches."""

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


SCHEMA_VERSION = "vfx_professional_debris_teacher_reproduction.v1"
RULE_ID = "professional_explosion_debris_branches_r001"
SHARED_CAPTURE_SEED_ID = "professional_explosion_debris_pair_r001"


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = copy.deepcopy(source)
    graph.pop("graph_id", None)
    for node in graph.get("nodes") or []:
        if node.get("role") in {"support", "residual"}:
            node["active_self"] = False
    hit = _single_role_component(graph, "particle_systems", "hit")
    parameters = hit["parameters"]
    start_color = list(parameters["start_color_rgba"])
    start_color[3] = 0.0 if variant == "no_debris" else 0.95 if variant == "radial_debris" else None
    if start_color[3] is None:
        raise ValueError(f"unsupported debris reproduction variant: {variant}")
    parameters["start_color_rgba"] = start_color
    graph["condition"] = {
        "prompt": "专业爆炸碎片分支对照实验",
        "effect_family": "explosion",
        "style_family": "cartoon",
        "seed": 20261312,
        "parent_prefab_path": None,
    }
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {
        "source_dataset_id": "professional_debris_teacher_reproduction_r001",
        "source_run_id": RULE_ID,
        "exporter": "prefab_graph_constrained.v1",
        "assumptions": [
            "Shockwave and Residual are disabled in both variants while Core remains visible.",
            "Only Debris start alpha differs.",
            "The experiment validates readable debris branches, not global aesthetic quality.",
        ],
    }
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _controlled_graph_comparison(no_debris: dict[str, Any], radial_debris: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(no_debris), copy.deepcopy(radial_debris)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    particles = (left.get("components") or {}).get("particle_systems") or []
    hit = _single_role_component(left, "particle_systems", "hit")
    hit_index = next(index for index, row in enumerate(particles) if row is hit)
    expected = f"components.particle_systems[{hit_index}].parameters.start_color_rgba[3]"
    return {"difference_paths": paths, "expected_difference_path": expected, "only_debris_alpha_differs": paths == [expected]}


def prepare(source_graph: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional debris output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, compile_requests = [], []
    for variant in ("no_debris", "radial_debris"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append({
            "variant": variant,
            "graph_id": graph["graph_id"],
            "graph_path": _portable(graph_path),
            "output_prefab_path": output_prefab,
            "compile_result_path": _portable(compile_result),
            "readback_graph_path": _portable(readback_graph),
            "readback_result_path": _portable(readback_result),
        })
        compile_requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    experiment_path = _write(output_root / "experiment_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "source_graph_path": _portable(source_graph),
        "professional_source": {
            "source_id": "SRC-2026-SERIES-001-EP008",
            "title": "第08集作业点评：火鸟/凤凰爆炸主体与碎片分支",
            "author": "三生路_王先生特效",
            "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md: 作者页面说明为网易资深特效师",
            "license_scope": "internal_learning_only_no_redistribution",
            "timecodes": ["00:05:53-00:11:14"],
            "frame_paths": [
                "knowledge/sources/SRC-2026-SERIES-001/ep008/visual_check/02_fire_burst/01_00300.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep008/visual_check/02_fire_burst/02_00432.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep008/visual_check/02_fire_burst/03_00564.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep008/visual_check/02_fire_burst/04_00699.jpg",
            ],
            "expert_judgment": "爆裂时应增加从核心向外展开的小型分支或碎片，不能只有单一过曝主体。",
            "judgment_axes": ["layer_separation", "composition", "core_readability"],
        },
        "controlled_variables": {
            "changed": ["debris.start_color_rgba.alpha"],
            "held_constant": ["core", "debris texture", "debris material", "burst count", "speed", "lifetime", "camera", "capture seed"],
        },
        "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID,
        "variants": variants,
        "status": "prepared",
    })
    compile_path = _write(output_root / "compile_request.json", {
        "schema_version": "vfx_prefab_graph_batch_compile_request.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requests": compile_requests,
    })
    return {"experiment": experiment_path, "compile_request": compile_path}


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment = _read(experiment_path.resolve())
    requests = []
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        if result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        root = output_path.resolve().parent / "runtime_captures" / variant["variant"]
        requests.append({
            "candidate_id": experiment["shared_capture_seed_id"],
            "prefab_path": result["output_prefab_path"],
            "capture_dir": (root / "captures").as_posix(),
            "capture_manifest_path": (root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (root / "material_timeline.json").as_posix(),
            "source_script_fidelity": "generated_graph_no_source_scripts",
            "ignored_script_dependency_count": 0,
            "missing_script_count": 0,
            "capture_category": "explosion",
            "forced_camera_view": "front",
            "force_orthographic": True,
            "forced_orthographic_size": 3.0,
        })
    return _write(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_path.resolve().parent.name,
        "scene": "ProfessionalTeacherExplosionDebris",
        "camera": "ProfessionalTeacherExplosionDebrisCamera",
        "width": 640,
        "height": 640,
        "sampling_mode": "adaptive_runtime",
        "sampling": {
            "target_intervals": 32,
            "short_effect_target_intervals": 32,
            "min_interval_seconds": 0.01,
            "max_interval_seconds": 0.025,
            "max_duration_seconds": 1.2,
            "include_zero": True,
            "duration_sources": ["particle_system"],
        },
        "capture_material_timeline": True,
        "requests": requests,
    })


def _connected_components(mask: np.ndarray, minimum_pixels: int = 3) -> int:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    count = 0
    for y, x in np.argwhere(mask):
        if visited[y, x]:
            continue
        stack = [(int(y), int(x))]
        visited[y, x] = True
        size = 0
        while stack:
            cy, cx = stack.pop()
            size += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
        if size >= minimum_pixels:
            count += 1
    return count


def _difference_metrics(left_path: Path, right_path: Path) -> dict[str, float]:
    with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
        left = np.asarray(left_image.convert("RGB"), dtype=np.int16)
        right = np.asarray(right_image.convert("RGB"), dtype=np.int16)
    delta = np.max(np.abs(right - left), axis=2)
    visible = delta > 8
    if not visible.any():
        return {"visible_area_ratio": 0.0, "radius_p90": 0.0, "component_count": 0.0, "mae": float(np.mean(np.abs(right - left)) / 255.0)}
    height, width = visible.shape
    yy, xx = np.nonzero(visible)
    radius = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (height - 1) / 2.0) ** 2) / (min(width, height) / 2.0)
    return {
        "visible_area_ratio": float(visible.mean()),
        "radius_p90": float(np.percentile(radius, 90)),
        "component_count": float(_connected_components(visible)),
        "mae": float(np.mean(np.abs(right - left)) / 255.0),
    }


def _pair_summary(left_manifest: Path, right_manifest: Path) -> dict[str, Any]:
    left_capture = _capture_summary(left_manifest)
    right_capture = _capture_summary(right_manifest)
    left_by_time = {round(float(row["time_seconds"]), 6): row for row in left_capture["frames"]}
    right_by_time = {round(float(row["time_seconds"]), 6): row for row in right_capture["frames"]}
    frames = []
    for time_seconds in sorted(set(left_by_time) & set(right_by_time)):
        if not 0.05 <= time_seconds <= 0.65:
            continue
        metrics = _difference_metrics(_repo_root() / left_by_time[time_seconds]["path"], _repo_root() / right_by_time[time_seconds]["path"])
        frames.append({"time_seconds": time_seconds, **metrics})
    active = [row for row in frames if row["visible_area_ratio"] >= 0.0001]
    return {
        "matched_frame_count": len(frames),
        "active_difference_frame_count": len(active),
        "peak_component_count": max((row["component_count"] for row in active), default=0.0),
        "peak_radius_p90": max((row["radius_p90"] for row in active), default=0.0),
        "peak_visible_area_ratio": max((row["visible_area_ratio"] for row in active), default=0.0),
        "frames": frames,
        "left_capture": left_capture,
        "right_capture": right_capture,
    }


def _contact_sheet(summary: dict[str, Any], output: Path) -> Path:
    targets = [0.075, 0.15, 0.25, 0.4, 0.55]
    tile_size = (230, 210)
    canvas = Image.new("RGB", (tile_size[0] * len(targets), tile_size[1] * 2 + 38), "#101418")
    draw = ImageDraw.Draw(canvas)
    for row_index, (label, capture) in enumerate((("no debris", summary["left_capture"]), ("radial debris", summary["right_capture"]))):
        top = 38 + row_index * tile_size[1]
        draw.text((8, top + 6), label, fill="#ffba6a" if row_index else "#aeb8c2")
        for column, target in enumerate(targets):
            frame = min(capture["frames"], key=lambda row: abs(float(row["time_seconds"]) - target))
            with Image.open(_repo_root() / frame["path"]) as source:
                tile = ImageOps.contain(source.convert("RGB"), (tile_size[0] - 8, tile_size[1] - 28))
            left = column * tile_size[0]
            canvas.paste(tile, (left + 4, top + 24))
            draw.text((left + 6, 10), f"{float(frame['time_seconds']):.3f}s", fill="#e4e7ea")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def finalize(experiment_path: Path, output_path: Path) -> dict[str, Path]:
    experiment = _read(experiment_path.resolve())
    graphs = {row["variant"]: _read(_repo_root() / row["graph_path"]) for row in experiment["variants"]}
    comparison = _controlled_graph_comparison(graphs["no_debris"], graphs["radial_debris"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summary = _pair_summary(runtime_root / "no_debris" / "capture_manifest.json", runtime_root / "radial_debris" / "capture_manifest.json")
    left, right = summary["left_capture"], summary["right_capture"]
    gates = {
        "controlled_graph_difference_only_debris_alpha": comparison["only_debris_alpha_differs"],
        "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()),
        "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()),
        "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()),
        "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"],
        "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0,
        "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front",
        "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"],
        "multiple_debris_components": summary["peak_component_count"] >= 5,
        "debris_reaches_outside_core": summary["peak_radius_p90"] >= 0.15,
        "debris_visible_across_frames": summary["active_difference_frame_count"] >= 5,
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
        "graph_comparison": comparison,
        "difference_summary": summary,
        "quality_gates": gates,
        "validated_controller_prior": {
            "status": "eligible" if verified else "blocked",
            "effect_family": "explosion",
            "target_role": "hit",
            "judgment_axis": "debris_branches",
            "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "radial_debris"),
            "minimum_component_count": 5,
            "minimum_peak_radius_p90": 0.15,
            "allowed_use": "explosion_debris_rule_controller_only" if verified else "knowledge_prior_only",
        },
        "conclusion": "Unity reproduction supports adding multiple small outward debris branches around the explosion core." if verified else "Unity reproduction did not establish readable debris branches.",
        "status": "verified" if verified else "blocked",
    }
    report_path = _write(output_path.resolve(), report)
    sheet_path = _contact_sheet(summary, output_path.resolve().parent / "debris_pair_contact_sheet.png")
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {
        "schema_version": "course_knowledge_record.v1",
        "record_id": RULE_ID,
        "source_path": "knowledge/sources/SRC-2026-SERIES-001/ep008/visual_review_front.md",
        "heading": "爆炸主体必须可识别",
        "line_start": 18,
        "line_end": 23,
        "excerpt": experiment["professional_source"]["expert_judgment"],
        "record_type": "tutorial_fact",
        "status": "verified" if verified else "pending",
        "effect_family": "explosion",
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
            "reason": "Teacher rule may supervise the explosion debris axis only; it is not a global quality label.",
        },
    }
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {
        "schema_version": "course_knowledge_index.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_id": "professional_teacher_explosion_debris_r001",
        "input_count": 1,
        "record_count": 1,
        "record_type_counts": {"tutorial_fact": 1},
        "status_counts": {record["status"]: 1},
        "files": {"records": records_path.name},
        "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True},
        "status": "pass",
    })
    return {"report": report_path, "contact_sheet": sheet_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a controlled explosion debris Teacher reproduction.")
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
