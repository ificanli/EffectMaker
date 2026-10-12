"""Build Aesthetic Judge inputs from active-learning Capture v2 records."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workspace.tools.vfx_training_features import aggregate_image_features


CAPTURE_PIPELINE = "play_mode_runtime_isolated_multiview.v2"
FEATURE_SCHEMA = "vfx_prefab_review_judge_features.v1"


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _capture_frames(manifest_path: Path, manifest: dict[str, Any]) -> tuple[list[Path], list[float]]:
    capture_root_value = manifest.get("capture_root")
    capture_root = _resolve(str(capture_root_value)) if capture_root_value else manifest_path.parent / "captures"
    paths: list[Path] = []
    times: list[float] = []
    for frame in manifest.get("frames") or []:
        if frame.get("valid") is not True or not frame.get("path"):
            continue
        path = Path(str(frame["path"]))
        path = path.resolve() if path.is_absolute() else (capture_root / path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Capture v2 frame is missing: {path}")
        paths.append(path)
        times.append(float(frame.get("requested_time_seconds") or 0.0))
    if not paths:
        raise ValueError(f"Capture v2 has no valid frames: {manifest_path}")
    return paths, times


def _model_compatible_features(manifest: dict[str, Any], image: dict[str, float]) -> dict[str, Any]:
    frame_metrics = [frame.get("pixel_metrics") or {} for frame in manifest.get("frames") or []]
    cropped = sum(bool(metric.get("cropped")) for metric in frame_metrics)
    features: dict[str, Any] = {
        **image,
        "auto.status": "pass" if not manifest.get("render_error") and int(manifest.get("invalid_frame_count") or 0) == 0 and cropped == 0 else "warn",
        "auto.frame_delta_mean": float(image.get("image.temporal_delta.mean") or 0.0),
        "auto.hard_reject_count": 0.0,
        "auto.mean_luminance_peak": float(image.get("image.mean_luma.max") or 0.0),
        "auto.missing_asset_count": 0.0,
        "auto.missing_frame_count": float(manifest.get("invalid_frame_count") or 0),
        "auto.overexposed_ratio_peak": float(image.get("image.overexposed_ratio.max") or 0.0),
        "auto.unity_error_count": 1.0 if manifest.get("render_error") else 0.0,
        "auto.visible_area_ratio_peak": max((float(metric.get("visible_area_ratio") or 0.0) for metric in frame_metrics), default=0.0),
        "spec.adapter.generator_family": "source_prefab_render",
        "spec.adapter.name": "source_ingest.render_review",
        "spec.adapter.specialized_metrics.length": 3.0,
        "spec.adapter.version": "0.1.0",
        "spec.effect_family": "source_ingest",
        "spec.effect_type": "imported_prefab",
        "spec.generation.generator": "source_prefab_render",
        "spec.generation.generator_version": "0.1.0",
        "spec.layers.length": 1.0,
        "spec.layers.source_prefab.constraints.length": 2.0,
        "spec.layers.source_prefab.role": "source_prefab",
        "spec.layers.source_prefab.status": "active",
        "spec.layers.source_prefab.topology": "imported_prefab",
    }
    return features


def build_judge_features(active_root: Path, output_root: Path) -> dict[str, Path]:
    active_root, output_root = active_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Judge feature output already exists and is not empty: {output_root}")
    active = _read_json(active_root / "active_learning_batch.json")
    rows: list[dict[str, Any]] = []
    feature_names: set[str] = set()
    for item in active.get("items") or []:
        manifest_path = _resolve(str(item["capture_manifest_path"]))
        manifest = _read_json(manifest_path)
        if manifest.get("capture_pipeline_version") != CAPTURE_PIPELINE or manifest.get("image_sequence_training_eligible") is not True:
            raise ValueError(f"Judge features require eligible Capture v2: {manifest_path}")
        frame_paths, times = _capture_frames(manifest_path, manifest)
        features = _model_compatible_features(manifest, aggregate_image_features(frame_paths, times))
        feature_names.update(features)
        rows.append({
            "schema_version": FEATURE_SCHEMA,
            "candidate_id": item["sample_id"],
            "group_id": item["cluster_id"],
            "features": features,
            "provenance": {
                "prefab_path": item["prefab_path"],
                "capture_manifest_path": _portable(manifest_path),
                "frame_paths": [_portable(path) for path in frame_paths],
                "label_status": "unlabeled_judge_input",
            },
        })
    if len(rows) != int(active.get("review_budget") or 0):
        raise ValueError("Judge feature count does not match active-learning review budget")
    feature_path = _write_jsonl(output_root / "judge_input.jsonl", rows)
    manifest_path = _write_json(output_root / "feature_manifest.json", {
        "schema_version": FEATURE_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_active_batch": _portable(active_root / "active_learning_batch.json"),
        "record_count": len(rows),
        "feature_count": len(feature_names),
        "feature_names": sorted(feature_names),
        "label_status": "unlabeled_judge_input",
        "domain_status": "capture_v2_partial_training_feature_compatibility",
        "status": "pass",
    })
    return {"features": feature_path, "manifest": manifest_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Aesthetic Judge inputs for an active Prefab review batch.")
    parser.add_argument("--active-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_judge_features(args.active_root, args.output_root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
