from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from PIL import Image

from workspace.tools.vfx_generation.run_pipeline import _frame_image_stats, build_contact_sheet_pages


REQUEST_SCHEMA = "effectdemo_material_trajectory_requests.v1"
RESULT_SCHEMA = "material_trajectory_execution_result.v1"
MANIFEST_SCHEMA = "material_trajectory_execution_manifest.v1"
VISUAL_AREA_THRESHOLD = 0.001
SMOKE_IDS = (
    "mtc_001_dissolve_mat_nuge_03",
    "mtc_021_flow_distortion_mat_jinmianju_04",
    "mtc_036_emission_alpha_mat_jinzita_02",
    "mtc_051_mpb_mat_starchain_01",
    "mtc_066_texture_swap_suishi_1",
    "mtc_081_keyword_material_mat_kun_16",
    "mtc_086_negative_mat_fozu_01",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _schema_path(name: str) -> Path:
    return Path(__file__).parents[2] / "data/vfx_generation/schemas" / name


def _validate(payload: dict[str, Any], schema_name: str, label: str) -> None:
    schema = _read_json(_schema_path(schema_name))
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _curriculum_spec_paths(curriculum_root: Path) -> list[Path]:
    manifest = _read_json(curriculum_root / "manifest.json")
    paths = [(curriculum_root / str(value)).resolve() for value in manifest.get("spec_paths", [])]
    if not paths:
        raise ValueError(f"curriculum has no spec paths: {curriculum_root}")
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"curriculum spec does not exist: {missing[0]}")
    return paths


def select_spec_paths(curriculum_root: Path, mode: str, trajectory_ids: Iterable[str] = ()) -> list[Path]:
    paths = _curriculum_spec_paths(curriculum_root.resolve())
    by_id = {path.stem: path for path in paths}
    requested = tuple(trajectory_ids)
    if requested:
        missing = [value for value in requested if value not in by_id]
        if missing:
            raise ValueError(f"trajectory id is not in curriculum: {missing[0]}")
        return [by_id[value] for value in requested]
    if mode == "full":
        return paths
    if mode != "smoke":
        raise ValueError(f"unsupported execution mode: {mode}")
    missing = [value for value in SMOKE_IDS if value not in by_id]
    if missing:
        raise ValueError(f"smoke trajectory is not in curriculum: {missing[0]}")
    return [by_id[value] for value in SMOKE_IDS]


def prepare_execution_run(
    curriculum_root: Path,
    run_root: Path,
    run_id: str,
    mode: str,
    trajectory_ids: Iterable[str] = (),
    *,
    unity_project: Path = Path("UnityDemo/EffectDemo"),
    execution_project: Path | None = None,
    width: int = 512,
    height: int = 512,
    target_intervals: int = 10,
    context_map_path: Path | None = None,
) -> Path:
    curriculum_root = curriculum_root.resolve()
    run_root = run_root.resolve()
    unity_project = unity_project.resolve()
    execution_project = (execution_project or unity_project).resolve()
    if run_root.exists() and any(run_root.iterdir()):
        raise FileExistsError(f"execution run root already exists and is not empty: {run_root}")
    if width < 64 or height < 64:
        raise ValueError("capture dimensions must be at least 64x64")
    if target_intervals < 2:
        raise ValueError("target_intervals must be at least 2")

    trajectory_schema = _read_json(_schema_path("material_trajectory.schema.json"))
    trajectory_validator = Draft202012Validator(trajectory_schema)
    selected = select_spec_paths(curriculum_root, mode, trajectory_ids)
    context_by_id: dict[str, dict[str, Any]] = {}
    if context_map_path is not None:
        context_map_path = context_map_path.resolve()
        context_payload = _read_json(context_map_path)
        if context_payload.get("schema_version") != "material_trajectory_context_map.v1":
            raise ValueError(f"unsupported context renderer map: {context_map_path}")
        context_by_id = {
            str(entry["trajectory_id"]): entry
            for entry in context_payload.get("entries", [])
            if isinstance(entry, dict) and entry.get("trajectory_id")
        }
    requests: list[dict[str, Any]] = []
    categories: list[str] = []
    for spec_path in selected:
        spec = _read_json(spec_path)
        errors = list(trajectory_validator.iter_errors(spec))
        if errors:
            raise ValueError(f"invalid trajectory spec {spec_path.name}: {errors[0].message}")
        trajectory_id = str(spec["trajectory_id"])
        context = context_by_id.get(trajectory_id, {})
        context_prefab_path = context.get("prefab_path")
        if context_prefab_path is not None and not isinstance(context_prefab_path, str):
            raise ValueError(f"context renderer prefab path must be a string or null: {trajectory_id}")
        categories.append(str(spec["category"]))
        candidate_root = run_root / "candidates" / trajectory_id
        requests.append(
            {
                "trajectory_id": trajectory_id,
                "spec_path": spec_path.as_posix(),
                "capture_dir": (candidate_root / "frames").as_posix(),
                "material_timeline_path": (candidate_root / "material_timeline.json").as_posix(),
                "result_path": (candidate_root / "execution_result.json").as_posix(),
                "prefab_path": context_prefab_path,
                "context_renderer_status": str(context.get("status") or "stable_quad_baseline"),
                "context_renderer_reason": str(context.get("reason") or "no_context_renderer_mapping"),
                "track_clamps": [
                    {
                        "has_min": track.get("clamp_min") is not None,
                        "min": float(track.get("clamp_min") or 0.0),
                        "has_max": track.get("clamp_max") is not None,
                        "max": float(track.get("clamp_max") or 0.0),
                    }
                    for track in spec.get("parameter_tracks", [])
                ],
                "has_negative_mutation": spec.get("negative_mutation") is not None,
            }
        )

    run_root.mkdir(parents=True, exist_ok=True)
    request_path = run_root / "execution_requests.json"
    _write_json(
        request_path,
        {
            "schema_version": REQUEST_SCHEMA,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "execution_mode": mode if not tuple(trajectory_ids) else "selected",
            "curriculum_root": curriculum_root.as_posix(),
            "unity_project": unity_project.as_posix(),
            "execution_project": execution_project.as_posix(),
            "context_renderer_map_path": context_map_path.as_posix() if context_map_path else None,
            "context_renderer_count": sum(1 for item in requests if item.get("prefab_path")),
            "width": width,
            "height": height,
            "target_intervals": target_intervals,
            "run_resource_audit_path": (run_root / "run_resource_audit.json").as_posix(),
            "selection": {
                "count": len(requests),
                "trajectory_ids": [item["trajectory_id"] for item in requests],
                "category_counts": dict(sorted(Counter(categories).items())),
            },
            "requests": requests,
        },
    )
    return request_path


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def frame_visual_metrics(capture_dir: Path, frames: Iterable[dict[str, Any]]) -> dict[str, Any]:
    visible_ratios: list[float] = []
    for frame in frames:
        path = capture_dir / str(frame.get("path") or "")
        if not frame.get("valid") or not path.is_file():
            continue
        with Image.open(path) as image:
            visible_ratios.append(_frame_image_stats(image, background_relative=True)["visible_area_ratio"])
    maximum = max(visible_ratios, default=0.0)
    mean = sum(visible_ratios) / len(visible_ratios) if visible_ratios else 0.0
    visible = maximum >= VISUAL_AREA_THRESHOLD
    return {
        "status": "visible" if visible else "near_blank",
        "image_training_eligible": visible,
        "max_visible_area_ratio": round(maximum, 8),
        "mean_visible_area_ratio": round(mean, 8),
        "evaluated_frame_count": len(visible_ratios),
    }


def _candidate_for_contact_sheet(
    run_root: Path,
    spec: dict[str, Any],
    result: dict[str, Any],
    request: dict[str, Any],
    visual: dict[str, Any],
) -> dict[str, Any]:
    context_status = str(result.get("context_renderer_status") or "stable_quad_baseline")
    context_reason = str(result.get("context_renderer_reason") or "no_context_renderer_mapping")
    if result.get("status") != "pass":
        status = "reject"
        reasons = [str(result.get("error") or "trajectory execution failed")]
    elif not visual["image_training_eligible"]:
        status = "warn"
        reasons = [context_reason]
    else:
        status = "pass"
        reasons = []
    return {
        "candidate_id": result["trajectory_id"],
        "seed": spec["seed"],
        "capture_root": request["capture_dir"],
        "frame_count": len(result.get("frames", [])),
        "valid_frame_count": int(result.get("valid_frame_count", 0)),
        "frames": result.get("frames", []),
        "prefab_path": result.get("prefab_path"),
        "context_renderer_status": context_status,
        "context_renderer_reason": context_reason,
        "auto_eval": {
            "status": status,
            "rank_hint": 1.0 if status == "pass" else 0.5 if status == "warn" else 0.0,
            "hard_reject_reasons": reasons,
        },
    }


def finalize_execution_run(request_path: Path) -> tuple[Path, bool]:
    request_path = request_path.resolve()
    request = _read_json(request_path)
    if request.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError(f"unsupported execution request schema: {request.get('schema_version')}")
    run_root = request_path.parent
    timeline_schema = _read_json(_schema_path("material_timeline.schema.json"))
    timeline_validator = Draft202012Validator(timeline_schema)
    result_schema = _read_json(_schema_path("material_trajectory_execution_result.schema.json"))
    result_validator = Draft202012Validator(result_schema)

    results: list[dict[str, Any]] = []
    contact_candidates: list[dict[str, Any]] = []
    schema_errors: list[str] = []
    category_counts: Counter[str] = Counter()
    scope_counts: Counter[str] = Counter()
    curve_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    candidate_resource_leaks: list[str] = []
    visuals: dict[str, dict[str, Any]] = {}

    for item in request.get("requests", []):
        spec_path = Path(str(item["spec_path"]))
        result_path = Path(str(item["result_path"]))
        timeline_path = Path(str(item["material_timeline_path"]))
        if not result_path.is_file():
            raise FileNotFoundError(f"execution result is missing: {result_path}")
        if not timeline_path.is_file():
            raise FileNotFoundError(f"material timeline is missing: {timeline_path}")
        spec = _read_json(spec_path)
        result = _read_json(result_path)
        timeline = _read_json(timeline_path)
        for error in result_validator.iter_errors(result):
            schema_errors.append(f"{result_path.name}:{'.'.join(map(str, error.path))}:{error.message}")
        for error in timeline_validator.iter_errors(timeline):
            schema_errors.append(f"{timeline_path.name}:{'.'.join(map(str, error.path))}:{error.message}")
        if result.get("trajectory_id") != spec.get("trajectory_id"):
            schema_errors.append(f"{result_path.name}:trajectory_id does not match spec")
        category_counts[str(result.get("category"))] += 1
        scope_counts[str(result.get("control_scope"))] += 1
        curve_counts.update(str(value) for value in result.get("curves_executed", []))
        signal_counts.update(str(value) for value in result.get("actual_signals", []))
        event_counts["keyword"] += int(result.get("keyword_event_count", 0))
        event_counts["texture_swap"] += int(result.get("texture_swap_event_count", 0))
        event_counts["material_replace"] += int(result.get("material_replace_event_count", 0))
        resource = result.get("resource_audit") or {}
        if int(resource.get("runtime_materials_live", -1)) != 0 or int(resource.get("runtime_textures_live", -1)) != 0:
            candidate_resource_leaks.append(str(result.get("trajectory_id")))
        visual = frame_visual_metrics(Path(str(item["capture_dir"])), result.get("frames", []))
        visuals[str(result["trajectory_id"])] = visual
        results.append(result)
        contact_candidates.append(_candidate_for_contact_sheet(run_root, spec, result, item, visual))

    resource_path = Path(str(request["run_resource_audit_path"]))
    run_resource = _read_json(resource_path) if resource_path.is_file() else {}
    run_resource_clean = int(run_resource.get("render_textures_live", -1)) == 0
    all_passed = bool(results) and all(result.get("status") == "pass" for result in results)
    all_frames_valid = all(int(result.get("valid_frame_count", 0)) == len(result.get("frames", [])) for result in results)
    resources_clean = not candidate_resource_leaks and run_resource_clean
    execution_passed = all_passed and all_frames_valid and not schema_errors and resources_clean
    near_blank_ids = sorted(trajectory_id for trajectory_id, visual in visuals.items() if not visual["image_training_eligible"])

    pages = build_contact_sheet_pages(
        run_root,
        contact_candidates,
        [],
        run_root / "contact_sheets",
        page_size=8,
        run_id=str(request["run_id"]),
        unity_project=Path("UnityDemo/EffectDemo"),
        scene="MaterialTrajectoryRuntimePreview",
        camera="MaterialTrajectoryCaptureCamera",
        resolution=(int(request["width"]), int(request["height"])),
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": request["run_id"],
        "execution_mode": request.get("execution_mode"),
        "curriculum_root": request["curriculum_root"],
        "unity_project": request["unity_project"],
        "execution_project": request["execution_project"],
        "execution_uses_isolated_staging": Path(str(request["unity_project"])).resolve() != Path(str(request["execution_project"])).resolve(),
        "unity_version": "2022.3.16f1c1",
        "render_pipeline": "URP 14.0.9",
        "capture_sync": "trajectory_apply_at_late_update -> material_snapshot -> camera_render",
        "spec_count": len(results),
        "pass_count": sum(result.get("status") == "pass" for result in results),
        "fail_count": sum(result.get("status") != "pass" for result in results),
        "valid_frame_count": sum(int(result.get("valid_frame_count", 0)) for result in results),
        "frame_count": sum(len(result.get("frames", [])) for result in results),
        "category_counts": dict(sorted(category_counts.items())),
        "scope_counts": dict(sorted(scope_counts.items())),
        "curve_counts": dict(sorted(curve_counts.items())),
        "actual_signal_counts": dict(sorted(signal_counts.items())),
        "event_counts": dict(sorted(event_counts.items())),
        "schema_error_count": len(schema_errors),
        "schema_errors": schema_errors,
        "resource_audit": {
            "candidate_leak_count": len(candidate_resource_leaks),
            "candidate_leaks": candidate_resource_leaks,
            "run_resource_audit_path": _relative(resource_path, run_root),
            "run_render_texture_live": int(run_resource.get("render_textures_live", -1)),
            "clean": resources_clean,
        },
        "visual_evidence": {
            "status": "complete" if not near_blank_ids else "partial",
            "visible_area_threshold": VISUAL_AREA_THRESHOLD,
            "visible_candidate_count": len(results) - len(near_blank_ids),
            "near_blank_candidate_count": len(near_blank_ids),
            "near_blank_candidate_ids": near_blank_ids,
            "image_training_eligible_count": len(results) - len(near_blank_ids),
            "policy": "near_blank candidates remain material-state valid but are excluded from image-conditioned training",
        },
        "status": "pass" if execution_passed else "fail",
        "contact_sheet_paths": [str(page["path"]) for page in pages],
        "candidates": [
            {
                "trajectory_id": result["trajectory_id"],
                "category": result["category"],
                "label": result["label"],
                "control_scope": result["control_scope"],
                "status": result["status"],
                "expected_signals": result["expected_signals"],
                "actual_signals": result["actual_signals"],
                "visual_status": visuals[result["trajectory_id"]]["status"],
                "image_training_eligible": visuals[result["trajectory_id"]]["image_training_eligible"],
                "max_visible_area_ratio": visuals[result["trajectory_id"]]["max_visible_area_ratio"],
                "mean_visible_area_ratio": visuals[result["trajectory_id"]]["mean_visible_area_ratio"],
                "prefab_path": result.get("prefab_path"),
                "context_renderer_status": result.get("context_renderer_status") or "stable_quad_baseline",
                "context_renderer_reason": result.get("context_renderer_reason") or "no_context_renderer_mapping",
                "effective_control_scope": result.get("effective_control_scope") or result.get("control_scope"),
                "result_path": _relative(Path(str(item["result_path"])), run_root),
                "material_timeline_path": _relative(Path(str(item["material_timeline_path"])), run_root),
            }
            for item, result in zip(request.get("requests", []), results)
        ],
    }
    _validate(manifest, "material_trajectory_execution_manifest.schema.json", "execution manifest")
    manifest_path = run_root / "run_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path, execution_passed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and finalize EffectDemo MaterialTrajectorySpec execution runs.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--curriculum-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    prepare.add_argument("--trajectory-id", action="append", default=[])
    prepare.add_argument("--unity-project", type=Path, default=Path("UnityDemo/EffectDemo"))
    prepare.add_argument("--execution-project", type=Path)
    prepare.add_argument("--width", type=int, default=512)
    prepare.add_argument("--height", type=int, default=512)
    prepare.add_argument("--target-intervals", type=int, default=10)
    prepare.add_argument("--context-map", type=Path)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--requests", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            path = prepare_execution_run(
                args.curriculum_root,
                args.run_root,
                args.run_id,
                args.mode,
                args.trajectory_id,
                unity_project=args.unity_project,
                execution_project=args.execution_project,
                width=args.width,
                height=args.height,
                target_intervals=args.target_intervals,
                context_map_path=args.context_map,
            )
            print(json.dumps({"success": True, "request_path": path.as_posix()}, ensure_ascii=False, indent=2))
            return 0
        manifest_path, passed = finalize_execution_run(args.requests)
        print(json.dumps({"success": passed, "manifest_path": manifest_path.as_posix()}, ensure_ascii=False, indent=2))
        return 0 if passed else 2
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
