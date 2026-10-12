"""Merge verified professional Teacher indexes without losing provenance."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def merge_indexes(index_roots: list[Path], output_root: Path, catalog_id: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional Teacher catalog output already exists and is not empty: {output_root}")
    if not index_roots:
        raise ValueError("at least one Teacher index is required")
    records_by_id: dict[str, dict[str, Any]] = {}
    source_indexes = []
    for index_root in index_roots:
        root = index_root.resolve()
        index = _read(root / "course_knowledge_index.json")
        source_indexes.append({"index_id": index.get("index_id"), "path": root.as_posix()})
        for record in _read_jsonl(root / str(index["files"]["records"])):
            record_id = str(record.get("record_id") or "")
            if not record_id:
                raise ValueError(f"Teacher record without record_id: {root}")
            previous = records_by_id.get(record_id)
            if previous is not None and previous != record:
                raise ValueError(f"conflicting Teacher record: {record_id}")
            records_by_id[record_id] = record
    records = [records_by_id[key] for key in sorted(records_by_id)]
    records_path = _write_jsonl(output_root / "course_knowledge_records.jsonl", records)
    index_path = _write(output_root / "course_knowledge_index.json", {
        "schema_version": "course_knowledge_index.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_id": catalog_id,
        "input_count": len(index_roots),
        "record_count": len(records),
        "record_type_counts": dict(sorted(Counter(str(row.get("record_type") or "unknown") for row in records).items())),
        "status_counts": dict(sorted(Counter(str(row.get("status") or "unknown") for row in records).items())),
        "effect_family_counts": dict(sorted(Counter(str(row.get("effect_family") or "unknown") for row in records).items())),
        "source_indexes": source_indexes,
        "files": {"records": records_path.name},
        "policy": {"deduplicate_by_record_id": True, "conflicting_duplicate_is_error": True, "preserve_source_provenance": True},
        "status": "pass",
    })
    return {"index": index_path, "records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge verified professional Teacher indexes.")
    parser.add_argument("--index-root", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--catalog-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = merge_indexes(args.index_root, args.output_root, args.catalog_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
