"""Finalize incremental Prefab Capture v2 outputs without converting technical failures to aesthetic labels."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.capture_visual_integrity import analyze_capture_manifest


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def finalize_capture_batch(batch_root: Path, output_root: Path) -> dict[str, Path]:
    batch_root, output_root = batch_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"capture report output already exists and is not empty: {output_root}")
    batch = _read(batch_root / "capture_batch_manifest.json")
    records = []
    missing = 0
    for selected in batch["selected"]:
        manifest_path = batch_root / "cases" / selected["candidate_id"] / "capture_manifest.json"
        timeline_path = batch_root / "cases" / selected["candidate_id"] / "material_timeline.json"
        if not manifest_path.is_file() or not timeline_path.is_file():
            missing += 1
            continue
        capture = _read(manifest_path)
        frames = capture.get("frames") or []
        peak = max((float((frame.get("pixel_metrics") or {}).get("visible_area_ratio") or 0.0) for frame in frames), default=0.0)
        visual_integrity = analyze_capture_manifest(manifest_path, capture)
        image_ready = capture.get("image_sequence_training_eligible") is True and not visual_integrity["material_render_error"]
        if capture.get("render_error") or int(capture.get("invalid_frame_count") or 0) > 0:
            status = "capture_error"
        elif image_ready:
            status = "visual_feature_ready"
        else:
            status = "technical_only"
        records.append({
            "schema_version": "vfx_full_prefab_capture_record.v1",
            "batch_id": batch["batch_id"],
            "candidate_id": selected["candidate_id"],
            "prefab_path": selected["prefab_path"],
            "source_group": selected["source_group"],
            "effect_family_hint": selected["effect_family_hint"],
            "status": status,
            "capture_manifest_path": _portable(manifest_path),
            "material_timeline_path": _portable(timeline_path),
            "capture_pipeline_version": capture.get("capture_pipeline_version"),
            "valid_frame_count": int(capture.get("valid_frame_count") or 0),
            "invalid_frame_count": int(capture.get("invalid_frame_count") or 0),
            "max_visible_area_ratio": peak,
            "near_blank": peak < 0.001,
            "cropped_frame_count": sum(bool((frame.get("pixel_metrics") or {}).get("cropped")) for frame in frames),
            "material_render_error": visual_integrity["material_render_error"],
            "material_render_error_frame_count": visual_integrity["error_magenta_frame_count"],
            "max_error_magenta_ratio": visual_integrity["max_error_magenta_ratio"],
            "image_sequence_training_eligible": image_ready,
            "full_visual_training_eligible": bool(capture.get("full_visual_training_eligible")),
            "visual_evidence_status": capture.get("visual_evidence_status"),
            "limitations": list(capture.get("visual_evidence_limitations") or []) + (["Unity error-magenta material pixels detected."] if visual_integrity["material_render_error"] else []),
            "aesthetic_label_source": "none",
            "training": {"eligible_tasks": ["visual_self_supervision", "temporal_embedding", "clustering", "retrieval"] if image_ready else ["technical_failure_modeling"], "excluded_tasks": ["aesthetic_judge", "human_gold", "positive_generation_supervision", "preference_training", "regression_evaluation"]},
        })
    ids = [row["candidate_id"] for row in records]
    gates = {
        "missing_capture_outputs": missing,
        "duplicate_candidates": len(ids) - len(set(ids)),
        "capture_v2_mismatch": sum(row["capture_pipeline_version"] != "play_mode_runtime_isolated_multiview.v2" for row in records),
        "invalid_frames": sum(row["invalid_frame_count"] for row in records),
        "technical_failure_as_aesthetic_label": sum(row["aesthetic_label_source"] != "none" for row in records),
    }
    if any(gates.values()):
        raise ValueError(f"capture report quality gate failed: {gates}")
    records_path = _write_jsonl(output_root / "records.jsonl", records)
    visual_path = _write_jsonl(output_root / "visual_feature_ready.jsonl", (row for row in records if row["status"] == "visual_feature_ready"))
    technical_path = _write_jsonl(output_root / "technical_only.jsonl", (row for row in records if row["status"] != "visual_feature_ready"))
    limitations = sorted({limitation for row in records for limitation in row["limitations"]})
    report = {
        "schema_version": "vfx_full_prefab_capture_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch["batch_id"],
        "selected_count": int(batch["selected_count"]),
        "capture_count": len(records),
        "valid_frame_count": sum(row["valid_frame_count"] for row in records),
        "invalid_frame_count": sum(row["invalid_frame_count"] for row in records),
        "visual_feature_ready_count": sum(row["status"] == "visual_feature_ready" for row in records),
        "technical_only_count": sum(row["status"] != "visual_feature_ready" for row in records),
        "full_visual_ready_count": sum(row["full_visual_training_eligible"] for row in records),
        "near_blank_count": sum(row["near_blank"] for row in records),
        "cropped_capture_count": sum(row["cropped_frame_count"] > 0 for row in records),
        "material_render_error_count": sum(row["material_render_error"] for row in records),
        "effect_family_counts": dict(sorted(Counter(row["effect_family_hint"] for row in records).items())),
        "status_counts": dict(sorted(Counter(row["status"] for row in records).items())),
        "files": {"records": _portable(records_path), "visual_feature_ready": _portable(visual_path), "technical_only": _portable(technical_path)},
        "quality_gates": gates,
        "limitations": limitations,
        "status": "pass",
    }
    schema = _read(_repo_root() / "workspace/data/vfx_generation/schemas/full_prefab_capture_report.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        raise ValueError(f"capture report schema error: {errors[0].message}")
    report_path = _write(output_root / "capture_report.json", report)
    return {"report": report_path, "records": records_path, "visual_feature_ready": visual_path, "technical_only": technical_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize a full Prefab Capture v2 batch.")
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = finalize_capture_batch(args.batch_root, args.output_root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
