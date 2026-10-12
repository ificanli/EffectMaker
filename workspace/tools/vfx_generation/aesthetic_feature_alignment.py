"""Align canonical human aesthetic labels with real Unity feature vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from workspace.tools.vfx_training_features import FeatureExtractionError, aggregate_image_features


class FeatureAlignmentError(ValueError):
    """Raised when feature alignment would invent or silently drop evidence."""


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FeatureAlignmentError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"alignment input does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise FeatureAlignmentError(f"JSON object expected: {path}:{line_number}")
        rows.append(value)
    return rows


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _resolve(value: str, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    repo_candidate = (_repo_root() / path).resolve()
    if repo_candidate.is_file():
        return repo_candidate
    return (base / path).resolve()


def _record_ids(record: dict[str, Any]) -> list[str]:
    scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    candidate_ids = scope.get("candidate_ids") if isinstance(scope.get("candidate_ids"), list) else []
    return list(dict.fromkeys([str(candidate_ids[0]) if candidate_ids else "", str(provenance.get("render_candidate_id") or "")]))


def _run_id(record: dict[str, Any]) -> str:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    explicit = str(provenance.get("run_id") or "")
    if explicit:
        return explicit
    for frame in provenance.get("frame_paths", []) if isinstance(provenance.get("frame_paths"), list) else []:
        parts = str(frame).replace("\\", "/").split("/")
        if "runs" in parts:
            index = parts.index("runs")
            if index + 1 < len(parts):
                return parts[index + 1]
    return "unknown"


def _load_existing_features(paths: Iterable[Path]) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    exact: dict[tuple[str, str], dict[str, Any]] = {}
    by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths:
        for row in _read_jsonl(path.resolve()):
            candidate_id = str(row.get("candidate_id") or "")
            run_id = str(row.get("run_id") or "")
            features = row.get("features")
            if not candidate_id or not run_id or not isinstance(features, dict):
                raise FeatureAlignmentError(f"invalid existing feature row: {path}")
            key = (candidate_id, run_id)
            if key in exact:
                raise FeatureAlignmentError(f"duplicate existing feature row: {run_id}/{candidate_id}")
            normalized = {"candidate_id": candidate_id, "run_id": run_id, "features": features, "source_path": path.resolve().as_posix()}
            exact[key] = normalized
            by_candidate[candidate_id].append(normalized)
    return exact, by_candidate


def _find_existing(record: dict[str, Any], exact: dict[tuple[str, str], dict[str, Any]], by_candidate: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    run_id = _run_id(record)
    for candidate_id in _record_ids(record):
        if not candidate_id:
            continue
        direct = exact.get((candidate_id, run_id))
        if direct is not None:
            return direct
        matches = by_candidate.get(candidate_id, [])
        if len(matches) == 1:
            return matches[0]
    return None


def _direct_image_features(record: dict[str, Any], source_path: Path) -> dict[str, float]:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    frame_values = provenance.get("frame_paths") if isinstance(provenance.get("frame_paths"), list) else []
    frame_paths = [_resolve(str(value), _repo_root()) for value in frame_values if str(value)]
    if not frame_paths or any(not path.is_file() for path in frame_paths):
        raise FeatureAlignmentError(f"missing aligned frame evidence for {record.get('record_id')}")
    try:
        return aggregate_image_features(frame_paths, [None] * len(frame_paths))
    except (FeatureExtractionError, OSError) as error:
        raise FeatureAlignmentError(f"could not extract image features for {record.get('record_id')}: {error}") from error


def build_feature_alignment(record_path: Path, existing_feature_paths: Iterable[Path], output_dir: Path, dataset_id: str) -> dict[str, Path]:
    record_path = record_path.resolve()
    output_dir = output_dir.resolve()
    existing_feature_paths = list(existing_feature_paths)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"alignment output already exists and is not empty: {output_dir}")
    records = _read_jsonl(record_path)
    exact, by_candidate = _load_existing_features(existing_feature_paths)
    judge_records = [row for row in records if row.get("record_kind") == "human_label" and (row.get("training_eligibility") or {}).get("aesthetic_judge") is True]
    aligned: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    exclusion_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    coverage: Counter[str] = Counter()
    seen_candidates: set[str] = set()
    for record in judge_records:
        candidate_ids = _record_ids(record)
        canonical_candidate = candidate_ids[0] if candidate_ids else str(record.get("record_id") or "")
        if canonical_candidate in seen_candidates:
            raise FeatureAlignmentError(f"duplicate aligned aesthetic candidate: {canonical_candidate}")
        seen_candidates.add(canonical_candidate)
        run_id = _run_id(record)
        existing = _find_existing(record, exact, by_candidate)
        if existing is not None:
            features = dict(existing["features"])
            feature_source = "existing_run_feature_matrix"
            source_counts["existing_run_feature_matrix"] += 1
        else:
            try:
                features = _direct_image_features(record, record_path)
            except FeatureAlignmentError as error:
                reason = "missing_or_unreadable_frame_features"
                exclusion_counts[reason] += 1
                exclusions.append({"record_id": record.get("record_id"), "candidate_id": canonical_candidate, "run_id": run_id, "reason": reason, "detail": str(error)})
                continue
            feature_source = "direct_record_frames"
            source_counts["direct_record_frames"] += 1
        aligned.append({
            "schema_version": "vfx_aesthetic_aligned_feature.v1",
            "record_id": record.get("record_id"),
            "run_id": run_id,
            "candidate_id": canonical_candidate,
            "features": features,
            "feature_source": feature_source,
            "provenance": record.get("provenance"),
        })
        coverage[run_id] += 1
    if not judge_records:
        exclusion_counts["no_judge_candidates"] += 1
    feature_path = _write_jsonl(output_dir / "candidate_features.jsonl", aligned)
    exclusion_path = _write_jsonl(output_dir / "alignment_exclusions.jsonl", exclusions)
    manifest = {
        "schema_version": "vfx_aesthetic_feature_alignment.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "input_record_count": len(records),
        "judge_candidate_count": len(judge_records),
        "aligned_count": len(aligned),
        "excluded_count": len(exclusions),
        "existing_feature_match_count": source_counts.get("existing_run_feature_matrix", 0),
        "direct_image_feature_count": source_counts.get("direct_record_frames", 0),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "coverage_by_run": dict(sorted(coverage.items())),
        "files": {"candidate_features": feature_path.name, "alignment_exclusions": exclusion_path.name},
        "status": "pass",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/aesthetic_feature_alignment.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        raise FeatureAlignmentError(f"feature alignment manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "feature_alignment_manifest.json", manifest)
    return {"manifest": manifest_path, "features": feature_path, "exclusions": exclusion_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Align human aesthetic labels with real Unity feature vectors.")
    parser.add_argument("--judge-records", type=Path, required=True)
    parser.add_argument("--existing-feature", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_feature_alignment(args.judge_records, args.existing_feature, args.output_dir, args.dataset_id)
    except (FeatureAlignmentError, FileNotFoundError, FileExistsError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
