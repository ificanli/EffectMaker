"""Audit course records for professional Aesthetic Teacher training readiness."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "vfx_professional_aesthetic_teacher_readiness.v1"
REQUIRED_FIELDS = (
    "verified_professional_source",
    "explicit_aesthetic_judgment",
    "dynamic_frame_or_timecode_evidence",
    "judgment_axes",
    "verified_unity_reproduction",
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _readiness(record: dict[str, Any]) -> dict[str, bool]:
    return {
        "verified_professional_source": record.get("source_expertise_status") == "verified_professional",
        "explicit_aesthetic_judgment": record.get("record_type") == "tutorial_fact" and record.get("status") == "verified",
        "dynamic_frame_or_timecode_evidence": bool(record.get("frame_paths") or record.get("timecodes")),
        "judgment_axes": bool(record.get("judgment_axes")),
        "verified_unity_reproduction": record.get("unity_reproduction_status") == "verified",
    }


def audit(index_root: Path, output_root: Path, audit_id: str) -> dict[str, Path]:
    index_root, output_root = index_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"teacher readiness output already exists and is not empty: {output_root}")
    index = _read_json(index_root / "course_knowledge_index.json")
    records = _read_jsonl(index_root / str(index["files"]["records"]))
    candidates: list[dict[str, Any]] = []
    ready: list[dict[str, Any]] = []
    for record in records:
        if record.get("record_type") not in {"tutorial_fact", "engineering_mapping"} or record.get("effect_family") == "unknown":
            continue
        checks = _readiness(record)
        candidate = {
            "record_id": record["record_id"],
            "source_path": record["source_path"],
            "effect_family": record["effect_family"],
            "record_type": record["record_type"],
            "source_status": record["status"],
            "evidence_level": record["evidence_level"],
            "expert_judgment": record.get("excerpt"),
            "judgment_axes": record.get("judgment_axes") or [],
            "timecodes": record.get("timecodes") or [],
            "frame_paths": record.get("frame_paths") or [],
            "unity_reproduction_report": record.get("unity_reproduction_report"),
            "readiness": checks,
            "missing_requirements": [name for name in REQUIRED_FIELDS if not checks[name]],
            "teacher_training_eligible": all(checks.values()),
            "allowed_use": "aesthetic_teacher_training" if all(checks.values()) else "knowledge_prior_and_evidence_completion_only",
        }
        candidates.append(candidate)
        if candidate["teacher_training_eligible"]:
            ready.append(candidate)
    candidates_path = _write_jsonl(output_root / "teacher_candidates.jsonl", candidates)
    ready_path = _write_jsonl(output_root / "teacher_ready.jsonl", ready)
    missing_counts = Counter(requirement for row in candidates for requirement in row["missing_requirements"])
    manifest_path = _write_json(output_root / "readiness_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audit_id": audit_id,
        "source_index_id": index.get("index_id"),
        "source_record_count": len(records),
        "candidate_count": len(candidates),
        "teacher_ready_count": len(ready),
        "missing_requirement_counts": dict(sorted(missing_counts.items())),
        "required_fields": list(REQUIRED_FIELDS),
        "policy": {
            "nonexpert_feedback_is_semantic_only": True,
            "course_text_alone_is_not_aesthetic_label": True,
            "professional_source_requires_verification": True,
            "unity_reproduction_required": True,
        },
        "files": {"candidates": candidates_path.name, "teacher_ready": ready_path.name},
        "status": "ready" if ready else "blocked_no_teacher_ready_records",
    })
    return {"manifest": manifest_path, "candidates": candidates_path, "teacher_ready": ready_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit professional Aesthetic Teacher training readiness.")
    parser.add_argument("--index-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--audit-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = audit(args.index_root, args.output_root, args.audit_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
