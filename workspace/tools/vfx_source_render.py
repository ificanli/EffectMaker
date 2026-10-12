"""Prepare and finalize render-review runs for imported Unity VFX Prefabs.

The source-ingest step proves that a Prefab's dependencies were copied.  This
module turns that structural evidence into reviewable render candidates without
losing the material -> shader -> tagged texture relationship that an eventual
material-selection model needs.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from workspace.tools.vfx_generation.run_pipeline import build_run_outputs


REQUEST_SCHEMA = "effectdemo_source_render_requests.v1"
DEFAULT_SCENE = "SourceIngestBatchScene"
DEFAULT_CAMERA = "SourceIngestReviewCamera"
DEFAULT_RESOLUTION = (960, 540)
DEFAULT_TIME_POINTS = (0.0, 0.08, 0.16, 0.32, 0.64)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _relative_path(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_prefab_paths(source_sample: dict[str, Any]) -> list[str]:
    prefabs: list[str] = []
    for layer in _as_list(source_sample.get("extracted", {}).get("layers")):
        if not isinstance(layer, dict):
            continue
        prefabs.extend(
            str(path)
            for path in _as_list(layer.get("source_files"))
            if str(path).lower().endswith(".prefab")
        )
    return sorted(set(prefabs), key=str.casefold)


def _material_dependencies_by_prefab(source_manifest: dict[str, Any]) -> dict[str, list[str]]:
    material_paths: dict[str, list[str]] = {}
    for dependency in _as_list(source_manifest.get("dependencies")):
        if not isinstance(dependency, dict) or dependency.get("dependency_type") != "material":
            continue
        if dependency.get("status") != "resolved":
            continue
        source = dependency.get("from_path")
        target = dependency.get("to_path")
        if not isinstance(source, str) or not isinstance(target, str) or not source.lower().endswith(".prefab"):
            continue
        material_paths.setdefault(source, []).append(target)
    return {path: sorted(set(materials), key=str.casefold) for path, materials in material_paths.items()}


def _ignored_script_dependencies_by_prefab(source_manifest: dict[str, Any]) -> dict[str, list[str]]:
    scripts: dict[str, list[str]] = {}
    for dependency in _as_list(source_manifest.get("dependencies")):
        if not isinstance(dependency, dict) or dependency.get("dependency_type") != "script" or dependency.get("status") != "ignored":
            continue
        source = dependency.get("from_path")
        target = dependency.get("to_path")
        if isinstance(source, str) and source.lower().endswith(".prefab") and isinstance(target, str):
            scripts.setdefault(source, []).append(target)
    return {path: sorted(set(paths), key=str.casefold) for path, paths in scripts.items()}


def _material_selection_index(training_example: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    selection = training_example.get("inputs", {}).get("material_selection", {})
    if not isinstance(selection, dict):
        return {}, {}
    materials = {
        str(material["material_path"]): material
        for material in _as_list(selection.get("materials"))
        if isinstance(material, dict) and isinstance(material.get("material_path"), str)
    }
    summary = {
        "texture_tag_index_path": selection.get("texture_tag_index_path"),
        "texture_tag_index_status": selection.get("texture_tag_index_status"),
        "texture_tag_index_record_count": selection.get("texture_tag_index_record_count"),
        "texture_tagging_status": selection.get("texture_tagging_status"),
        "selection_basis": _as_list(selection.get("selection_basis")),
    }
    return materials, summary


def _candidate_id(prefab_path: str, ordinal: int) -> str:
    stem = Path(prefab_path).stem
    normalized = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "prefab"
    return f"source_prefab_{ordinal:03d}_{normalized}"


def _candidate_spec(
    *,
    source_id: str,
    source_sample_id: str,
    run_id: str,
    candidate_id: str,
    prefab_path: str,
    material_paths: Iterable[str],
    material_index: dict[str, dict[str, Any]],
    selection_summary: dict[str, Any],
    unity_project: Path,
    scene: str,
    camera: str,
    resolution: tuple[int, int],
    time_points: Iterable[float],
    training_case: dict[str, Any] | None = None,
    sampling_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    material_paths = list(material_paths)
    resolved_materials = [material_index[path] for path in material_paths if path in material_index]
    missing_materials = [path for path in material_paths if path not in material_index]
    case_material_selection = training_case.get("material_selection") if isinstance(training_case, dict) else None
    target_style_profile = training_case.get("target_style_profile") if isinstance(training_case, dict) else None
    observed_style_profile = training_case.get("observed_style_profile") if isinstance(training_case, dict) else None
    payload = {
        "schema_version": "vfxspec.v1",
        "effect_family": "source_ingest",
        "effect_type": "imported_prefab",
        "adapter": {
            "name": "source_ingest.render_review",
            "version": "0.1.0",
            "generator_family": "source_prefab_render",
            "specialized_metrics": [
                "source_dependency_completeness",
                "render_readability",
                "material_selection_traceability",
            ],
        },
        "prompt": f"Render-review imported Unity VFX Prefab: {Path(prefab_path).name}",
        "negative_prompt": "Do not accept source structure as visual evidence. Do not detach materials from shaders or tagged textures.",
        "reference": {
            "source_id": source_id,
            "case_id": str(training_case.get("case_id") or source_sample_id) if isinstance(training_case, dict) else source_sample_id,
            "frames": [],
        },
        "generation": {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "seed": None,
            "generator": "source_prefab_render",
            "generator_version": "0.1.0",
            "parent_candidate_id": None,
        },
        "layers": [
            {
                "role": "source_prefab",
                "status": "active",
                "topology": "imported_prefab",
                "shape_parameters": {"source_prefab_path": prefab_path},
                "material_parameters": {
                    "material_selection": case_material_selection or {
                        **selection_summary,
                        "prefab_material_count": len(material_paths),
                        "resolved_material_count": len(resolved_materials),
                        "missing_material_selection_count": len(missing_materials),
                        "missing_material_paths": missing_materials,
                        "materials": resolved_materials,
                    }
                },
                "timing_parameters": {"duration_seconds": None, "peak_time_seconds": None},
                "constraints": [
                    "Use the imported material, shader, and texture binding without substitutions.",
                    "Human review is required before this candidate becomes a training label.",
                ],
            }
        ],
        "render_plan": {
            "unity_project": unity_project.resolve().as_posix(),
            "scene": scene,
            "camera": camera,
            "resolution": [resolution[0], resolution[1]],
            "time_points_seconds": [round(float(value), 3) for value in time_points],
        },
    }
    if sampling_plan:
        payload["render_plan"]["sampling_mode"] = "adaptive_runtime"
        payload["render_plan"]["sampling_plan"] = sampling_plan
    if isinstance(training_case, dict):
        payload["training_case_id"] = training_case.get("case_id")
    if isinstance(target_style_profile, dict):
        payload["target_style_profile"] = target_style_profile
    if isinstance(observed_style_profile, dict):
        payload["observed_style_profile"] = observed_style_profile
    return payload


def prepare_render_run(
    source_dir: Path,
    run_root: Path,
    *,
    unity_project: Path,
    prefab_paths: Iterable[str] | None = None,
    time_points: Iterable[float] = DEFAULT_TIME_POINTS,
    resolution: tuple[int, int] = DEFAULT_RESOLUTION,
    scene: str = DEFAULT_SCENE,
    camera: str = DEFAULT_CAMERA,
    run_id: str | None = None,
    training_cases: Iterable[dict[str, Any]] | None = None,
    adaptive_runtime: bool = False,
    target_intervals: int = 10,
    min_interval_seconds: float = 0.02,
    max_interval_seconds: float = 0.1,
    max_duration_seconds: float = 8.0,
) -> dict[str, Path]:
    """Create candidate specs plus the Unity-side request file for one source sample."""
    source_dir = source_dir.resolve()
    run_root = run_root.resolve()
    source_manifest = _read_json(source_dir / "source_manifest.json")
    source_sample = _read_json(source_dir / "source_sample.json")
    training_example = _read_json(source_dir / "training_example.json")
    source_id = str(source_sample.get("source_id") or source_manifest.get("source_id") or source_dir.name)
    source_sample_id = str(source_sample.get("sample_id") or source_dir.name)
    run_id = str(run_id or training_example.get("run_id") or f"{source_id.lower()}_r001")
    training_case_by_prefab = {
        str(case["prefab_path"]): case
        for case in (training_cases or [])
        if isinstance(case, dict) and isinstance(case.get("prefab_path"), str)
    }
    available_prefabs = _source_prefab_paths(source_sample)
    selected_prefabs = sorted(set(prefab_paths or training_case_by_prefab or available_prefabs), key=str.casefold)
    unknown_prefabs = sorted(set(selected_prefabs) - set(available_prefabs), key=str.casefold)
    if unknown_prefabs:
        raise ValueError(f"requested Prefab path is not in the source sample: {unknown_prefabs[0]}")
    if not selected_prefabs:
        raise ValueError("source sample does not contain any Prefab paths")
    if run_root.exists() and any(run_root.iterdir()):
        raise FileExistsError(f"render run already exists and is not empty: {run_root}")

    normalized_times = [] if adaptive_runtime else [round(float(value), 3) for value in time_points]
    if not adaptive_runtime and (not normalized_times or any(value < 0 for value in normalized_times)):
        raise ValueError("render time points must contain non-negative values")
    if adaptive_runtime and (target_intervals < 1 or min_interval_seconds <= 0 or max_interval_seconds < min_interval_seconds or max_duration_seconds <= 0):
        raise ValueError("adaptive runtime sampling settings are invalid")
    sampling_plan = {
        "target_intervals": target_intervals,
        "min_interval_seconds": min_interval_seconds,
        "max_interval_seconds": max_interval_seconds,
        "max_duration_seconds": max_duration_seconds,
        "include_zero": True,
        "duration_sources": ["particle_system", "animator", "animation", "playable_director"],
    } if adaptive_runtime else None
    run_root.mkdir(parents=True, exist_ok=True)
    material_dependencies = _material_dependencies_by_prefab(source_manifest)
    ignored_script_dependencies = _ignored_script_dependencies_by_prefab(source_manifest)
    material_index, selection_summary = _material_selection_index(training_example)
    candidate_root = run_root / "candidates"
    requests: list[dict[str, Any]] = []

    for ordinal, prefab_path in enumerate(selected_prefabs, start=1):
        candidate_id = _candidate_id(prefab_path, ordinal)
        candidate_dir = candidate_root / candidate_id
        materials = material_dependencies.get(prefab_path, [])
        training_case = training_case_by_prefab.get(prefab_path)
        runtime_observation = {}
        if isinstance(training_case, dict):
            runtime_observation = training_case.get("runtime_observation") or (training_case.get("observations") or {}).get("runtime_observation") or {}
        missing_script_count = int(runtime_observation.get("missing_script_count") or 0)
        spec = _candidate_spec(
            source_id=source_id,
            source_sample_id=source_sample_id,
            run_id=run_id,
            candidate_id=candidate_id,
            prefab_path=prefab_path,
            material_paths=materials,
            material_index=material_index,
            selection_summary=selection_summary,
            unity_project=unity_project,
            scene=scene,
            camera=camera,
            resolution=resolution,
            time_points=normalized_times,
            training_case=training_case,
            sampling_plan=sampling_plan,
        )
        timeline_path = (candidate_dir / "material_timeline.json").resolve()
        ignored_scripts = ignored_script_dependencies.get(prefab_path, [])
        script_fidelity = "source_scripts_missing" if missing_script_count > 0 else "source_scripts_excluded" if ignored_scripts else "no_ignored_script_dependencies"
        spec["render_plan"]["material_state_capture"] = {
            "required": adaptive_runtime,
            "timeline_path": timeline_path.as_posix(),
            "source_script_fidelity": script_fidelity,
            "ignored_script_dependency_count": len(ignored_scripts),
            "missing_script_count": missing_script_count,
            "ignored_script_paths": ignored_scripts,
        }
        _write_json(candidate_dir / "spec.json", spec)
        requests.append(
            {
                "candidate_id": candidate_id,
                "prefab_path": prefab_path,
                "capture_dir": (candidate_dir / "captures").resolve().as_posix(),
                "capture_manifest_path": (candidate_dir / "capture_manifest.json").resolve().as_posix(),
                "material_timeline_path": timeline_path.as_posix(),
                "source_script_fidelity": script_fidelity,
                "ignored_script_dependency_count": len(ignored_scripts),
                "missing_script_count": missing_script_count,
                "capture_category": "source_prefab",
            }
        )

    prompt_path = run_root / "prompt.md"
    prompt_path.write_text(
        "# Source Prefab Render Review\n\n"
        f"- Source sample: `{source_sample_id}`\n"
        f"- Source ID: `{source_id}`\n"
        f"- Candidate count: `{len(requests)}`\n"
        "- Review boundary: source dependencies prove structural closure only; render and human feedback determine training eligibility.\n",
        encoding="utf-8",
    )
    request_path = run_root / "render_requests.json"
    _write_json(
        request_path,
        {
            "schema_version": REQUEST_SCHEMA,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "unity_project": unity_project.resolve().as_posix(),
            "scene": scene,
            "camera": camera,
            "width": resolution[0],
            "height": resolution[1],
            "time_points_seconds": normalized_times,
            "sampling_mode": "adaptive_runtime" if adaptive_runtime else "fixed_editor_simulation",
            "sampling": sampling_plan,
            "capture_material_timeline": adaptive_runtime,
            "requests": requests,
        },
    )
    return {"run_root": run_root, "request_path": request_path, "prompt_path": prompt_path}


def finalize_render_run(
    request_path: Path,
    *,
    parent_beads_id: str | None,
    verify_errors: int | None = None,
    verify_warnings: int | None = None,
    console_error_count: int | None = None,
    console_warning_count: int | None = None,
    console_last_error: str | None = None,
) -> dict[str, Path]:
    """Build auto-eval, contact sheet, and feedback placeholders from Unity captures."""
    request_path = request_path.resolve()
    request = _read_json(request_path)
    if request.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError(f"unsupported render request schema: {request.get('schema_version')}")
    run_root = request_path.parent
    result = build_run_outputs(
        run_root,
        run_id=str(request["run_id"]),
        parent_beads_id=parent_beads_id,
        prompt_path=run_root / "prompt.md",
        generator_version="vfx_source_render.v1",
        unity_project=Path(str(request["unity_project"])),
        scene=str(request["scene"]),
        camera=str(request["camera"]),
        resolution=(int(request["width"]), int(request["height"])),
        render_time_points_seconds=[float(value) for value in _as_list(request.get("time_points_seconds"))],
        verify_errors=verify_errors,
        verify_warnings=verify_warnings,
        console_error_count=console_error_count,
        console_warning_count=console_warning_count,
        console_last_error=console_last_error,
        source_review_mode=True,
    )
    if request.get("sampling_mode") == "adaptive_runtime":
        manifest = _read_json(result["run_manifest"])
        manifest["capture_mode"] = "play_mode_runtime"
        manifest["sampling_mode"] = "adaptive_runtime"
        manifest["sampling_plan"] = request.get("sampling")
        _write_json(result["run_manifest"], manifest)
    else:
        manifest = _read_json(result["run_manifest"])
        manifest["capture_mode"] = "editor_particle_simulation"
        manifest["sampling_mode"] = "fixed_editor_simulation"
        _write_json(result["run_manifest"], manifest)
    return {"run_root": run_root, **result}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and finalize render-review runs for imported Unity VFX Prefabs.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="write candidate specs and a Unity render request")
    prepare.add_argument("--source-dir", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    prepare.add_argument("--unity-project", type=Path, required=True)
    prepare.add_argument("--prefab", action="append", default=[])
    prepare.add_argument("--review-batch", type=Path)
    prepare.add_argument("--run-id")
    prepare.add_argument("--adaptive-runtime", action="store_true")
    prepare.add_argument("--target-intervals", type=int, default=10)
    prepare.add_argument("--min-interval", type=float, default=0.02)
    prepare.add_argument("--max-interval", type=float, default=0.1)
    prepare.add_argument("--max-duration", type=float, default=8.0)
    prepare.add_argument("--time-points", type=float, nargs="+", default=list(DEFAULT_TIME_POINTS))
    prepare.add_argument("--width", type=int, default=DEFAULT_RESOLUTION[0])
    prepare.add_argument("--height", type=int, default=DEFAULT_RESOLUTION[1])
    prepare.add_argument("--scene", default=DEFAULT_SCENE)
    prepare.add_argument("--camera", default=DEFAULT_CAMERA)
    finalize = commands.add_parser("finalize", help="build run manifest, auto-eval, contact sheets, and feedback placeholder")
    finalize.add_argument("--requests", type=Path, required=True)
    finalize.add_argument("--parent-beads-id")
    finalize.add_argument("--verify-errors", type=int)
    finalize.add_argument("--verify-warnings", type=int)
    finalize.add_argument("--console-error-count", type=int)
    finalize.add_argument("--console-warning-count", type=int)
    finalize.add_argument("--console-last-error")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            review_records = []
            if args.review_batch is not None:
                review_payload = _read_json(args.review_batch)
                review_records = _as_list(review_payload.get("records"))
            paths = prepare_render_run(
                args.source_dir,
                args.run_root,
                unity_project=args.unity_project,
                prefab_paths=args.prefab or ([str(record["prefab_path"]) for record in review_records] if review_records else None),
                time_points=args.time_points,
                resolution=(args.width, args.height),
                scene=args.scene,
                camera=args.camera,
                run_id=args.run_id,
                training_cases=review_records,
                adaptive_runtime=args.adaptive_runtime,
                target_intervals=args.target_intervals,
                min_interval_seconds=args.min_interval,
                max_interval_seconds=args.max_interval,
                max_duration_seconds=args.max_duration,
            )
        else:
            paths = finalize_render_run(
                args.requests,
                parent_beads_id=args.parent_beads_id,
                verify_errors=args.verify_errors,
                verify_warnings=args.verify_warnings,
                console_error_count=args.console_error_count,
                console_warning_count=args.console_warning_count,
                console_last_error=args.console_last_error,
            )
    except (FileExistsError, OSError, ValueError) as exc:
        parser_error = {"success": False, "error": str(exc)}
        print(json.dumps(parser_error, ensure_ascii=False))
        return 2
    print(json.dumps({key: value.as_posix() for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
