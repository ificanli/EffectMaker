"""Build an incremental, leakage-aware index for large Unity VFX Prefab corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _manifest_paths(inputs: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for raw in inputs:
        path = raw.resolve()
        if path.is_file() and path.name == "source_manifest.json":
            found.add(path)
        elif path.is_dir():
            direct = path / "source_manifest.json"
            if direct.is_file():
                found.add(direct)
            else:
                found.update(candidate.resolve() for candidate in path.rglob("source_manifest.json"))
        else:
            raise FileNotFoundError(f"corpus input does not exist: {path}")
    return sorted(found, key=lambda item: item.as_posix().casefold())


def _source_summary(manifest: dict[str, Any]) -> dict[str, int]:
    counts = Counter(str(row.get("role") or "unknown") for row in manifest.get("files", []) if isinstance(row, dict))
    return dict(sorted(counts.items()))


def _split_for(group_id: str) -> str:
    bucket = int(_digest(group_id)[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def _record_from_file(manifest_path: Path, manifest: dict[str, Any], file_row: dict[str, Any]) -> dict[str, Any]:
    source_id = str(manifest.get("source_id") or manifest_path.parent.name)
    prefab_path = str(file_row.get("path") or "")
    source_project = str((manifest.get("unity_context") or {}).get("original_project_path") or "")
    license_info = manifest.get("license") if isinstance(manifest.get("license"), dict) else {}
    license_status = str(license_info.get("status") or "unknown")
    content_sha = str(file_row.get("sha256") or "")
    # Exact copies imported from different batches must stay in one split, or the
    # controller can memorize an asset through a second source package.
    split_identity = f"content:{content_sha}" if content_sha else f"source_path:{source_id}|{prefab_path}"
    group_id = _digest(split_identity)[:20]
    record_key = _digest(f"{source_id}|{prefab_path}")
    excluded = []
    if license_status in {"unknown", "unverified", ""}:
        excluded.append("license_review_required")
    return {
        "schema_version": "vfx_prefab_corpus_record.v1",
        "record_key": record_key,
        "source_id": source_id,
        "source_manifest_path": manifest_path.as_posix(),
        "source_project_path": source_project,
        "prefab_path": prefab_path,
        "prefab_guid": file_row.get("unity_guid"),
        "content_sha256": content_sha or None,
        "source_group": source_id,
        "split_group": group_id,
        "split": _split_for(group_id),
        "license_status": license_status,
        "local_training_allowed": license_status in {"local_reference_only", "user_owned_local_project", "apache-2.0", "mit"},
        "record_status": "active",
        "training_eligibility": {
            "source_structure_supervision": not excluded,
            "controller_sft": False,
            "positive_generation_supervision": False,
            "prompt_condition_supervision": False,
            "preference_training": False,
            "excluded_reasons": excluded,
        },
    }


def _validate_records(records: list[dict[str, Any]]) -> tuple[int, int]:
    keys = [str(row["record_key"]) for row in records]
    duplicate_count = len(keys) - len(set(keys))
    split_groups: dict[str, set[str]] = {}
    for row in records:
        split_groups.setdefault(str(row["split_group"]), set()).add(str(row["split"]))
    overlap_count = sum(len(splits) > 1 for splits in split_groups.values())
    if overlap_count:
        raise ValueError(f"split group leakage detected: {overlap_count} groups")
    return duplicate_count, overlap_count


def build_corpus(inputs: Iterable[Path], output_dir: Path, corpus_id: str, previous_manifest: Path | None = None) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"corpus output already exists and is not empty: {output_dir}")
    manifests = _manifest_paths(inputs)
    if not manifests:
        raise ValueError("no source_manifest.json found in corpus inputs")
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    for manifest_path in manifests:
        try:
            manifest = _read_json(manifest_path)
            source_id = str(manifest.get("source_id") or manifest_path.parent.name)
            source_summaries.append({"source_id": source_id, "manifest_path": manifest_path.as_posix(), "file_counts": _source_summary(manifest)})
            prefab_files = [row for row in manifest.get("files", []) if isinstance(row, dict) and row.get("role") == "prefab"]
            if not prefab_files:
                failures.append({"source_manifest_path": manifest_path.as_posix(), "reason": "no_prefab_file_records"})
            records.extend(_record_from_file(manifest_path, manifest, file_row) for file_row in prefab_files)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failures.append({"source_manifest_path": manifest_path.as_posix(), "reason": str(error)})
    if failures and not records:
        raise ValueError(f"all source manifests failed: {failures[0]['reason']}")
    unique_records: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for row in records:
        key = str(row["record_key"])
        if key in unique_records:
            duplicate_count += 1
            failures.append({
                "source_manifest_path": row["source_manifest_path"],
                "prefab_path": row["prefab_path"],
                "reason": "duplicate_source_key",
                "kept_manifest_path": unique_records[key]["source_manifest_path"],
            })
            continue
        unique_records[key] = row
    records = list(unique_records.values())
    _ignored_duplicate_count, overlap_count = _validate_records(records)
    previous: dict[str, dict[str, Any]] = {}
    if previous_manifest is not None and previous_manifest.resolve().is_file():
        previous_payload = _read_json(previous_manifest.resolve())
        previous_records_path = Path(str(previous_payload.get("files", {}).get("records") or ""))
        if not previous_records_path.is_absolute():
            previous_records_path = previous_manifest.resolve().parent / previous_records_path
        if previous_records_path.is_file():
            previous = {str(row["record_key"]): row for row in (json.loads(line) for line in previous_records_path.read_text(encoding="utf-8").splitlines() if line.strip())}
    current = {str(row["record_key"]): row for row in records}
    changed = sum(key in previous and previous[key].get("content_sha256") != row.get("content_sha256") for key, row in current.items())
    new_count = sum(key not in previous for key in current)
    unchanged_count = sum(key in previous and previous[key].get("content_sha256") == row.get("content_sha256") for key, row in current.items())
    removed_count = sum(key not in current for key in previous)
    records_path = _write_jsonl(output_dir / "prefab_records.jsonl", records)
    failures_path = _write_jsonl(output_dir / "failures.jsonl", failures)
    splits_path = _write_jsonl(output_dir / "split_assignments.jsonl", [{"record_key": row["record_key"], "split_group": row["split_group"], "split": row["split"]} for row in records])
    manifest = {
        "schema_version": "vfx_prefab_corpus.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_id": corpus_id,
        "source_count": len(manifests),
        "prefab_count": len(records),
        "record_count": len(records),
        "split_counts": dict(sorted(Counter(str(row["split"]) for row in records).items())),
        "delta": {"new_count": new_count, "unchanged_count": unchanged_count, "changed_count": changed, "removed_count": removed_count},
        "files": {"records": records_path.name, "failures": failures_path.name, "split_assignments": splits_path.name},
        "quality_gates": {
            "source_manifests_readable": True,
            "prefab_paths_present": all(bool(row["prefab_path"]) for row in records),
            "split_groups_disjoint": overlap_count == 0,
            "duplicate_source_keys": duplicate_count,
            "license_review_required_count": sum("license_review_required" in row["training_eligibility"]["excluded_reasons"] for row in records),
        },
        "training_policy": {
            "asset_copying": "not_performed",
            "local_reference_only_is_allowed_for_local_training": True,
            "not_visible_or_no_visual_evidence_is_not_positive_training": True,
            "source_structure_is_not_visual_quality": True,
            "source_summaries": source_summaries,
        },
        "status": "pass",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/vfx_prefab_corpus.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise ValueError(f"corpus manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "corpus_manifest.json", manifest)
    return {"corpus_manifest": manifest_path, "records": records_path, "failures": failures_path, "split_assignments": splits_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a large incremental VFX Prefab corpus index.")
    parser.add_argument("--input", type=Path, action="append", required=True, help="source directory or source_manifest.json; repeatable")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--previous-manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = build_corpus(args.input, args.output_dir, args.corpus_id, args.previous_manifest)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
