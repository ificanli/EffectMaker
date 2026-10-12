"""Batch run manifest and contact-sheet helpers for VFX candidate comparison."""

from __future__ import annotations

import argparse
import json
import math
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageStat

from workspace.tools.vfx_generation.evaluator import score_candidate


DEFAULT_CANDIDATE_ROOT = "candidates"
DEFAULT_RENDER_MANIFEST_NAMES = ("render_manifest.json", "capture_manifest.json")
DEFAULT_AUTO_EVAL_FILENAME = "auto_eval.jsonl"
DEFAULT_FEEDBACK_FILENAME = "feedback.jsonl"
DEFAULT_CONTACT_SHEET_DIR = "contact_sheets"
DEFAULT_GENERATOR_VERSION = "vfx_generation.run_pipeline.v1"
STATUS_ORDER = {"pass": 0, "warn": 1, "reject": 2}
STATUS_COLORS = {
    "pass": "#214d37",
    "warn": "#7b5b18",
    "reject": "#6a2c2c",
    "unknown": "#303030",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def _path_text(path: Path | None, base: Path | None = None) -> str | None:
    if path is None:
        return None
    path = Path(path)
    if not path.is_absolute():
        return path.as_posix()
    if base is not None:
        try:
            return path.relative_to(base.resolve()).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _resolve_path(path_text: str | Path, base: Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else (base / path).resolve()


def _normalize_timepoints(values: Sequence[float] | None) -> list[float]:
    if values is None:
        return []
    return [round(float(value), 3) for value in values]


def _times_match(expected: Sequence[float], actual: Sequence[float], tolerance: float = 0.002) -> bool:
    if len(expected) != len(actual):
        return False
    return all(abs(float(left) - float(right)) <= tolerance for left, right in zip(expected, actual))


def _discover_candidate_dirs(run_root: Path, candidate_root_name: str = DEFAULT_CANDIDATE_ROOT) -> list[Path]:
    run_root = run_root.resolve()
    roots: list[Path] = []
    candidate_root = run_root / candidate_root_name
    if candidate_root.is_dir():
        roots.extend(sorted(path for path in candidate_root.iterdir() if path.is_dir() and (path / "spec.json").exists()))
    else:
        roots.extend(sorted(path for path in run_root.iterdir() if path.is_dir() and (path / "spec.json").exists()))
    if not roots:
        raise FileNotFoundError(f"no candidate spec.json files were found under {run_root}")
    return roots


def _pick_render_manifest(candidate_dir: Path, names: Sequence[str] = DEFAULT_RENDER_MANIFEST_NAMES) -> Path | None:
    for name in names:
        path = candidate_dir / name
        if path.exists():
            return path
    return None


def _frame_image_stats(image: Image.Image, *, background_relative: bool = False) -> dict[str, float]:
    rgb = image.convert("RGB")
    gray = rgb.convert("L")
    histogram = gray.histogram()
    total = float(sum(histogram) or 1)
    if background_relative:
        corners = [
            rgb.getpixel((0, 0)),
            rgb.getpixel((rgb.width - 1, 0)),
            rgb.getpixel((0, rgb.height - 1)),
            rgb.getpixel((rgb.width - 1, rgb.height - 1)),
        ]
        background = tuple(round(sum(pixel[channel] for pixel in corners) / len(corners)) for channel in range(3))
        difference = ImageChops.difference(rgb, Image.new("RGB", rgb.size, background)).convert("L")
        difference_histogram = difference.histogram()
        visible = float(sum(difference_histogram[6:]))
        difference.close()
    else:
        visible = float(sum(histogram[16:]))
    over = float(sum(histogram[245:]))
    under = float(sum(histogram[:8]))
    mean_luminance = sum(index * count for index, count in enumerate(histogram)) / (255.0 * total)
    return {
        "visible_area_ratio": visible / total,
        "mean_luminance": mean_luminance,
        "overexposed_ratio": over / total,
        "underexposed_ratio": under / total,
    }


def _downsample_gray(image: Image.Image, size: tuple[int, int] = (64, 36)) -> Image.Image:
    gray = image.convert("L")
    return gray.resize(size, Image.Resampling.BILINEAR)


def _load_preview_image(frame_path: Path, size: tuple[int, int]) -> Image.Image | None:
    try:
        with Image.open(frame_path) as image:
            preview = ImageOps.contain(image.convert("RGB"), size, Image.Resampling.LANCZOS)
            return preview.copy()
    except (FileNotFoundError, OSError, ValueError):
        return None


def _placeholder_tile(size: tuple[int, int], title: str, body: str, fill: str) -> Image.Image:
    tile = Image.new("RGB", size, fill)
    draw = ImageDraw.Draw(tile)
    font = ImageFont.load_default()
    draw.multiline_text((10, 8), title, fill="white", font=font, spacing=2)
    draw.multiline_text((10, 36), body, fill="#f0f0f0", font=font, spacing=2)
    return tile


def _render_tile(
    candidate_id: str,
    frame: dict,
    capture_root: Path,
    tile_size: tuple[int, int],
    status_color: str,
) -> Image.Image:
    tile = Image.new("RGB", tile_size, "#1b1b1b")
    draw = ImageDraw.Draw(tile)
    font = ImageFont.load_default()
    time_value = frame.get("requested_time_seconds")
    time_label = f"{float(time_value):0.3f}s" if time_value is not None else "time ?"
    draw.rectangle([0, 0, tile_size[0] - 1, tile_size[1] - 1], outline=status_color, width=2)
    draw.text((8, 6), time_label, fill="white", font=font)
    path_text = frame.get("path")
    frame_path = _resolve_path(path_text, capture_root) if path_text is not None else capture_root
    preview = _load_preview_image(frame_path, (tile_size[0] - 18, tile_size[1] - 36))
    if preview is None:
        body = "missing" if not frame.get("valid") else "unreadable"
        placeholder = _placeholder_tile((tile_size[0] - 18, tile_size[1] - 36), candidate_id, body, "#441b1b")
        tile.paste(placeholder, (9, 28))
    else:
        x = 9 + max(0, (tile_size[0] - 18 - preview.width) // 2)
        y = 28 + max(0, (tile_size[1] - 36 - preview.height) // 2)
        tile.paste(preview, (x, y))
        preview.close()
    return tile


def _candidate_sort_key(candidate: dict) -> tuple[int, float, str]:
    auto_eval = candidate.get("auto_eval", {})
    status_rank = STATUS_ORDER.get(str(auto_eval.get("status", "unknown")), 99)
    rank_hint = auto_eval.get("rank_hint")
    rank_value = float(rank_hint) if isinstance(rank_hint, (int, float)) else 0.0
    return (status_rank, -rank_value, str(candidate.get("candidate_id", "")))


def _candidate_metrics(images: list[Image.Image], *, source_review_mode: bool = False) -> tuple[float, float, float, float, float]:
    if not images:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    metrics = [_frame_image_stats(image, background_relative=source_review_mode) for image in images]
    visible_peak = max(item["visible_area_ratio"] for item in metrics)
    mean_luminance_peak = max(item["mean_luminance"] for item in metrics)
    overexposed_peak = max(item["overexposed_ratio"] for item in metrics)
    underexposed_peak = max(item["underexposed_ratio"] for item in metrics)
    if len(images) > 1:
        deltas: list[float] = []
        previous = _downsample_gray(images[0])
        for image in images[1:]:
            current = _downsample_gray(image)
            diff = ImageChops.difference(previous, current)
            deltas.append(ImageStat.Stat(diff).mean[0] / 255.0)
            previous.close()
            previous = current
        previous.close()
        frame_delta_mean = sum(deltas) / len(deltas)
    else:
        frame_delta_mean = 0.0
    return (
        visible_peak,
        mean_luminance_peak,
        overexposed_peak,
        underexposed_peak,
        frame_delta_mean,
    )


def _evaluate_candidate(
    *,
    run_id: str,
    candidate_id: str,
    seed: int | None,
    frames: list[dict],
    capture_root: Path,
    expected_time_points: Sequence[float],
    expected_scene: str | None,
    expected_camera: str | None,
    expected_resolution: Sequence[int] | None,
    actual_scene: str | None,
    actual_camera: str | None,
    actual_resolution: Sequence[int] | None,
    verify_errors: int | None,
    verify_warnings: int | None,
    console_error_count: int | None,
    console_warning_count: int | None,
    console_last_error: str | None,
    source_review_mode: bool = False,
) -> dict:
    hard_reject_reasons: list[str] = []
    warning_reasons: list[str] = []
    loaded_images: list[Image.Image] = []
    visible_peak = 0.0
    mean_luminance_peak = 0.0
    overexposed_peak = 0.0
    underexposed_peak = 0.0
    frame_delta_mean = 0.0

    if not frames:
        hard_reject_reasons.append("missing_render_manifest")
    else:
        if expected_time_points:
            actual_time_points = [round(float(frame.get("requested_time_seconds", 0.0)), 3) for frame in frames]
            if not _times_match(expected_time_points, actual_time_points):
                hard_reject_reasons.append("timepoint_mismatch")
        for frame in frames:
            path_text = frame.get("path")
            if path_text is None:
                hard_reject_reasons.append("missing_frame")
                continue
            frame_path = _resolve_path(path_text, capture_root)
            exists = frame_path.exists() and frame_path.is_file() and frame_path.stat().st_size > 0
            if not exists:
                hard_reject_reasons.append("missing_frame")
                continue
            try:
                with Image.open(frame_path) as image:
                    loaded = image.convert("RGB")
                    loaded_images.append(loaded.copy())
                    loaded.close()
            except (OSError, ValueError):
                hard_reject_reasons.append("corrupt_frame")

    if expected_scene is not None and actual_scene != expected_scene:
        hard_reject_reasons.append("scene_mismatch")
    if expected_camera is not None and actual_camera != expected_camera:
        hard_reject_reasons.append("camera_mismatch")
    if expected_resolution is not None:
        actual_resolution_tuple = tuple(int(value) for value in actual_resolution) if actual_resolution is not None else None
        if actual_resolution_tuple is None or tuple(int(value) for value in expected_resolution) != actual_resolution_tuple:
            hard_reject_reasons.append("resolution_mismatch")

    if verify_errors is not None and verify_errors > 0:
        hard_reject_reasons.append("unity_error")
    elif verify_warnings is not None and verify_warnings > 0:
        warning_reasons.append("unity_warning")

    if console_error_count is not None and console_error_count > 0:
        hard_reject_reasons.append("console_error")
    elif console_warning_count is not None and console_warning_count > 0:
        warning_reasons.append("console_warning")
    if console_last_error:
        warning_reasons.append("console_last_error_recorded")

    if loaded_images:
        (
            visible_peak,
            mean_luminance_peak,
            overexposed_peak,
            underexposed_peak,
            frame_delta_mean,
        ) = _candidate_metrics(loaded_images, source_review_mode=source_review_mode)

    invisible_threshold = 0.0005 if source_review_mode else 0.01
    borderline_threshold = 0.002 if source_review_mode else 0.03
    if visible_peak < invisible_threshold:
        hard_reject_reasons.append("invisible")
    elif visible_peak < borderline_threshold:
        warning_reasons.append("borderline_visibility")

    if not source_review_mode and mean_luminance_peak < 0.02 and visible_peak < 0.02:
        hard_reject_reasons.append("too_dark")
    elif not source_review_mode and mean_luminance_peak < 0.08:
        warning_reasons.append("dark")

    if overexposed_peak > 0.98:
        hard_reject_reasons.append("overexposed")
    elif overexposed_peak > 0.9:
        warning_reasons.append("bright")

    if not source_review_mode and underexposed_peak > 0.98:
        hard_reject_reasons.append("underexposed")
    elif not source_review_mode and underexposed_peak > 0.9:
        warning_reasons.append("shadow_heavy")

    if len(loaded_images) > 1 and frame_delta_mean < 0.001:
        if source_review_mode:
            warning_reasons.append("static_frames")
        else:
            hard_reject_reasons.append("static_frames")
    elif len(loaded_images) > 1 and frame_delta_mean < 0.004:
        warning_reasons.append("low_motion")

    status = "pass"
    if hard_reject_reasons:
        status = "reject"
    elif warning_reasons:
        status = "warn"

    rank_hint = round(
        max(
            0.0,
            min(
                100.0,
                visible_peak * 70.0
                + min(frame_delta_mean, 0.05) / 0.05 * 20.0
                + max(0.0, 1.0 - abs(mean_luminance_peak - 0.35) / 0.35) * 10.0,
            ),
        ),
        2,
    )

    for image in loaded_images:
        image.close()

    metrics = {
        "unity_error_count": int(verify_errors or 0) + int(console_error_count or 0),
        "missing_asset_count": 0,
        "missing_frame_count": sum(1 for frame in frames if not frame.get("valid")),
        "visible_area_ratio_peak": round(visible_peak, 6),
        "mean_luminance_peak": round(mean_luminance_peak, 6),
        "overexposed_ratio_peak": round(overexposed_peak, 6),
        "underexposed_ratio_peak": round(underexposed_peak, 6),
        "frame_delta_mean": round(frame_delta_mean, 6),
        "particle_count_peak": None,
        "draw_call_count": None,
    }

    notes = []
    if warning_reasons:
        notes.extend(warning_reasons)
    if console_last_error:
        notes.append(console_last_error)

    return {
        "schema_version": "auto_eval.v1",
        "run_id": run_id,
        "candidate_id": candidate_id,
        "seed": int(seed or 0),
        "status": status,
        "hard_reject_reasons": sorted(set(hard_reject_reasons)),
        "rank_hint": rank_hint,
        "metrics": metrics,
        "notes": "; ".join(notes) if notes else None,
    }


def collect_candidate_records(
    run_root: Path,
    *,
    run_id: str | None = None,
    candidate_root_name: str = DEFAULT_CANDIDATE_ROOT,
    render_manifest_names: Sequence[str] = DEFAULT_RENDER_MANIFEST_NAMES,
    expected_time_points_seconds: Sequence[float] | None = None,
    expected_scene: str | None = None,
    expected_camera: str | None = None,
    expected_resolution: Sequence[int] | None = None,
    verify_errors: int | None = None,
    verify_warnings: int | None = None,
    console_error_count: int | None = None,
    console_warning_count: int | None = None,
    console_last_error: str | None = None,
    source_review_mode: bool = False,
) -> tuple[list[dict], list[dict]]:
    run_root = run_root.resolve()
    run_id = run_id or run_root.name
    candidate_dirs = _discover_candidate_dirs(run_root, candidate_root_name=candidate_root_name)
    expected_time_points = _normalize_timepoints(expected_time_points_seconds)
    records: list[dict] = []
    auto_eval_records: list[dict] = []

    for discovery_index, candidate_dir in enumerate(candidate_dirs, start=1):
        spec_path = candidate_dir / "spec.json"
        spec = _load_json(spec_path)
        generation = spec.get("generation", {})
        candidate_id = generation.get("candidate_id") or candidate_dir.name
        seed = generation.get("seed")
        render_plan = spec.get("render_plan", {})
        render_manifest_path = _pick_render_manifest(candidate_dir, render_manifest_names)
        render_manifest = _load_json(render_manifest_path) if render_manifest_path else None
        capture_root = candidate_dir
        if render_manifest is not None:
            capture_root_text = render_manifest.get("capture_root") or render_manifest.get("root")
            if capture_root_text is not None:
                capture_root = _resolve_path(capture_root_text, render_manifest_path.parent)
        material_timeline_path = None
        material_timeline = None
        material_timeline_status = "not_linked"
        if render_manifest is not None and render_manifest.get("material_timeline_path"):
            material_timeline_path = _resolve_path(render_manifest["material_timeline_path"], render_manifest_path.parent)
            if material_timeline_path.is_file():
                try:
                    material_timeline = _load_json(material_timeline_path)
                    material_timeline_status = "ready" if material_timeline.get("schema_version") == "vfx_material_timeline.v1" else "invalid"
                except (OSError, json.JSONDecodeError):
                    material_timeline_status = "invalid"
            else:
                material_timeline_status = "missing"
        material_summary = material_timeline.get("summary", {}) if isinstance(material_timeline, dict) else {}

        frames: list[dict] = []
        raw_frames = list(render_manifest.get("frames", [])) if render_manifest else []
        for frame in raw_frames:
            path_text = frame.get("path")
            frame_record = {
                "requested_time_seconds": frame.get("requested_time_seconds"),
                "capture_time_seconds": frame.get("capture_time_seconds"),
                "simulation_elapsed_seconds": frame.get("simulation_elapsed_seconds"),
                "wall_clock_elapsed_seconds": frame.get("wall_clock_elapsed_seconds"),
                "unity_frame_count": frame.get("unity_frame_count"),
                "unity_time_seconds": frame.get("unity_time_seconds"),
                "unity_unscaled_time_seconds": frame.get("unity_unscaled_time_seconds"),
                "path": str(path_text).replace("\\", "/") if path_text is not None else None,
                "valid": bool(frame.get("valid", False)),
                "error": frame.get("error"),
                "material_timeline_frame_index": frame.get("material_timeline_frame_index"),
                "camera_view": frame.get("camera_view"),
                "pixel_metrics": frame.get("pixel_metrics"),
            }
            if frame_record["path"] is not None:
                frame_path = _resolve_path(frame_record["path"], capture_root)
                exists = frame_path.exists() and frame_path.is_file() and frame_path.stat().st_size > 0
                if not exists:
                    frame_record["valid"] = False
                    frame_record["error"] = frame_record["error"] or "missing capture file"
                elif not frame_record["valid"]:
                    frame_record["error"] = frame_record["error"] or "invalid capture file"
                else:
                    frame_record["file_size"] = frame_path.stat().st_size
            frames.append(frame_record)

        expected_resolution_tuple = tuple(int(value) for value in expected_resolution) if expected_resolution is not None else None
        render_resolution = render_manifest.get("resolution") if render_manifest else None
        render_scene = render_manifest.get("scene") if render_manifest else None
        render_camera = render_manifest.get("camera") if render_manifest else None

        record = {
            "discovery_index": discovery_index,
            "candidate_id": candidate_id,
            "seed": seed,
            "spec_path": _path_text(spec_path, run_root),
            "render_manifest_path": _path_text(render_manifest_path, run_root),
            "material_timeline_path": _path_text(material_timeline_path, run_root),
            "material_timeline_status": material_timeline_status,
            "material_state_summary": {
                "frame_count": material_summary.get("frame_count", 0),
                "delta_count": material_summary.get("delta_count", 0),
                "changed_frame_count": material_summary.get("changed_frame_count", 0),
                "has_dynamic_material_state": bool(material_summary.get("has_dynamic_material_state", False)),
                "key_material_change_times": material_summary.get("key_material_change_times", []),
                "source_script_fidelity": material_timeline.get("source_script_fidelity") if isinstance(material_timeline, dict) else None,
                "ignored_script_dependency_count": material_timeline.get("ignored_script_dependency_count", 0) if isinstance(material_timeline, dict) else 0,
                "has_unenumerated_property_block_values": bool(material_summary.get("has_unenumerated_property_block_values", False)),
                "global_shader_state_status": material_summary.get("global_shader_state_status"),
            },
            "capture_root": _path_text(capture_root, run_root),
            "spec_summary": {
                "effect_family": spec.get("effect_family"),
                "effect_type": spec.get("effect_type"),
                "generator": generation.get("generator"),
                "generator_version": generation.get("generator_version"),
                "parent_candidate_id": generation.get("parent_candidate_id"),
            },
            "render_plan": {
                "unity_project": render_plan.get("unity_project"),
                "scene": render_plan.get("scene"),
                "camera": render_plan.get("camera"),
                "resolution": render_plan.get("resolution"),
                "time_points_seconds": render_plan.get("time_points_seconds", []),
            },
            "render_context": {
                "scene": render_scene,
                "camera": render_camera,
                "resolution": render_resolution,
                "editor_status": render_manifest.get("editor_status") if render_manifest else None,
                "play_requested": render_manifest.get("play_requested") if render_manifest else None,
                "capture_pipeline_version": render_manifest.get("capture_pipeline_version") if render_manifest else None,
                "selected_camera_view": (render_manifest.get("camera_selection") or {}).get("selected_view") if render_manifest else None,
            },
            "capture_evidence": {
                "pipeline_version": render_manifest.get("capture_pipeline_version") if render_manifest else None,
                "instance_isolation_mode": render_manifest.get("instance_isolation_mode") if render_manifest else None,
                "distinct_instance_ids": render_manifest.get("distinct_instance_ids") if render_manifest else None,
                "camera_selection": render_manifest.get("camera_selection") if render_manifest else None,
                "context": render_manifest.get("context") if render_manifest else None,
                "technical_frame_eligible": render_manifest.get("technical_frame_eligible") if render_manifest else None,
                "image_sequence_training_eligible": render_manifest.get("image_sequence_training_eligible") if render_manifest else None,
                "full_visual_training_eligible": render_manifest.get("full_visual_training_eligible") if render_manifest else None,
                "visual_evidence_status": render_manifest.get("visual_evidence_status") if render_manifest else None,
                "visual_evidence_limitations": render_manifest.get("visual_evidence_limitations", []) if render_manifest else [],
            },
            "frames": frames,
            "frame_count": len(frames),
            "valid_frame_count": sum(1 for frame in frames if frame.get("valid")),
            "missing_frame_count": sum(1 for frame in frames if not frame.get("valid")),
            "render_status": "missing_manifest"
            if render_manifest is None
            else "blocked"
            if not frames
            else "ready"
            if all(frame.get("valid") for frame in frames)
            else "partial"
            if any(frame.get("valid") for frame in frames)
            else "blocked",
        }
        auto_eval = _evaluate_candidate(
            run_id=run_id,
            candidate_id=candidate_id,
            seed=seed,
            frames=frames,
            capture_root=capture_root,
            expected_time_points=expected_time_points,
            expected_scene=expected_scene,
            expected_camera=expected_camera,
            expected_resolution=expected_resolution_tuple,
            actual_scene=render_scene,
            actual_camera=render_camera,
            actual_resolution=render_resolution,
            verify_errors=verify_errors,
            verify_warnings=verify_warnings,
            console_error_count=console_error_count,
            console_warning_count=console_warning_count,
            console_last_error=console_last_error,
            source_review_mode=source_review_mode,
        )
        if render_manifest and render_manifest.get("capture_pipeline_version") == "play_mode_runtime_isolated_multiview.v2":
            capture_gate_reasons = []
            if render_manifest.get("technical_frame_eligible") is not True:
                capture_gate_reasons.append("capture_technical_frame_ineligible")
            if render_manifest.get("image_sequence_training_eligible") is not True:
                capture_gate_reasons.append("capture_image_sequence_ineligible")
            if render_manifest.get("distinct_instance_ids") is not True:
                capture_gate_reasons.append("capture_instance_isolation_failed")
            context_status = (render_manifest.get("context") or {}).get("status")
            if context_status != "standard_context_ready":
                capture_gate_reasons.append("capture_context_incomplete")
            if capture_gate_reasons:
                auto_eval["hard_reject_reasons"] = sorted(set(auto_eval["hard_reject_reasons"] + capture_gate_reasons))
                auto_eval["status"] = "reject"
                auto_eval["rank_hint"] = 0.0
            if render_manifest.get("full_visual_training_eligible") is not True:
                note = "full_visual_training_ineligible"
                auto_eval["notes"] = "; ".join(value for value in (auto_eval.get("notes"), note) if value)
        candidate_score = score_candidate(
            spec,
            render_metrics=auto_eval["metrics"],
            rendered=any(frame.get("valid") for frame in frames),
            render_context={
                "scene_match": None if expected_scene is None else render_scene == expected_scene,
                "camera_match": None if expected_camera is None else render_camera == expected_camera,
                "resolution_match": None
                if expected_resolution_tuple is None
                else render_resolution is not None
                and tuple(int(value) for value in render_resolution) == expected_resolution_tuple,
            },
        )
        auto_eval["candidate_score"] = candidate_score
        record["auto_eval"] = {
            "status": auto_eval["status"],
            "rank_hint": auto_eval["rank_hint"],
            "hard_reject_reasons": auto_eval["hard_reject_reasons"],
            "metrics": auto_eval["metrics"],
            "candidate_score": candidate_score,
            "notes": auto_eval["notes"],
        }
        records.append(record)
        auto_eval_records.append(auto_eval)

    records.sort(key=_candidate_sort_key)
    auto_eval_records.sort(key=lambda item: _candidate_sort_key({"candidate_id": item["candidate_id"], "auto_eval": item}))
    return records, auto_eval_records


def _candidate_row_label(candidate: dict) -> str:
    auto_eval = candidate.get("auto_eval", {})
    lines = [
        candidate.get("candidate_id", ""),
        f"seed={candidate.get('seed')}",
        f"status={auto_eval.get('status', 'unknown')}  rank={auto_eval.get('rank_hint', 0):0.2f}",
        f"frames={candidate.get('valid_frame_count', 0)}/{candidate.get('frame_count', 0)}",
    ]
    reasons = auto_eval.get("hard_reject_reasons") or []
    if reasons:
        lines.append("reject=" + ", ".join(reasons[:2]))
    return "\n".join(line for line in lines if line)


def _candidate_row_fill(status: str) -> str:
    return STATUS_COLORS.get(status, STATUS_COLORS["unknown"])


def build_contact_sheet_pages(
    run_root: Path,
    candidates: list[dict],
    time_points_seconds: Sequence[float],
    output_dir: Path | None = None,
    *,
    page_size: int = 8,
    run_id: str | None = None,
    prompt_path: Path | None = None,
    unity_project: Path | None = None,
    scene: str | None = None,
    camera: str | None = None,
    resolution: Sequence[int] | None = None,
) -> list[dict]:
    run_root = run_root.resolve()
    run_id = run_id or run_root.name
    output_dir = (output_dir or (run_root / DEFAULT_CONTACT_SHEET_DIR)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    if not candidates:
        return []

    time_points = _normalize_timepoints(time_points_seconds)
    adaptive_frames = not time_points
    columns = min(6, max((len(candidate.get("frames", [])) for candidate in candidates), default=1)) if adaptive_frames else max(1, len(time_points))
    page_count = math.ceil(len(candidates) / page_size)
    pages: list[dict] = []
    page_margin = 16
    header_height = 82
    row_label_width = 240
    tile_width = 230
    tile_height = 178
    row_height = tile_height + 10

    font = ImageFont.load_default()
    status_font = ImageFont.load_default()

    for page_index, start in enumerate(range(0, len(candidates), page_size), start=1):
        page_candidates = candidates[start:start + page_size]
        width = page_margin * 2 + row_label_width + columns * tile_width
        height = page_margin * 2 + header_height + len(page_candidates) * row_height
        sheet = Image.new("RGB", (width, height), "#101010")
        draw = ImageDraw.Draw(sheet)
        title = f"Run {run_id}  page {page_index}/{page_count}  candidates {start + 1}-{start + len(page_candidates)} of {len(candidates)}"
        details = [
            f"prompt: {_path_text(prompt_path, run_root) if prompt_path else 'n/a'}",
            f"scene: {scene or 'n/a'}  camera: {camera or 'n/a'}  resolution: {resolution[0]}x{resolution[1] if resolution else 'n/a'}" if resolution else f"scene: {scene or 'n/a'}  camera: {camera or 'n/a'}",
            "timepoints: " + ", ".join(f"{time:0.2f}s" for time in time_points) if time_points else "timepoints: adaptive per candidate; contact sheet shows evenly sampled keyframes",
        ]
        draw.multiline_text((page_margin, page_margin), "\n".join([title, *details]), fill="white", font=font, spacing=3)
        counts = Counter(candidate.get("auto_eval", {}).get("status", "unknown") for candidate in candidates)
        legend = f"pass={counts.get('pass', 0)}  warn={counts.get('warn', 0)}  reject={counts.get('reject', 0)}"
        draw.text((page_margin, page_margin + 54), legend, fill="#cfcfcf", font=status_font)

        for row_offset, candidate in enumerate(page_candidates):
            row_top = page_margin + header_height + row_offset * row_height
            status = candidate.get("auto_eval", {}).get("status", "unknown")
            fill = _candidate_row_fill(status)
            draw.rectangle(
                [page_margin, row_top, page_margin + row_label_width - 8, row_top + tile_height],
                fill=fill,
                outline=fill,
            )
            draw.multiline_text(
                (page_margin + 10, row_top + 10),
                textwrap.fill(_candidate_row_label(candidate), width=26),
                fill="white",
                font=font,
                spacing=3,
            )
            capture_root = _resolve_path(candidate["capture_root"], run_root)
            frames = candidate.get("frames", [])
            if adaptive_frames and len(frames) > columns and columns > 1:
                indices = [round(index * (len(frames) - 1) / (columns - 1)) for index in range(columns)]
                display_frames = [frames[index] for index in indices]
            else:
                display_frames = frames
            for column_index in range(columns):
                cell_left = page_margin + row_label_width + column_index * tile_width
                cell_box = [cell_left, row_top, cell_left + tile_width - 8, row_top + tile_height]
                draw.rectangle(cell_box, outline=fill, width=2)
                if column_index < len(display_frames):
                    tile = _render_tile(candidate["candidate_id"], display_frames[column_index], capture_root, (tile_width - 8, tile_height), fill)
                    sheet.paste(tile, (cell_left, row_top))
                    tile.close()
                else:
                    placeholder = _placeholder_tile((tile_width - 8, tile_height), "no frame", "timepoint missing", "#222222")
                    sheet.paste(placeholder, (cell_left, row_top))
                    placeholder.close()

            candidate["contact_sheet_page"] = page_index
            candidate["contact_sheet_row"] = row_offset + 1

        page_path = output_dir / f"page-{page_index:03d}.jpg"
        sheet.save(page_path, format="JPEG", quality=92)
        sheet.close()
        pages.append(
            {
                "page": page_index,
                "path": _path_text(page_path, run_root),
                "candidate_ids": [candidate["candidate_id"] for candidate in page_candidates],
                "candidate_count": len(page_candidates),
            }
        )

    return pages


def build_run_manifest(
    run_root: Path,
    *,
    run_id: str,
    parent_beads_id: str | None,
    prompt_path: Path,
    generator_version: str,
    unity_project: Path,
    scene: str,
    camera: str,
    resolution: Sequence[int],
    render_time_points_seconds: Sequence[float],
    candidates: list[dict],
    contact_sheet_paths: Sequence[str],
    auto_eval_path: Path,
    feedback_path: Path,
    candidate_root_path: str = DEFAULT_CANDIDATE_ROOT,
    verify_errors: int | None = None,
    verify_warnings: int | None = None,
    console_error_count: int | None = None,
    console_warning_count: int | None = None,
    console_last_error: str | None = None,
) -> dict:
    run_root = run_root.resolve()
    candidate_status_counts = Counter(candidate.get("auto_eval", {}).get("status", "unknown") for candidate in candidates)
    frame_summary = {
        "valid_frame_count": sum(candidate.get("valid_frame_count", 0) for candidate in candidates),
        "missing_frame_count": sum(candidate.get("missing_frame_count", 0) for candidate in candidates),
    }
    material_state_summary = {
        "ready_timeline_count": sum(candidate.get("material_timeline_status") == "ready" for candidate in candidates),
        "dynamic_candidate_count": sum(bool(candidate.get("material_state_summary", {}).get("has_dynamic_material_state")) for candidate in candidates),
        "delta_count": sum(int(candidate.get("material_state_summary", {}).get("delta_count", 0) or 0) for candidate in candidates),
    }
    capture_evidence_summary = {
        "pipeline_v2_count": sum(candidate.get("capture_evidence", {}).get("pipeline_version") == "play_mode_runtime_isolated_multiview.v2" for candidate in candidates),
        "isolated_instance_count": sum(candidate.get("capture_evidence", {}).get("distinct_instance_ids") is True for candidate in candidates),
        "image_sequence_training_eligible_count": sum(candidate.get("capture_evidence", {}).get("image_sequence_training_eligible") is True for candidate in candidates),
        "full_visual_training_eligible_count": sum(candidate.get("capture_evidence", {}).get("full_visual_training_eligible") is True for candidate in candidates),
        "incomplete_context_count": sum((candidate.get("capture_evidence", {}).get("context") or {}).get("status") == "incomplete_context" for candidate in candidates),
    }

    if verify_errors is None and verify_warnings is None:
        verify = {"errors": None, "warnings": None, "status": "unknown"}
    else:
        verify = {
            "errors": verify_errors,
            "warnings": verify_warnings,
            "status": "failed" if (verify_errors or 0) > 0 else "warning" if (verify_warnings or 0) > 0 else "passed",
        }
    if console_error_count is None and console_warning_count is None and console_last_error is None:
        console = {"error_count": None, "warning_count": None, "last_error": None, "status": "unknown"}
    else:
        console = {
            "error_count": console_error_count,
            "warning_count": console_warning_count,
            "last_error": console_last_error,
            "status": "failed" if (console_error_count or 0) > 0 else "warning" if (console_warning_count or 0) > 0 else "clean",
        }

    return {
        "schema_version": "vfx_run_manifest.v1",
        "run_id": run_id,
        "parent_beads_id": parent_beads_id,
        "prompt_path": _path_text(prompt_path, run_root),
        "generator_version": generator_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_root_path": candidate_root_path,
        "candidate_count": len(candidates),
        "candidate_status_counts": dict(candidate_status_counts),
        "frame_summary": frame_summary,
        "material_state_summary": material_state_summary,
        "capture_evidence_summary": capture_evidence_summary,
        "render_time_points_seconds": [round(float(value), 3) for value in render_time_points_seconds],
        "unity_project": _path_text(unity_project, run_root),
        "scene": scene,
        "camera": camera,
        "resolution": [int(resolution[0]), int(resolution[1])],
        "verify": verify,
        "console": console,
        "auto_eval_path": _path_text(auto_eval_path, run_root),
        "feedback_path": _path_text(feedback_path, run_root),
        "contact_sheet_paths": list(contact_sheet_paths),
        "candidates": candidates,
    }


def build_run_outputs(
    run_root: Path,
    *,
    run_id: str | None = None,
    parent_beads_id: str | None = None,
    prompt_path: Path,
    generator_version: str = DEFAULT_GENERATOR_VERSION,
    unity_project: Path,
    scene: str,
    camera: str = "Main Camera",
    resolution: tuple[int, int] = (1280, 720),
    render_time_points_seconds: Sequence[float],
    candidate_root_name: str = DEFAULT_CANDIDATE_ROOT,
    page_size: int = 8,
    render_manifest_names: Sequence[str] = DEFAULT_RENDER_MANIFEST_NAMES,
    verify_errors: int | None = None,
    verify_warnings: int | None = None,
    console_error_count: int | None = None,
    console_warning_count: int | None = None,
    console_last_error: str | None = None,
    source_review_mode: bool = False,
) -> dict[str, Path]:
    run_root = run_root.resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id or run_root.name

    candidates, auto_eval_records = collect_candidate_records(
        run_root,
        run_id=run_id,
        candidate_root_name=candidate_root_name,
        render_manifest_names=render_manifest_names,
        expected_time_points_seconds=render_time_points_seconds,
        expected_scene=scene,
        expected_camera=camera,
        expected_resolution=resolution,
        verify_errors=verify_errors,
        verify_warnings=verify_warnings,
        console_error_count=console_error_count,
        console_warning_count=console_warning_count,
        console_last_error=console_last_error,
        source_review_mode=source_review_mode,
    )

    contact_sheet_dir = run_root / DEFAULT_CONTACT_SHEET_DIR
    pages = build_contact_sheet_pages(
        run_root,
        candidates,
        render_time_points_seconds,
        contact_sheet_dir,
        page_size=page_size,
        run_id=run_id,
        prompt_path=prompt_path,
        unity_project=unity_project,
        scene=scene,
        camera=camera,
        resolution=resolution,
    )
    contact_sheet_paths = [page["path"] for page in pages]

    auto_eval_path = run_root / DEFAULT_AUTO_EVAL_FILENAME
    feedback_path = run_root / DEFAULT_FEEDBACK_FILENAME
    if not feedback_path.exists():
        feedback_path.write_text("", encoding="utf-8")

    manifest = build_run_manifest(
        run_root,
        run_id=run_id,
        parent_beads_id=parent_beads_id,
        prompt_path=prompt_path,
        generator_version=generator_version,
        unity_project=unity_project,
        scene=scene,
        camera=camera,
        resolution=resolution,
        render_time_points_seconds=render_time_points_seconds,
        candidates=candidates,
        contact_sheet_paths=contact_sheet_paths,
        auto_eval_path=auto_eval_path,
        feedback_path=feedback_path,
        candidate_root_path=candidate_root_name,
        verify_errors=verify_errors,
        verify_warnings=verify_warnings,
        console_error_count=console_error_count,
        console_warning_count=console_warning_count,
        console_last_error=console_last_error,
    )
    manifest["evaluation_profile"] = "source_vfx_review" if source_review_mode else "generated_candidate"
    _write_json(run_root / "run_manifest.json", manifest)
    _write_jsonl(auto_eval_path, auto_eval_records)

    return {
        "run_manifest": run_root / "run_manifest.json",
        "auto_eval": auto_eval_path,
        "feedback": feedback_path,
        "contact_sheet_dir": contact_sheet_dir,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a VFX run manifest, auto-eval records, and contact sheets.")
    parser.add_argument("--run-root", type=Path, required=True, help="Run directory that contains candidate specs and capture manifests.")
    parser.add_argument("--run-id")
    parser.add_argument("--parent-beads-id")
    parser.add_argument("--prompt-path", type=Path, required=True)
    parser.add_argument("--generator-version", default=DEFAULT_GENERATOR_VERSION)
    parser.add_argument("--unity-project", type=Path, required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--camera", default="Main Camera")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--time-points", type=float, nargs="+", required=True)
    parser.add_argument("--candidate-root", default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--page-size", type=int, default=8)
    parser.add_argument("--verify-errors", type=int)
    parser.add_argument("--verify-warnings", type=int)
    parser.add_argument("--console-error-count", type=int)
    parser.add_argument("--console-warning-count", type=int)
    parser.add_argument("--console-last-error")
    parser.add_argument("--source-review-mode", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = build_run_outputs(
        args.run_root,
        run_id=args.run_id,
        parent_beads_id=args.parent_beads_id,
        prompt_path=args.prompt_path,
        generator_version=args.generator_version,
        unity_project=args.unity_project,
        scene=args.scene,
        camera=args.camera,
        resolution=(args.width, args.height),
        render_time_points_seconds=args.time_points,
        candidate_root_name=args.candidate_root,
        page_size=args.page_size,
        verify_errors=args.verify_errors,
        verify_warnings=args.verify_warnings,
        console_error_count=args.console_error_count,
        console_warning_count=args.console_warning_count,
        console_last_error=args.console_last_error,
        source_review_mode=args.source_review_mode,
    )
    print(json.dumps({key: value.as_posix() if isinstance(value, Path) else value for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
