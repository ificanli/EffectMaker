"""Detect renderer failure colors in Unity Capture v2 image sequences."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image


ERROR_MAGENTA_RATIO_THRESHOLD = 0.001
ERROR_MAGENTA_MIN_PIXELS = 64
ERROR_MAGENTA_VISIBLE_RATIO_THRESHOLD = 0.5


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _resolve(value: str, base: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return ((base or _repo_root()) / path).resolve()


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def analyze_frame(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    error_mask = (rgb[:, :, 0] >= 250) & (rgb[:, :, 1] <= 8) & (rgb[:, :, 2] >= 250)
    error_pixels = int(error_mask.sum())
    total_pixels = max(1, int(error_mask.size))
    ratio = error_pixels / total_pixels
    corner_size = max(1, min(5, rgb.shape[0] // 2, rgb.shape[1] // 2))
    corners = np.concatenate((
        rgb[:corner_size, :corner_size].reshape(-1, 3),
        rgb[:corner_size, -corner_size:].reshape(-1, 3),
        rgb[-corner_size:, :corner_size].reshape(-1, 3),
        rgb[-corner_size:, -corner_size:].reshape(-1, 3),
    ))
    background = np.median(corners, axis=0)
    visible_mask = np.max(np.abs(rgb.astype(np.int16) - background.astype(np.int16)), axis=2) > 8
    visible_pixels = int(visible_mask.sum())
    visible_ratio = visible_pixels / total_pixels
    magenta_visible_ratio = error_pixels / max(1, visible_pixels)
    material_render_error = (
        error_pixels >= ERROR_MAGENTA_MIN_PIXELS
        and ratio >= ERROR_MAGENTA_RATIO_THRESHOLD
        and magenta_visible_ratio >= ERROR_MAGENTA_VISIBLE_RATIO_THRESHOLD
    )
    return {
        "path": _portable(path),
        "error_magenta_pixel_count": error_pixels,
        "error_magenta_ratio": ratio,
        "visible_pixel_count": visible_pixels,
        "visible_area_ratio": visible_ratio,
        "error_magenta_visible_ratio": magenta_visible_ratio,
        "unity_error_magenta": material_render_error,
    }


def analyze_capture_manifest(manifest_path: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = manifest or _read_json(manifest_path)
    capture_root_value = manifest.get("capture_root")
    capture_root = _resolve(str(capture_root_value)) if capture_root_value else manifest_path.parent / "captures"
    frames = []
    for frame in manifest.get("frames") or []:
        if frame.get("valid") is not True or not frame.get("path"):
            continue
        path = _resolve(str(frame["path"]), capture_root)
        if not path.is_file():
            raise FileNotFoundError(f"Capture frame is missing: {path}")
        result = analyze_frame(path)
        result["requested_time_seconds"] = float(frame.get("requested_time_seconds") or 0.0)
        frames.append(result)
    affected = [frame for frame in frames if frame["unity_error_magenta"]]
    max_ratio = max((float(frame["error_magenta_ratio"]) for frame in frames), default=0.0)
    max_visible_ratio = max((float(frame["error_magenta_visible_ratio"]) for frame in frames), default=0.0)
    return {
        "schema_version": "vfx_capture_visual_integrity.v1",
        "capture_manifest_path": _portable(manifest_path),
        "prefab_path": manifest.get("effect"),
        "frame_count": len(frames),
        "error_magenta_frame_count": len(affected),
        "max_error_magenta_ratio": max_ratio,
        "max_error_magenta_visible_ratio": max_visible_ratio,
        "material_render_error": bool(affected),
        "status": "technical_exclusion" if affected else "pass",
        "reason": "unity_error_magenta" if affected else None,
        "frames": frames,
    }


def audit_capture_roots(capture_roots: Iterable[Path], output_root: Path, audit_id: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"visual integrity output already exists and is not empty: {output_root}")
    latest: dict[str, tuple[Path, dict[str, Any]]] = {}
    for root in capture_roots:
        for path in root.resolve().rglob("capture_manifest.json"):
            manifest = _read_json(path)
            prefab = str(manifest.get("effect") or "").replace("\\", "/")
            if not prefab:
                continue
            previous = latest.get(prefab)
            if previous is None or str(manifest.get("created_at") or "") > str(previous[1].get("created_at") or ""):
                latest[prefab] = (path, manifest)
    records = [analyze_capture_manifest(path, manifest) for _, (path, manifest) in sorted(latest.items())]
    records_path = _write_jsonl(output_root / "records.jsonl", records)
    exclusions_path = _write_jsonl(output_root / "technical_exclusions.jsonl", [row for row in records if row["material_render_error"]])
    manifest_path = _write_json(output_root / "audit_manifest.json", {
        "schema_version": "vfx_capture_visual_integrity_audit.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audit_id": audit_id,
        "capture_count": len(records),
        "pass_count": sum(row["status"] == "pass" for row in records),
        "technical_exclusion_count": sum(row["status"] == "technical_exclusion" for row in records),
        "reason_counts": dict(sorted(Counter(row["reason"] for row in records if row["reason"]).items())),
        "thresholds": {
            "error_magenta_ratio": ERROR_MAGENTA_RATIO_THRESHOLD,
            "error_magenta_min_pixels": ERROR_MAGENTA_MIN_PIXELS,
            "error_magenta_visible_ratio": ERROR_MAGENTA_VISIBLE_RATIO_THRESHOLD,
            "pixel_definition": "R>=250,G<=8,B>=250",
            "visible_pixel_definition": "max(abs(RGB-background_median_from_corners))>8",
        },
        "quality_gates": {"aesthetic_negative_count": 0, "missing_capture_count": 0},
        "files": {"records": records_path.name, "technical_exclusions": exclusions_path.name},
        "status": "pass",
    })
    return {"manifest": manifest_path, "records": records_path, "exclusions": exclusions_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect Unity error-magenta frames in Capture v2 outputs.")
    parser.add_argument("--capture-root", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--audit-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = audit_capture_roots(args.capture_root, args.output_root, args.audit_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
