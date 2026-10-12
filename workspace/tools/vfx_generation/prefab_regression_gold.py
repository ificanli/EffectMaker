"""Freeze Capture v2 human labels and export cluster-isolated training views."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


CAPTURE_PIPELINE = "play_mode_runtime_isolated_multiview.v2"
MANIFEST_SCHEMA = "vfx_prefab_regression_gold_manifest.v1"


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _normalize_prefab(value: Any) -> str:
    return str(value or "").replace("\\", "/").lower()


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        _read_json(_repo_root() / "workspace/data/vfx_generation/schemas" / name),
        format_checker=FormatChecker(),
    )


def _schema_errors(validator: Draft202012Validator, records: Iterable[dict[str, Any]]) -> list[str]:
    errors = []
    for record in records:
        for error in validator.iter_errors(record):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{record.get('record_id', 'unknown')}:{location}:{error.message}")
    return errors


def _capture_v2_ready(record: dict[str, Any]) -> bool:
    value = record.get("evidence", {}).get("capture_manifest_path")
    if record.get("tier") != "human_gold" or record.get("status") != "ready" or not value:
        return False
    try:
        manifest = _read_json(_resolve(str(value)))
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return False
    return manifest.get("capture_pipeline_version") == CAPTURE_PIPELINE and manifest.get("image_sequence_training_eligible") is True


def _freeze_record(record: dict[str, Any], cluster_id: str, freeze_id: str, created_at: str) -> dict[str, Any]:
    frozen = deepcopy(record)
    parent_record_id = str(record["record_id"])
    frozen["record_id"] = "regression_" + hashlib.sha256(f"{freeze_id}|{record['sample_id']}|{parent_record_id}".encode("utf-8")).hexdigest()[:20]
    frozen["tier"] = "regression_gold"
    frozen["grouping"]["cluster_id"] = cluster_id
    frozen["evidence"]["parent_record_ids"] = sorted(set([*frozen["evidence"].get("parent_record_ids", []), parent_record_id]))
    frozen["observations"] = {**frozen.get("observations", {}), "regression_freeze": {"freeze_id": freeze_id, "source_human_record_id": parent_record_id}}
    frozen["label_provenance"] = {
        "label_source": "regression_frozen",
        "confidence": 1.0,
        "model_version": None,
        "reviewer": record["label_provenance"].get("reviewer") or "local_human",
        "parent_human_record_id": parent_record_id,
        "distance": None,
        "created_at": created_at,
    }
    frozen["training"] = {
        "weight": 0.0,
        "eligible_tasks": [],
        "excluded_tasks": [
            "all_training", "hyperparameter_selection", "model_promotion_training", "preference_training",
            "pseudo_label_propagation", "threshold_selection",
        ],
        "split": "regression",
        "frozen": True,
        "expires_with_model_version": False,
    }
    frozen["status"] = "frozen"
    frozen["limitations"] = sorted(set(frozen.get("limitations", [])))
    return frozen


def freeze_regression_gold(
    dataset_root: Path,
    active_root: Path,
    output_root: Path,
    freeze_id: str,
    *,
    target_size: int = 32,
    minimum_recommended_size: int = 24,
    judge_training_path: Path | None = None,
) -> dict[str, Path]:
    dataset_root, active_root, output_root = dataset_root.resolve(), active_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"regression output already exists and is not empty: {output_root}")
    if target_size < 1 or minimum_recommended_size < 1:
        raise ValueError("regression target sizes must be positive")
    dataset_manifest = _read_json(dataset_root / "dataset_manifest.json")
    dataset_records = _read_jsonl(dataset_root / "records.jsonl")
    routed_records = _read_jsonl(active_root / "routed_records.jsonl")
    assignments = _read_jsonl(active_root / "cluster_assignments.jsonl")
    assignment_by_sample = {str(row["sample_id"]): str(row["cluster_id"]) for row in assignments}

    eligible_by_prefab: dict[str, dict[str, Any]] = {}
    for record in dataset_records:
        if not _capture_v2_ready(record) or record["sample_id"] not in assignment_by_sample:
            continue
        prefab_key = _normalize_prefab(record["source"].get("prefab_path"))
        if prefab_key:
            eligible_by_prefab[prefab_key] = record
    eligible = sorted(
        eligible_by_prefab.values(),
        key=lambda row: (
            str(row["grouping"].get("source_group") or ""),
            str((row.get("labels", {}).get("observed_element_tags") or ["unknown"])[0]),
            float(row.get("labels", {}).get("quality_score") or 0.0),
            str(row["sample_id"]),
        ),
    )
    selected = eligible[:target_size]
    created_at = _now()
    regression_clusters = {assignment_by_sample[str(row["sample_id"])] for row in selected}
    regression_sample_ids = {str(row["sample_id"]) for row in selected}
    frozen = [_freeze_record(row, assignment_by_sample[str(row["sample_id"])], freeze_id, created_at) for row in selected]

    heldout_prefabs = {
        _normalize_prefab(row["source"].get("prefab_path"))
        for row in routed_records
        if str(row["grouping"].get("cluster_id")) in regression_clusters and row["source"].get("prefab_path")
    }
    training_records = [row for row in routed_records if str(row["grouping"].get("cluster_id")) not in regression_clusters]
    pseudo_propagation = [row for row in training_records if row["tier"] in {"human_gold", "ai_pseudo_label"}]

    judge_input: list[dict[str, Any]] = []
    judge_filtered: list[dict[str, Any]] = []
    judge_regression: list[dict[str, Any]] = []
    direct_regression_prefabs = {_normalize_prefab(row["source"].get("prefab_path")) for row in selected}
    judge_output_path: Path | None = None
    judge_regression_path: Path | None = None
    if judge_training_path is not None:
        judge_training_path = judge_training_path.resolve()
        judge_input = _read_jsonl(judge_training_path)
        judge_filtered = [row for row in judge_input if _normalize_prefab((row.get("provenance") or {}).get("prefab_path")) not in heldout_prefabs]
        judge_regression = [row for row in judge_input if _normalize_prefab((row.get("provenance") or {}).get("prefab_path")) in direct_regression_prefabs]
        judge_output_path = output_root / "judge_training_excluding_regression.jsonl"
        judge_regression_path = output_root / "judge_regression_rows.jsonl"
        _write_jsonl(judge_output_path, judge_filtered)
        _write_jsonl(judge_regression_path, judge_regression)

    record_validator = _validator("prefab_training_layer_record.schema.json")
    errors = _schema_errors(record_validator, frozen)
    regression_path = _write_jsonl(output_root / "regression_gold.jsonl", frozen)
    training_path = _write_jsonl(output_root / "training_records.jsonl", training_records)
    pseudo_path = _write_jsonl(output_root / "pseudo_propagation_records.jsonl", pseudo_propagation)
    training_samples = {str(row["sample_id"]) for row in training_records}
    training_clusters = {str(row["grouping"].get("cluster_id")) for row in training_records}
    pseudo_prefabs = {_normalize_prefab(row["source"].get("prefab_path")) for row in pseudo_propagation}
    filtered_judge_prefabs = {_normalize_prefab((row.get("provenance") or {}).get("prefab_path")) for row in judge_filtered}
    direct_overlap = sum(_normalize_prefab((row.get("provenance") or {}).get("prefab_path")) in direct_regression_prefabs for row in judge_input)
    cluster_overlap = sum(_normalize_prefab((row.get("provenance") or {}).get("prefab_path")) in heldout_prefabs for row in judge_input)
    gates = {
        "schema_errors": len(errors),
        "regression_records_trainable": sum(row["training"]["weight"] > 0 or bool(row["training"]["eligible_tasks"]) for row in frozen),
        "regression_samples_in_training": len(regression_sample_ids & training_samples),
        "regression_clusters_in_training": len(regression_clusters & training_clusters),
        "heldout_prefabs_in_pseudo_propagation": len(heldout_prefabs & pseudo_prefabs),
        "regression_prefabs_in_filtered_judge": len(heldout_prefabs & filtered_judge_prefabs),
    }
    if any(gates.values()):
        raise ValueError(f"regression contamination gate failed: {gates}; schema errors: {errors[:1]}")
    status = "no_eligible_samples" if not frozen else "underfilled" if len(frozen) < minimum_recommended_size else "pass"
    files = {
        "regression_gold": _portable(regression_path),
        "training_records": _portable(training_path),
        "pseudo_propagation_records": _portable(pseudo_path),
        "judge_training_excluding_regression": _portable(judge_output_path) if judge_output_path is not None else None,
        "judge_regression_rows": _portable(judge_regression_path) if judge_regression_path is not None else None,
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "created_at": created_at,
        "freeze_id": freeze_id,
        "source_dataset": _portable(dataset_root / "dataset_manifest.json"),
        "source_assignments": _portable(active_root / "cluster_assignments.jsonl"),
        "target_size": target_size,
        "minimum_recommended_size": minimum_recommended_size,
        "eligible_count": len(eligible),
        "frozen_count": len(frozen),
        "status": status,
        "regression_sample_ids": sorted(regression_sample_ids),
        "regression_cluster_ids": sorted(regression_clusters),
        "held_out_prefab_paths": sorted(heldout_prefabs),
        "historical_training_audit": {
            "input_path": _portable(judge_training_path) if judge_training_path is not None else None,
            "input_count": len(judge_input),
            "direct_regression_overlap_count": direct_overlap,
            "heldout_cluster_overlap_count": cluster_overlap,
            "filtered_count": len(judge_filtered),
            "affected_existing_models_must_not_use_this_regression_set": cluster_overlap > 0,
        },
        "files": files,
        "quality_gates": gates,
    }
    manifest_validator = _validator("prefab_regression_gold_manifest.schema.json")
    manifest_errors = list(manifest_validator.iter_errors(manifest))
    if manifest_errors:
        raise ValueError(f"regression manifest schema error: {manifest_errors[0].message}")
    manifest_path = _write_json(output_root / "regression_manifest.json", manifest)
    return {
        "manifest": manifest_path,
        "regression_gold": regression_path,
        "training_records": training_path,
        "pseudo_propagation_records": pseudo_path,
        "judge_training_excluding_regression": judge_output_path,
        "judge_regression_rows": judge_regression_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze Capture v2 human gold into a cluster-isolated regression set.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--active-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--freeze-id", required=True)
    parser.add_argument("--target-size", type=int, default=32)
    parser.add_argument("--minimum-recommended-size", type=int, default=24)
    parser.add_argument("--judge-training", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = freeze_regression_gold(
            args.dataset_root,
            args.active_root,
            args.output_root,
            args.freeze_id,
            target_size=args.target_size,
            minimum_recommended_size=args.minimum_recommended_size,
            judge_training_path=args.judge_training,
        )
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() if path is not None else None for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
