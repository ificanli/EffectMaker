"""Prepare and validate the five-category EffectDemo runtime-capture regression."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


CASES = (
    (
        "instant",
        "capture_v2_instant_rayline",
        "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/Battle/Fx_rayline/eff/Fx_rayline_body.prefab",
    ),
    (
        "moving",
        "capture_v2_moving_probe",
        "__effectdemo_capture_moving_probe__",
    ),
    (
        "ground",
        "capture_v2_ground_tip_circle",
        "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/Bundles/Battle/Prefab/Effect/BOSS/Fx_Tip_Common_Circle.prefab",
    ),
    (
        "ui",
        "capture_v2_ui_gene_lock",
        "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/UI/FX_ui_jiyinsuo/eff/FX_ui_jiyinsuo.prefab",
    ),
    (
        "script_material",
        "capture_v2_script_material_probe",
        "__effectdemo_material_state_probe__",
    ),
)


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def prepare(project_path: Path, output_root: Path) -> Path:
    project_path = project_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"capture regression output already exists and is not empty: {output_root}")
    requests = []
    for category, candidate_id, prefab_path in CASES:
        if not prefab_path.startswith("__") and not (project_path / prefab_path).is_file():
            raise FileNotFoundError(f"regression Prefab is missing in execution project: {prefab_path}")
        candidate_root = output_root / "cases" / candidate_id
        requests.append(
            {
                "candidate_id": candidate_id,
                "prefab_path": prefab_path,
                "capture_dir": (candidate_root / "captures").as_posix(),
                "capture_manifest_path": (candidate_root / "capture_manifest.json").as_posix(),
                "material_timeline_path": (candidate_root / "material_timeline.json").as_posix(),
                "source_script_fidelity": "no_ignored_script_dependencies",
                "ignored_script_dependency_count": 0,
                "missing_script_count": 0,
                "capture_category": category,
            }
        )
    payload = {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "unity_project": project_path.as_posix(),
        "scene": "RuntimeCaptureV2Regression",
        "camera": "RuntimeCaptureV2Camera",
        "width": 640,
        "height": 360,
        "time_points_seconds": [],
        "sampling_mode": "adaptive_runtime",
        "sampling": {
            "target_intervals": 10,
            "min_interval_seconds": 0.02,
            "max_interval_seconds": 0.1,
            "max_duration_seconds": 8.0,
            "include_zero": True,
            "duration_sources": ["particle_system", "animator", "animation", "playable_director", "trail_renderer", "custom_script_unknown"],
        },
        "capture_material_timeline": True,
        "requests": requests,
    }
    return _write(output_root / "render_requests.json", payload)


def finalize(output_root: Path, report_path: Path) -> Path:
    output_root = output_root.resolve()
    request = _read(output_root / "render_requests.json")
    rows = []
    for item in request["requests"]:
        manifest_path = Path(item["capture_manifest_path"])
        timeline_path = Path(item["material_timeline_path"])
        if not manifest_path.is_file() or not timeline_path.is_file():
            raise FileNotFoundError(f"regression output is missing: {item['candidate_id']}")
        manifest = _read(manifest_path)
        timeline = _read(timeline_path)
        camera_candidates = manifest.get("camera_selection", {}).get("candidates") or []
        frames = manifest.get("frames") or []
        rows.append(
            {
                "candidate_id": item["candidate_id"],
                "category": item["capture_category"],
                "prefab_path": item["prefab_path"],
                "manifest_path": manifest_path.as_posix(),
                "timeline_path": timeline_path.as_posix(),
                "pipeline_version": manifest.get("capture_pipeline_version"),
                "instance_ids": [manifest.get("bounds_probe_instance_id"), manifest.get("camera_probe_instance_id"), manifest.get("capture_instance_id")],
                "distinct_instance_ids": manifest.get("distinct_instance_ids"),
                "camera_status": manifest.get("camera_selection", {}).get("status"),
                "selected_camera_view": manifest.get("camera_selection", {}).get("selected_view"),
                "camera_candidate_count": len(camera_candidates),
                "context_status": manifest.get("context", {}).get("status"),
                "frame_count": len(frames),
                "valid_frame_count": manifest.get("valid_frame_count"),
                "all_frames_have_actual_time": all(frame.get("simulation_elapsed_seconds") is not None and frame.get("wall_clock_elapsed_seconds") is not None and frame.get("unity_frame_count") is not None for frame in frames),
                "max_simulation_time_drift": max((abs(float(frame.get("simulation_elapsed_seconds") or 0.0) - float(frame.get("requested_time_seconds") or 0.0)) for frame in frames), default=0.0),
                "max_visible_area_ratio": max((float((frame.get("pixel_metrics") or {}).get("visible_area_ratio") or 0.0) for frame in frames), default=0.0),
                "cropped_frame_count": sum(bool((frame.get("pixel_metrics") or {}).get("cropped")) for frame in frames),
                "duration_seconds": manifest.get("duration_seconds"),
                "sample_interval_seconds": manifest.get("sample_interval_seconds"),
                "duration_clamped": manifest.get("duration_clamped"),
                "technical_frame_eligible": manifest.get("technical_frame_eligible"),
                "image_sequence_training_eligible": manifest.get("image_sequence_training_eligible"),
                "full_visual_training_eligible": manifest.get("full_visual_training_eligible"),
                "visual_evidence_status": manifest.get("visual_evidence_status"),
                "global_shader_state_status": manifest.get("global_shader_state_status"),
                "has_unenumerated_property_block_values": manifest.get("has_unenumerated_property_block_values"),
                "material_delta_count": (timeline.get("summary") or {}).get("delta_count", 0),
                "has_dynamic_material_state": (timeline.get("summary") or {}).get("has_dynamic_material_state", False),
            }
        )
    by_category = {row["category"]: row for row in rows}
    expected = {case[0] for case in CASES}
    gates = {
        "all_categories_present": set(by_category) == expected,
        "all_pipeline_v2": all(row["pipeline_version"] == "play_mode_runtime_isolated_multiview.v2" for row in rows),
        "all_instances_isolated": all(row["distinct_instance_ids"] and len(set(row["instance_ids"])) == 3 for row in rows),
        "all_three_camera_candidates": all(row["camera_candidate_count"] >= 3 for row in rows),
        "all_camera_results_classified": all(row["camera_status"] in {"selected_visible_view", "no_visible_camera_candidate"} for row in rows),
        "all_context_results_classified": all(row["context_status"] in {"standard_context_ready", "incomplete_context"} for row in rows),
        "all_frames_have_actual_time": all(row["all_frames_have_actual_time"] for row in rows),
        "all_capture_files_valid": all(row["frame_count"] > 0 and row["frame_count"] == row["valid_frame_count"] for row in rows),
        "instant_sampling_fine": float(by_category["instant"]["sample_interval_seconds"] or 1.0) <= 0.1,
        "instant_simulation_time_stable": float(by_category["instant"]["max_simulation_time_drift"]) <= max(0.025, float(by_category["instant"]["sample_interval_seconds"] or 0.0) * 1.25),
        "moving_view_visible": float(by_category["moving"]["max_visible_area_ratio"]) >= 0.001,
        "ground_view_visible": float(by_category["ground"]["max_visible_area_ratio"]) >= 0.001,
        "script_material_state_dynamic": bool(by_category["script_material"]["has_dynamic_material_state"]),
        "controlled_probe_global_and_mpb_instrumented": by_category["script_material"]["global_shader_state_status"] == "instrumented"
        and not by_category["script_material"]["has_unenumerated_property_block_values"]
        and bool(by_category["script_material"]["full_visual_training_eligible"]),
        "unknown_globals_not_full_training": all(
            row["global_shader_state_status"] != "instrumented" and not row["full_visual_training_eligible"]
            for row in rows if row["category"] != "script_material"
        ),
        "request_supports_eight_seconds": float(request["sampling"]["max_duration_seconds"]) >= 8.0,
    }
    report = {
        "schema_version": "effectdemo_runtime_capture_regression.v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(rows),
        "categories": sorted(by_category),
        "cases": sorted(rows, key=lambda row: row["category"]),
        "quality_gates": gates,
        "status": "pass" if len(rows) == 5 and all(gates.values()) else "blocked",
    }
    schema = _read(_repo_root() / "workspace/data/vfx_generation/schemas/runtime_capture_regression_report.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        raise ValueError(f"runtime capture regression schema error: {errors[0].message}")
    return _write(report_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or finalize EffectDemo runtime capture v2 regression.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("--project", type=Path, required=True)
    prepare_command.add_argument("--output-root", type=Path, required=True)
    finalize_command = commands.add_parser("finalize")
    finalize_command.add_argument("--output-root", type=Path, required=True)
    finalize_command.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = prepare(args.project, args.output_root) if args.command == "prepare" else finalize(args.output_root, args.report)
        status = "prepared" if args.command == "prepare" else _read(path)["status"]
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": status in {"prepared", "pass"}, "path": path.as_posix(), "status": status}, ensure_ascii=False, indent=2))
    return 0 if status in {"prepared", "pass"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
