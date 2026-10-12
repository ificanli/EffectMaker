"""Build reproducible VFX candidate feature matrices from Unity render runs."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
import pandas as pd


FEATURE_SCHEMA_VERSION = "vfx_candidate_features.v1"
FEATURE_EXTRACTOR_VERSION = "vfx_training_features.1.0.0"
EXCLUDED_SPEC_KEYS = {
    "candidate_id",
    "run_id",
    "prompt",
    "negative_prompt",
    "source_manifest_path",
    "source_sample_path",
    "render_manifest_path",
    "unity_project",
    "scene",
    "camera",
}


class FeatureExtractionError(ValueError):
    """Raised when a render run cannot produce a trustworthy feature matrix."""


def _read_image(path: Path) -> np.ndarray | None:
    """Read images through bytes so Windows paths containing non-ASCII text work."""
    try:
        encoded = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    return cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeatureExtractionError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FeatureExtractionError(f"JSON object expected: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def _resolve(path_text: str | Path, base: Path) -> Path:
    path = Path(path_text)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _finite(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def _numeric_summary(prefix: str, values: list[float], output: dict[str, Any]) -> None:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=np.float64)
    if finite.size == 0:
        return
    output[f"{prefix}.count"] = int(finite.size)
    output[f"{prefix}.mean"] = float(finite.mean())
    output[f"{prefix}.std"] = float(finite.std())
    output[f"{prefix}.min"] = float(finite.min())
    output[f"{prefix}.max"] = float(finite.max())


def _flatten_spec(value: Any, prefix: str, output: dict[str, Any]) -> None:
    if not prefix:
        return
    key_name = prefix.rsplit(".", 1)[-1]
    if key_name in EXCLUDED_SPEC_KEYS or key_name.endswith("_path") or key_name.endswith("_paths"):
        return
    if value is None:
        return
    if isinstance(value, bool):
        output[prefix] = int(value)
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        finite = _finite(float(value))
        if finite is not None:
            output[prefix] = finite
        return
    if isinstance(value, str):
        if len(value) <= 80 and "/" not in value and "\\" not in value:
            output[prefix] = value
        return
    if isinstance(value, dict):
        for child_key in sorted(value):
            _flatten_spec(value[child_key], f"{prefix}.{child_key}", output)
        return
    if not isinstance(value, list):
        return

    output[f"{prefix}.length"] = len(value)
    if not value:
        return
    if all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        _numeric_summary(prefix, [float(item) for item in value], output)
        return
    if all(isinstance(item, list) and item and all(isinstance(number, (int, float)) for number in item) for item in value):
        width = max(len(item) for item in value)
        for column in range(width):
            column_values = [float(item[column]) for item in value if len(item) > column]
            _numeric_summary(f"{prefix}.axis_{column}", column_values, output)
        return
    for index, item in enumerate(value[:8]):
        if isinstance(item, dict):
            role = item.get("role") or item.get("name") or str(index)
            role_text = str(role).replace(" ", "_")[:40]
            _flatten_spec(item, f"{prefix}.{role_text}", output)


def extract_spec_features(spec: dict[str, Any]) -> dict[str, Any]:
    features: dict[str, Any] = {}
    for key in ("effect_family", "effect_type", "adapter", "material_profile", "layers", "target_style_profile"):
        if key in spec:
            _flatten_spec(spec[key], f"spec.{key}", features)
    generation = spec.get("generation")
    if isinstance(generation, dict):
        for key in ("generator", "generator_version", "parent_candidate_id"):
            if key in generation:
                _flatten_spec(generation[key], f"spec.generation.{key}", features)
    return features


def _border_background(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    border = np.concatenate((gray[0], gray[-1], gray[:, 0], gray[:, -1]))
    return float(np.median(border))


def extract_frame_features(path: Path) -> tuple[dict[str, float], np.ndarray]:
    image = _read_image(path)
    if image is None:
        raise FeatureExtractionError(f"OpenCV could not read image: {path}")
    if image.ndim == 2:
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        alpha = None
    elif image.shape[2] == 4:
        bgr = image[:, :, :3]
        alpha = image[:, :, 3]
    else:
        bgr = image[:, :, :3]
        alpha = None

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    background = _border_background(gray)
    if alpha is not None and np.any(alpha < 250):
        mask = alpha > 8
    else:
        threshold = max(8.0, background + 8.0)
        mask = np.abs(gray.astype(np.float32) - background) > threshold
    visible_pixels = int(mask.sum())
    total_pixels = int(mask.size or 1)
    visible_ratio = visible_pixels / total_pixels

    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges)) / total_pixels
    visible_luma = gray[mask] if visible_pixels else gray.reshape(-1)
    visible_saturation = hsv[:, :, 1][mask] if visible_pixels else hsv[:, :, 1].reshape(-1)

    bbox_area_ratio = 0.0
    bbox_aspect = 0.0
    centroid_x = 0.5
    centroid_y = 0.5
    if visible_pixels:
        ys, xs = np.nonzero(mask)
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        bbox_width = x_max - x_min + 1
        bbox_height = y_max - y_min + 1
        bbox_area_ratio = bbox_width * bbox_height / total_pixels
        bbox_aspect = bbox_width / max(1, bbox_height)
        centroid_x = float(xs.mean()) / max(1, gray.shape[1] - 1)
        centroid_y = float(ys.mean()) / max(1, gray.shape[0] - 1)

    frame_features = {
        "visible_ratio": visible_ratio,
        "mean_luma": float(visible_luma.mean()) / 255.0,
        "std_luma": float(visible_luma.std()) / 255.0,
        "p95_luma": float(np.percentile(visible_luma, 95)) / 255.0,
        "overexposed_ratio": float(np.count_nonzero(gray >= 245)) / total_pixels,
        "edge_density": edge_density,
        "mean_saturation": float(visible_saturation.mean()) / 255.0,
        "bbox_area_ratio": bbox_area_ratio,
        "bbox_aspect": bbox_aspect,
        "centroid_x": centroid_x,
        "centroid_y": centroid_y,
        "background_luma": background / 255.0,
        "width": float(gray.shape[1]),
        "height": float(gray.shape[0]),
    }
    preview = cv2.resize(gray, (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    return frame_features, preview


def aggregate_image_features(frame_paths: list[Path], times: list[float | None]) -> dict[str, float]:
    if not frame_paths:
        return {"image.frame_count": 0.0}
    frames: list[dict[str, float]] = []
    previews: list[np.ndarray] = []
    for frame_path in frame_paths:
        features, preview = extract_frame_features(frame_path)
        frames.append(features)
        previews.append(preview)

    result: dict[str, float] = {"image.frame_count": float(len(frames))}
    for name in sorted(frames[0]):
        values = np.asarray([frame[name] for frame in frames], dtype=np.float64)
        result[f"image.{name}.mean"] = float(values.mean())
        result[f"image.{name}.max"] = float(values.max())
        result[f"image.{name}.min"] = float(values.min())
        result[f"image.{name}.std"] = float(values.std())

    visible_values = np.asarray([frame["visible_ratio"] for frame in frames], dtype=np.float64)
    peak_index = int(visible_values.argmax())
    result["image.peak_frame_index"] = float(peak_index)
    if peak_index < len(times) and times[peak_index] is not None:
        result["image.peak_time_seconds"] = float(times[peak_index])
    result["image.active_frame_ratio"] = float(np.count_nonzero(visible_values >= 0.01)) / len(frames)

    if len(previews) > 1:
        deltas = [float(np.abs(previews[index] - previews[index - 1]).mean()) for index in range(1, len(previews))]
        result["image.temporal_delta.mean"] = float(np.mean(deltas))
        result["image.temporal_delta.max"] = float(np.max(deltas))
        result["image.temporal_delta.std"] = float(np.std(deltas))
    else:
        result["image.temporal_delta.mean"] = 0.0
        result["image.temporal_delta.max"] = 0.0
        result["image.temporal_delta.std"] = 0.0
    return result


def _auto_eval_features(candidate: dict[str, Any]) -> dict[str, Any]:
    auto_eval = candidate.get("auto_eval")
    if not isinstance(auto_eval, dict):
        return {}
    output: dict[str, Any] = {}
    status = auto_eval.get("status")
    if isinstance(status, str):
        output["auto.status"] = status
    metrics = auto_eval.get("metrics")
    if isinstance(metrics, dict):
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                output[f"auto.{key}"] = float(value)
    reasons = auto_eval.get("hard_reject_reasons")
    if isinstance(reasons, list):
        output["auto.hard_reject_count"] = float(len(reasons))
        for reason in reasons:
            output[f"auto.reject.{reason}"] = 1.0
    return output


def build_feature_matrix(run_root: Path, output_dir: Path) -> dict[str, Path]:
    run_root = run_root.resolve()
    output_dir = output_dir.resolve()
    manifest_path = run_root / "run_manifest.json"
    manifest = _load_json(manifest_path)
    run_id = str(manifest.get("run_id") or run_root.name)
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise FeatureExtractionError(f"run has no rendered candidates: {run_root}")

    rows: list[dict[str, Any]] = []
    flat_rows: list[dict[str, Any]] = []
    feature_names: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id:
            raise FeatureExtractionError("candidate_id is missing")
        spec_path_text = candidate.get("spec_path")
        if not isinstance(spec_path_text, str):
            raise FeatureExtractionError(f"spec_path is missing for {candidate_id}")
        spec_path = _resolve(spec_path_text, run_root)
        spec = _load_json(spec_path)
        capture_root_text = candidate.get("capture_root")
        capture_root = _resolve(capture_root_text, run_root) if isinstance(capture_root_text, str) else spec_path.parent
        frame_paths: list[Path] = []
        times: list[float | None] = []
        for frame in candidate.get("frames", []):
            if not isinstance(frame, dict) or not frame.get("valid") or not isinstance(frame.get("path"), str):
                continue
            frame_path = _resolve(str(frame["path"]), capture_root)
            if not frame_path.is_file():
                raise FeatureExtractionError(f"valid frame does not exist: {frame_path}")
            frame_paths.append(frame_path)
            time_value = frame.get("requested_time_seconds")
            times.append(float(time_value) if isinstance(time_value, (int, float)) else None)
        if not frame_paths:
            raise FeatureExtractionError(f"candidate has no valid frame files: {candidate_id}")

        features = extract_spec_features(spec)
        features.update(_auto_eval_features(candidate))
        features.update(aggregate_image_features(frame_paths, times))
        feature_names.update(features)
        row = {
            "schema_version": FEATURE_SCHEMA_VERSION,
            "run_id": run_id,
            "candidate_id": candidate_id,
            "group_id": run_id,
            "feature_extractor_version": FEATURE_EXTRACTOR_VERSION,
            "features": features,
            "provenance": {
                "run_manifest_path": manifest_path.as_posix(),
                "spec_path": spec_path.as_posix(),
                "frame_paths": [path.as_posix() for path in frame_paths],
            },
        }
        rows.append(row)
        flat_rows.append({"run_id": run_id, "candidate_id": candidate_id, **features})

    output_dir.mkdir(parents=True, exist_ok=True)
    feature_jsonl = _write_jsonl(output_dir / "candidate_features.jsonl", rows)
    feature_csv = output_dir / "candidate_features.csv"
    pd.DataFrame(flat_rows).reindex(columns=["run_id", "candidate_id", *sorted(feature_names)]).to_csv(feature_csv, index=False)
    schema_path = _write_json(
        output_dir / "feature_schema.json",
        {
            "schema_version": FEATURE_SCHEMA_VERSION,
            "feature_extractor_version": FEATURE_EXTRACTOR_VERSION,
            "run_id": run_id,
            "candidate_count": len(rows),
            "feature_count": len(feature_names),
            "feature_names": sorted(feature_names),
            "source_run_manifest": manifest_path.as_posix(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label_status": "unlabeled_feature_matrix",
            "notes": [
                "Features are measurable inputs, not quality labels.",
                "Human pairwise feedback is required before preference-model training.",
            ],
        },
    )
    return {"feature_jsonl": feature_jsonl, "feature_csv": feature_csv, "feature_schema": schema_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a VFX candidate feature matrix from a rendered run.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = build_feature_matrix(args.run_root, args.output_dir)
    except (FeatureExtractionError, OSError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
