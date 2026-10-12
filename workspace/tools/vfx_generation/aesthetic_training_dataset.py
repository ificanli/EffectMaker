"""Assemble leakage-safe VFX aesthetic Judge and preference datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


JUDGE_MINIMUM = 32
PREFERENCE_MINIMUM = 20
SPLITS = ("train", "validation", "test")


class AestheticDatasetError(ValueError):
    """Raised when aesthetic records cannot be assembled safely."""


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AestheticDatasetError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise AestheticDatasetError(f"invalid JSONL {path}:{line_number}: {error}") from error
        if not isinstance(value, dict):
            raise AestheticDatasetError(f"JSON object expected: {path}:{line_number}")
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


def _split(group_id: str) -> str:
    bucket = int(hashlib.sha256(f"vfx_aesthetic_split.v1|{group_id}".encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def _norm_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").casefold()


def _group_id(record: dict[str, Any]) -> str:
    scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    prompt_id = str(scope.get("prompt_id") or "")
    family = str(scope.get("effect_family") or "unknown")
    if prompt_id:
        return f"prompt:{prompt_id}|family:{family}"
    prefab = _norm_path(provenance.get("prefab_path"))
    if prefab:
        return f"prefab:{prefab}"
    source = _norm_path(provenance.get("source_path"))
    return f"source:{source or record.get('record_id') or 'unknown'}"


def _group_keys(record: dict[str, Any]) -> list[str]:
    """Return every leakage key; records sharing any key must share one split."""
    scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    keys: list[str] = []
    prompt_id = str(scope.get("prompt_id") or "")
    family = str(scope.get("effect_family") or "unknown")
    if prompt_id:
        keys.append(f"prompt:{prompt_id}|family:{family}")
    prefab = _norm_path(provenance.get("prefab_path"))
    if prefab:
        keys.append(f"prefab:{prefab}")
    for field, prefix in (
        ("asset_content_sha256", "content"),
        ("source_group_id", "source_group"),
        ("material_group_id", "material_group"),
        ("shader_group_id", "shader_group"),
    ):
        value = str(provenance.get(field) or "")
        if value:
            keys.append(f"{prefix}:{value}")
    run_id = str(provenance.get("run_id") or "")
    if run_id:
        keys.append(f"run:{run_id}")
    source = _norm_path(provenance.get("source_path"))
    if not keys:
        keys.append(f"source:{source or record.get('record_id') or 'unknown'}")
    return sorted(set(keys))


def _candidate_id(record: dict[str, Any]) -> str:
    scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    candidate_ids = scope.get("candidate_ids") if isinstance(scope.get("candidate_ids"), list) else []
    return str(candidate_ids[0]) if candidate_ids else str(record.get("record_id") or "")


def _feature_key(record: dict[str, Any]) -> tuple[str, str | None]:
    candidate_id = _candidate_id(record)
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    return candidate_id, str(provenance.get("run_id") or "") or None


def _feature_candidate_ids(record: dict[str, Any]) -> list[str]:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    values = [_candidate_id(record), str(provenance.get("render_candidate_id") or "")]
    return list(dict.fromkeys(value for value in values if value))


def _load_features(paths: Iterable[Path]) -> tuple[dict[tuple[str, str | None], dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    exact: dict[tuple[str, str | None], dict[str, Any]] = {}
    by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"feature input does not exist: {path}")
        for row in _read_jsonl(path):
            candidate_id = str(row.get("candidate_id") or "")
            run_id = str(row.get("run_id") or "") or None
            features = row.get("features")
            if not candidate_id or not isinstance(features, dict):
                raise AestheticDatasetError(f"invalid feature row in {path}")
            key = (candidate_id, run_id)
            if key in exact:
                raise AestheticDatasetError(f"duplicate feature row: {candidate_id}/{run_id}")
            clean = {str(name): value for name, value in features.items() if isinstance(value, (str, int, float, bool)) and value is not None}
            normalized = {"candidate_id": candidate_id, "run_id": run_id, "features": clean, "source_path": path.as_posix()}
            exact[key] = normalized
            by_candidate[candidate_id].append(normalized)
    return exact, by_candidate


def _find_features(record: dict[str, Any], exact: dict[tuple[str, str | None], dict[str, Any]], by_candidate: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    run_id = _feature_key(record)[1]
    for candidate_id in _feature_candidate_ids(record):
        key = (candidate_id, run_id)
        if key in exact:
            return exact[key]
        candidates = by_candidate.get(candidate_id, [])
        if len(candidates) == 1:
            return candidates[0]
    return None


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _training_row(record: dict[str, Any], feature: dict[str, Any], split: str, group_id: str) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    return {
        "schema_version": "vfx_aesthetic_training_example.v1",
        "record_id": record["record_id"],
        "candidate_id": _candidate_id(record),
        "effect_family": scope.get("effect_family"),
        "style_family": scope.get("style_family"),
        "split": split,
        "group_id": group_id,
        "evaluation_group_id": str(record.get("provenance", {}).get("run_id") or group_id) if isinstance(record.get("provenance"), dict) else group_id,
        "label": payload,
        "features": feature["features"],
        "provenance": record["provenance"],
    }


def _preference_row(record: dict[str, Any], feature_a: dict[str, Any], feature_b: dict[str, Any], split: str, group_id: str) -> dict[str, Any]:
    payload = record["payload"]
    return {
        "schema_version": "vfx_aesthetic_preference_example.v1",
        "record_id": record["record_id"],
        "candidate_a": payload["candidate_a"],
        "candidate_b": payload["candidate_b"],
        "preference": payload["preference"],
        "reason_codes": payload["reason_codes"],
        "human_note": payload["human_note"],
        "split": split,
        "group_id": group_id,
        "evaluation_group_id": str(record.get("provenance", {}).get("run_id") or group_id) if isinstance(record.get("provenance"), dict) else group_id,
        "effect_family": record["scope"]["effect_family"],
        "style_family": record["scope"]["style_family"],
        "features_a": feature_a["features"],
        "features_b": feature_b["features"],
        "provenance": record["provenance"],
    }


def build_aesthetic_training_dataset(
    record_paths: Iterable[Path],
    feature_paths: Iterable[Path],
    technical_exclusion_paths: Iterable[Path],
    output_dir: Path,
    dataset_id: str,
    *,
    minimum_judge_examples: int = JUDGE_MINIMUM,
    minimum_preference_pairs: int = PREFERENCE_MINIMUM,
) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"aesthetic training dataset output already exists and is not empty: {output_dir}")
    record_paths = [Path(path).resolve() for path in record_paths]
    feature_paths = [Path(path).resolve() for path in feature_paths]
    technical_exclusion_paths = [Path(path).resolve() for path in technical_exclusion_paths]
    records: list[dict[str, Any]] = []
    for path in record_paths:
        if not path.is_file():
            raise FileNotFoundError(f"aesthetic record input does not exist: {path}")
        records.extend(_read_jsonl(path))
    if not records:
        raise AestheticDatasetError("no aesthetic records supplied")
    exact_features, candidate_features = _load_features(feature_paths)
    exclusions: list[dict[str, Any]] = []
    judge_rows: list[dict[str, Any]] = []
    preference_rows: list[dict[str, Any]] = []
    split_groups: dict[str, str] = {}
    exclusion_counts: Counter[str] = Counter()
    judge_candidates = 0
    preference_candidates = 0

    record_group_keys = [_group_keys(record) for record in records]
    union_find = _UnionFind(len(records))
    key_owner: dict[str, int] = {}
    for index, keys in enumerate(record_group_keys):
        for key in keys:
            owner = key_owner.setdefault(key, index)
            union_find.union(index, owner)
    component_keys: dict[int, set[str]] = defaultdict(set)
    for index, keys in enumerate(record_group_keys):
        component_keys[union_find.find(index)].update(keys)
    component_ids: dict[int, str] = {
        root: "group:" + hashlib.sha256("|".join(sorted(keys)).encode("utf-8")).hexdigest()[:20]
        for root, keys in component_keys.items()
    }
    record_group_ids = [component_ids[union_find.find(index)] for index in range(len(records))]
    record_splits = {group_id: _split(group_id) for group_id in set(record_group_ids)}
    split_assignments = [
        {"record_id": record.get("record_id"), "group_id": group_id, "split": record_splits[group_id], "group_keys": record_group_keys[index]}
        for index, (record, group_id) in enumerate(zip(records, record_group_ids))
    ]

    for index, record in enumerate(records):
        kind = record.get("record_kind")
        eligibility = record.get("training_eligibility") if isinstance(record.get("training_eligibility"), dict) else {}
        group_id = record_group_ids[index]
        split = record_splits[group_id]
        previous = split_groups.setdefault(group_id, split)
        if previous != split:
            raise AestheticDatasetError(f"split group assigned to multiple splits: {group_id}")
        if kind == "human_label" and eligibility.get("aesthetic_judge") is True:
            judge_candidates += 1
            feature = _find_features(record, exact_features, candidate_features)
            if feature is None:
                reason = "missing_feature_vector"
                exclusion_counts[reason] += 1
                exclusions.append({"record_id": record.get("record_id"), "record_kind": kind, "reason": reason, "group_id": group_id})
            else:
                judge_rows.append(_training_row(record, feature, split, group_id))
        elif kind == "preference_pair" and eligibility.get("preference_training") is True:
            preference_candidates += 1
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            if payload.get("preference") not in {"a", "b"} or payload.get("comparable") is not True:
                reason = "preference_not_comparable"
                exclusion_counts[reason] += 1
                exclusions.append({"record_id": record.get("record_id"), "record_kind": kind, "reason": reason, "group_id": group_id})
                continue
            candidate_a = str(payload.get("candidate_a") or "")
            candidate_b = str(payload.get("candidate_b") or "")
            feature_a = candidate_features.get(candidate_a, [])
            feature_b = candidate_features.get(candidate_b, [])
            if len(feature_a) != 1 or len(feature_b) != 1:
                reason = "missing_preference_feature_vector"
                exclusion_counts[reason] += 1
                exclusions.append({"record_id": record.get("record_id"), "record_kind": kind, "reason": reason, "group_id": group_id})
            else:
                preference_rows.append(_preference_row(record, feature_a[0], feature_b[0], split, group_id))
        else:
            reason = "non_training_record"
            exclusion_counts[reason] += 1
            exclusions.append({"record_id": record.get("record_id"), "record_kind": kind, "reason": reason, "group_id": group_id})

    for path in technical_exclusion_paths:
        if not path.is_file():
            raise FileNotFoundError(f"technical exclusion input does not exist: {path}")
        for row in _read_jsonl(path):
            exclusion_counts["technical_exclusion"] += 1
            exclusions.append({"record_id": row.get("record_id"), "record_kind": "technical_exclusion", "reason": "technical_exclusion", "source_path": path.as_posix()})

    split_counts = {
        "judge": dict(sorted(Counter(row["split"] for row in judge_rows).items())),
        "preference": dict(sorted(Counter(row["split"] for row in preference_rows).items())),
    }
    split_group_counts = dict(sorted(Counter(record_splits.values()).items()))
    judge_ready = len(judge_rows) >= minimum_judge_examples
    preference_ready = len(preference_rows) >= minimum_preference_pairs
    if not feature_paths and (judge_candidates or preference_candidates):
        gate_status = "blocked_no_feature_vectors"
        gate_reason = "feature vectors are required before Judge or preference training"
    elif not judge_rows and not preference_rows:
        gate_status = "no_eligible_examples"
        gate_reason = "no eligible aesthetic training record has a matched feature vector"
    elif not judge_ready or not preference_ready:
        gate_status = "blocked_insufficient_labels"
        gate_reason = f"need at least {minimum_judge_examples} Judge examples and {minimum_preference_pairs} preference pairs; found {len(judge_rows)} and {len(preference_rows)}"
    else:
        gate_status = "ready"
        gate_reason = "minimum Judge and preference training records are available"

    records_path = _write_jsonl(output_dir / "aesthetic_training_records.jsonl", records)
    feedback_path = _write_jsonl(output_dir / "aesthetic_feedback.jsonl", [record for record in records if record.get("record_kind") == "human_label"])
    preference_pairs_path = _write_jsonl(output_dir / "preference_pairs.jsonl", [record for record in records if record.get("record_kind") == "preference_pair"])
    judge_path = _write_jsonl(output_dir / "judge_training.jsonl", judge_rows)
    preference_path = _write_jsonl(output_dir / "preference_training.jsonl", preference_rows)
    exclusion_path = _write_jsonl(output_dir / "training_exclusions.jsonl", exclusions)
    assignment_path = _write_jsonl(output_dir / "split_assignments.jsonl", split_assignments)
    manifest = {
        "schema_version": "vfx_aesthetic_training_dataset.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_count": len(record_paths) + len(feature_paths) + len(technical_exclusion_paths),
        "record_count": len(records),
        "judge_candidate_count": judge_candidates,
        "judge_training_count": len(judge_rows),
        "preference_candidate_count": preference_candidates,
        "preference_training_count": len(preference_rows),
        "excluded_count": len(exclusions),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "split_counts": split_counts,
        "split_group_counts": split_group_counts,
        "training_gate": {
            "status": gate_status,
            "reason": gate_reason,
            "judge_ready": judge_ready,
            "preference_ready": preference_ready,
            "minimum_judge_examples": minimum_judge_examples,
            "minimum_preference_pairs": minimum_preference_pairs,
        },
        "files": {
            "records": records_path.name,
            "aesthetic_feedback": feedback_path.name,
            "preference_pairs": preference_pairs_path.name,
            "judge_training": judge_path.name,
            "preference_training": preference_path.name,
            "training_exclusions": exclusion_path.name,
            "split_assignments": assignment_path.name,
        },
        "policy": {
            "same_group_stays_in_one_split": True,
            "not_visible_is_not_aesthetic_training": True,
            "technical_exclusion_is_not_aesthetic_negative": True,
            "missing_features_are_not_silent": True,
            "course_prior_is_not_generation_success": True,
        },
        "status": "pass",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/aesthetic_training_dataset.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        raise AestheticDatasetError(f"aesthetic training manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "aesthetic_training_dataset_manifest.json", manifest)
    return {
        "manifest": manifest_path,
        "records": records_path,
        "aesthetic_feedback": feedback_path,
        "preference_pairs": preference_pairs_path,
        "judge_training": judge_path,
        "preference_training": preference_path,
        "exclusions": exclusion_path,
        "split_assignments": assignment_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble leakage-safe VFX aesthetic training data.")
    parser.add_argument("--aesthetic-record", type=Path, action="append", required=True)
    parser.add_argument("--feature", type=Path, action="append", default=[])
    parser.add_argument("--technical-exclusion", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--minimum-judge-examples", type=int, default=JUDGE_MINIMUM)
    parser.add_argument("--minimum-preference-pairs", type=int, default=PREFERENCE_MINIMUM)
    args = parser.parse_args(argv)
    try:
        paths = build_aesthetic_training_dataset(
            args.aesthetic_record,
            args.feature,
            args.technical_exclusion,
            args.output_dir,
            args.dataset_id,
            minimum_judge_examples=args.minimum_judge_examples,
            minimum_preference_pairs=args.minimum_preference_pairs,
        )
    except (AestheticDatasetError, FileNotFoundError, FileExistsError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
