"""Build a controlled Unity reproduction for slash contact-hit placement."""

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
from .slash_family_generator import HIT_TEXTURE


SCHEMA_VERSION = "vfx_professional_slash_hit_teacher_reproduction.v1"
RULE_ID = "professional_slash_contact_focus_r001"
SHARED_CAPTURE_SEED_ID = "professional_slash_hit_pair_r001"
CONTACT_POSITION = [1.45, -0.05, 0.0]
ORTHOGRAPHIC_SIZE = 2.0


def _contact_screen_position() -> tuple[float, float]:
    diameter = ORTHOGRAPHIC_SIZE * 2.0
    return 0.5 + CONTACT_POSITION[0] / diameter, 0.5 - CONTACT_POSITION[1] / diameter


def _role_node(graph: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [node for node in graph.get("nodes") or [] if node.get("role") == role]
    if len(matches) != 1:
        raise ValueError(f"exactly one {role} node expected, found {len(matches)}")
    return matches[0]


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = copy.deepcopy(source)
    graph.pop("graph_id", None)
    _role_node(graph, "residual")["active_self"] = False
    hit_node = _role_node(graph, "hit")
    hit = _single_role_component(graph, "particle_systems", "hit")
    hit["parameters"].update(
        {
            "start_delay_max": 0.075,
            "start_lifetime_max": 0.18,
            "start_speed_max": 0.0,
            "start_size_max": 0.92,
            "burst_particle_count": 1,
            "shape_enabled": False,
            "shape_type": "disabled",
            "shape_radius": 0.0,
            "end_size_multiplier": 0.25,
            "start_color_rgba": [0.9, 1.0, 1.0, 1.0],
            "texture_asset_path": HIT_TEXTURE,
        }
    )
    if variant == "center_misplaced":
        hit_node["transform"]["local_position"] = [0.0, 0.0, 0.0]
    elif variant == "contact_aligned":
        hit_node["transform"]["local_position"] = list(CONTACT_POSITION)
    else:
        raise ValueError(f"unsupported slash hit variant: {variant}")
    graph["condition"] = {
        "prompt": "专业刀光接触点局部亮点对照",
        "effect_family": "slash",
        "style_family": "cartoon",
        "seed": 20262312,
        "parent_prefab_path": None,
    }
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {
        "source_dataset_id": "professional_slash_hit_teacher_r001",
        "source_run_id": RULE_ID,
        "exporter": "prefab_graph_constrained.v1",
        "assumptions": [
            "OuterBlade and InnerSupport remain identical visual references in both variants.",
            "DirectionTrail is disabled in both variants.",
            "Only ContactHit local position differs.",
            "The experiment validates contact-focus placement, not global slash quality.",
        ],
    }
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _graph_comparison(center: dict[str, Any], aligned: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(center), copy.deepcopy(aligned)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    node_index = next(index for index, node in enumerate(left["nodes"]) if node.get("role") == "hit")
    prefix = f"nodes[{node_index}].transform.local_position"
    return {
        "difference_paths": paths,
        "expected_difference_prefix": prefix,
        "only_hit_position_differs": bool(paths) and all(path.startswith(prefix) for path in paths),
    }


def prepare(source_graph: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional slash hit output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, requests = [], []
    for variant in ("center_misplaced", "contact_aligned"):
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
    experiment = _write(
        output_root / "experiment_manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rule_id": RULE_ID,
            "source_graph_path": _portable(source_graph),
            "professional_source": {
                "source_id": "SRC-2026-001",
                "title": "20260415点评-一定要练基本功",
                "author": "三生路_王先生特效",
                "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md",
                "license_scope": "internal_learning_only_no_redistribution",
                "timecodes": ["00:33:12.540-00:34:09.000", "00:36:15.900-00:37:45.450"],
                "frame_paths": [
                    "knowledge/sources/SRC-2026-001/visual_review_22-44/2007_ground_hit.jpg",
                    "knowledge/sources/SRC-2026-001/visual_review_22-44/contact_11_33-34.jpg",
                    "knowledge/sources/SRC-2026-001/visual_review_22-44/2176_floating_blade.jpg",
                    "knowledge/sources/SRC-2026-001/visual_review_22-44/contact_14_36-37.jpg",
                ],
                "expert_judgment": "刀光命中反馈应集中在真实接触点或受力端，成为局部视觉重点；不能把亮点堆在刀光中心而让落点失焦。",
                "judgment_axes": ["composition", "contact_readability", "layer_separation"],
            },
            "controlled_variables": {
                "changed": ["contact_hit.transform.local_position"],
                "held_constant": [
                    "blade mesh",
                    "hit material",
                    "hit texture",
                    "hit timing",
                    "hit size",
                    "camera",
                    "capture seed",
                ],
            },
            "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID,
            "contact_position": CONTACT_POSITION,
            "variants": variants,
            "status": "prepared",
        },
    )
    return {
        "experiment": experiment,
        "compile_request": _write(
            output_root / "compile_request.json",
            {
                "schema_version": "vfx_prefab_graph_batch_compile_request.v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "requests": requests,
            },
        ),
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
            "scene": "ProfessionalTeacherSlashHit",
            "camera": "ProfessionalTeacherSlashHitCamera",
            "width": 640,
            "height": 640,
            "sampling_mode": "adaptive_runtime",
            "sampling": {
                "target_intervals": 24,
                "short_effect_target_intervals": 24,
                "min_interval_seconds": 0.01,
                "max_interval_seconds": 0.025,
                "max_duration_seconds": 0.6,
                "include_zero": True,
                "duration_sources": ["particle_system"],
            },
            "capture_material_timeline": True,
            "requests": requests,
        },
    )


def _luminance(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722


def _region_mean(image: np.ndarray, center_x: float, center_y: float, radius: float = 0.1) -> float:
    height, width = image.shape
    yy, xx = np.ogrid[:height, :width]
    x = center_x * max(1, width - 1)
    y = center_y * max(1, height - 1)
    mask = (xx - x) ** 2 + (yy - y) ** 2 <= (radius * min(width, height)) ** 2
    return float(image[mask].mean()) if mask.any() else 0.0


def _region_top_mean(image: np.ndarray, center_x: float, center_y: float, radius: float = 0.08, fraction: float = 0.05) -> float:
    height, width = image.shape
    yy, xx = np.ogrid[:height, :width]
    x = center_x * max(1, width - 1)
    y = center_y * max(1, height - 1)
    mask = (xx - x) ** 2 + (yy - y) ** 2 <= (radius * min(width, height)) ** 2
    values = image[mask]
    if values.size == 0:
        return 0.0
    count = max(1, int(values.size * fraction))
    return float(np.partition(values, values.size - count)[-count:].mean())


def _summary(manifest_path: Path) -> dict[str, Any]:
    capture = _capture_summary(manifest_path)
    contact_x, contact_y = _contact_screen_position()
    frames = []
    for row in capture["frames"]:
        image = _luminance(_repo_root() / row["path"])
        frames.append(
            {
                "time_seconds": float(row["time_seconds"]),
                "path": row["path"],
                "center_luminance": _region_mean(image, 0.5, 0.5, 0.06),
                "contact_luminance": _region_mean(image, contact_x, contact_y, 0.06),
                "center_peak_luminance": _region_top_mean(image, 0.5, 0.5),
                "contact_peak_luminance": _region_top_mean(image, contact_x, contact_y),
            }
        )
    return {"capture": capture, "frames": frames}


def _pair_metrics(center: dict[str, Any], aligned: dict[str, Any]) -> dict[str, float]:
    center_by_time = {round(float(row["time_seconds"]), 6): row for row in center["frames"]}
    aligned_by_time = {round(float(row["time_seconds"]), 6): row for row in aligned["frames"]}
    endpoint_gains = []
    endpoint_peak_gains = []
    center_gains = []
    positive_points = []
    for time_seconds in sorted(set(center_by_time) & set(aligned_by_time)):
        left = center_by_time[time_seconds]
        right = aligned_by_time[time_seconds]
        endpoint_gains.append(float(right["contact_luminance"] - left["contact_luminance"]))
        endpoint_peak_gains.append(float(right["contact_peak_luminance"] - left["contact_peak_luminance"]))
        center_gains.append(float(left["center_luminance"] - right["center_luminance"]))
        left_image = _luminance(_repo_root() / left["path"])
        right_image = _luminance(_repo_root() / right["path"])
        positive = np.maximum(right_image - left_image, 0.0)
        mask = positive >= 0.04
        if float(mask.mean()) < 0.00005:
            continue
        yy, xx = np.nonzero(mask)
        weights = positive[mask].astype(np.float64)
        positive_points.append(
            (
                float(np.average(xx, weights=weights) / max(1, mask.shape[1] - 1)),
                float(np.average(yy, weights=weights) / max(1, mask.shape[0] - 1)),
            )
        )
    target_x, target_y = _contact_screen_position()
    distances = [((x - target_x) ** 2 + (y - target_y) ** 2) ** 0.5 for x, y in positive_points]
    return {
        "active_positive_difference_frame_count": float(len(positive_points)),
        "max_contact_luminance_gain": max(endpoint_gains, default=0.0),
        "max_contact_peak_luminance_gain": max(endpoint_peak_gains, default=0.0),
        "mean_positive_contact_luminance_gain": float(np.mean([value for value in endpoint_gains if value > 0.0])) if any(value > 0.0 for value in endpoint_gains) else 0.0,
        "max_center_luminance_reduction": max(center_gains, default=0.0),
        "mean_positive_delta_centroid_x": float(np.mean([point[0] for point in positive_points])) if positive_points else 0.5,
        "mean_positive_delta_centroid_y": float(np.mean([point[1] for point in positive_points])) if positive_points else 0.5,
        "mean_positive_delta_target_distance": float(np.mean(distances)) if distances else 1.0,
    }


def _contact_sheet(summaries: dict[str, dict[str, Any]], output: Path) -> Path:
    targets = [0.05, 0.075, 0.1, 0.125, 0.15]
    tile_width, tile_height = 220, 205
    canvas = Image.new("RGB", (tile_width * len(targets), tile_height * 2 + 34), "#101418")
    draw = ImageDraw.Draw(canvas)
    for row_index, variant in enumerate(("center_misplaced", "contact_aligned")):
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
    graph_comparison = _graph_comparison(graphs["center_misplaced"], graphs["contact_aligned"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _summary(runtime_root / variant / "capture_manifest.json") for variant in ("center_misplaced", "contact_aligned")}
    metrics = _pair_metrics(summaries["center_misplaced"], summaries["contact_aligned"])
    left = summaries["center_misplaced"]["capture"]
    right = summaries["contact_aligned"]["capture"]
    gates = {
        "controlled_graph_difference_only_hit_position": graph_comparison["only_hit_position_differs"],
        "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()),
        "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()),
        "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()),
        "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"],
        "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0,
        "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front",
        "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"],
        "contact_difference_has_frames": metrics["active_positive_difference_frame_count"] >= 3,
        "contact_region_gains_luminance": metrics["max_contact_luminance_gain"] >= 0.012,
        "contact_bright_pixels_gain_luminance": metrics["max_contact_peak_luminance_gain"] >= 0.08,
        "positive_difference_lands_near_contact": metrics["mean_positive_delta_target_distance"] <= 0.12,
    }
    verified = all(gates.values())
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "professional_source": experiment["professional_source"],
        "controlled_variables": experiment["controlled_variables"],
        "experiment_manifest_path": _portable(experiment_path.resolve()),
        "unity": {
            "version": "2022.3.16f1c1",
            "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001",
            "render_pipeline": "URP 14.0.9",
            "capture_mode": "play_mode_runtime_isolated_multiview.v2",
        },
        "graph_comparison": graph_comparison,
        "variants": summaries,
        "comparison": metrics,
        "quality_gates": gates,
        "validated_controller_prior": {
            "status": "eligible" if verified else "blocked",
            "effect_family": "slash",
            "target_role": "hit",
            "judgment_axis": "contact_focus",
            "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "contact_aligned"),
            "contact_position": experiment["contact_position"],
            "minimum_contact_luminance_gain": 0.012,
            "minimum_contact_peak_luminance_gain": 0.08,
            "maximum_contact_centroid_distance": 0.12,
            "allowed_use": "slash_contact_hit_controller_only" if verified else "knowledge_prior_only",
        },
        "conclusion": "Unity reproduction supports placing the slash hit flash at the attack contact point." if verified else "Unity reproduction did not satisfy slash contact-focus gates.",
        "status": "verified" if verified else "blocked",
    }
    report_path = _write(output_path.resolve(), report)
    sheet_path = _contact_sheet(summaries, output_path.resolve().parent / "slash_hit_pair_contact_sheet.png")
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {
        "schema_version": "course_knowledge_record.v1",
        "record_id": RULE_ID,
        "source_path": "knowledge/sources/SRC-2026-001/visual_review_middle.md",
        "heading": "地面打击与接触亮点",
        "line_start": 52,
        "line_end": 76,
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
            "reason": "Teacher rule may supervise slash contact-hit placement only; it is not a global quality label.",
        },
    }
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(
        teacher_root / "course_knowledge_index.json",
        {
            "schema_version": "course_knowledge_index.v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "index_id": "professional_teacher_slash_hit_r001",
            "input_count": 1,
            "record_count": 1,
            "record_type_counts": {"tutorial_fact": 1},
            "status_counts": {record["status"]: 1},
            "files": {"records": records_path.name},
            "policy": {
                "source_text_is_evidence_not_training_label": True,
                "verified_course_fact_still_requires_unity_reproduction": True,
                "not_visible_is_not_training_data": True,
            },
            "status": "pass",
        },
    )
    return {"report": report_path, "contact_sheet": sheet_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a controlled slash contact-hit Teacher reproduction.")
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
