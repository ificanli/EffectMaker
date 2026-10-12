"""Assemble tutorial procedures into retrieval constraints and gated Planner SFT."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .procedure_spec import load_procedure_library


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


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


def _exclusion_reasons(spec: dict[str, Any]) -> list[str]:
    reasons = []
    if any(step.get("evidence_status") == "inferred" for step in spec["steps"]):
        reasons.append("inferred_steps_require_separate_validation")
    if spec["source"]["source_status"] != "verified":
        reasons.append("source_procedure_not_verified")
    if spec["validation"]["target_project_reproduction_status"] != "verified":
        reasons.append("target_project_reproduction_not_verified")
    if spec["validation"]["visual_quality_status"] != "professionally_verified":
        reasons.append("professional_visual_acceptance_missing")
    if not spec["training_eligibility"]["controller_sft"]:
        reasons.append("procedure_not_approved_for_controller_sft")
    return reasons


def build_procedure_training_dataset(procedure_root: Path, output_root: Path, dataset_id: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"procedure dataset output already exists and is not empty: {output_root}")
    procedures = load_procedure_library(procedure_root)
    ids = [row["procedure_id"] for row in procedures]
    duplicates = len(ids) - len(set(ids))
    index_rows = []
    constraints = []
    sft_rows = []
    exclusions = []
    family_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    target_verified_count = 0
    for spec in procedures:
        for family in spec["applicability"]["effect_families"]:
            family_counts[family] += 1
        status_counts[spec["source"]["source_status"]] += 1
        target_verified = spec["validation"]["target_project_reproduction_status"] == "verified"
        target_verified_count += int(target_verified)
        index_rows.append({
            "procedure_id": spec["procedure_id"],
            "title": spec["title"],
            "effect_families": spec["applicability"]["effect_families"],
            "style_families": spec["applicability"]["style_families"],
            "source_path": spec["source"]["source_path"],
            "source_status": spec["source"]["source_status"],
            "target_project_reproduction_status": spec["validation"]["target_project_reproduction_status"],
            "visual_quality_status": spec["validation"]["visual_quality_status"],
        })
        if spec["training_eligibility"]["procedure_retrieval"] and spec["training_eligibility"]["planner_constraint"]:
            constraints.append({
                "schema_version": "vfx_procedure_constraint.v1",
                "procedure_id": spec["procedure_id"],
                "input": {
                    "title": spec["title"],
                    "effect_families": spec["applicability"]["effect_families"],
                    "effect_types": spec["applicability"]["effect_types"],
                    "style_families": spec["applicability"]["style_families"],
                    "elements": spec["applicability"]["elements"],
                },
                "target": {
                    "steps": spec["steps"],
                    "output_contract": spec["output_contract"],
                },
                "evidence": {
                    "source": spec["source"],
                    "validation": spec["validation"],
                },
                "training_eligibility": {
                    "retrieval": True,
                    "planner_constraint": True,
                    "controller_sft": False,
                    "positive_generation_supervision": False,
                },
            })
        reasons = _exclusion_reasons(spec)
        if not reasons:
            sft_rows.append({
                "schema_version": "vfx_procedure_planner_sft.v1",
                "procedure_id": spec["procedure_id"],
                "input": {
                    "effect_families": spec["applicability"]["effect_families"],
                    "effect_types": spec["applicability"]["effect_types"],
                    "style_families": spec["applicability"]["style_families"],
                    "elements": spec["applicability"]["elements"],
                    "prerequisites": spec["prerequisites"],
                },
                "target": {"steps": spec["steps"], "output_contract": spec["output_contract"]},
                "provenance": spec["source"],
            })
        else:
            exclusions.append({
                "procedure_id": spec["procedure_id"],
                "source_path": spec["source"]["source_path"],
                "excluded_from": ["controller_sft", "positive_generation_supervision"],
                "reasons": reasons,
            })
    index_path = _write_jsonl(output_root / "procedure_index.jsonl", index_rows)
    constraints_path = _write_jsonl(output_root / "planner_constraints.jsonl", constraints)
    sft_path = _write_jsonl(output_root / "controller_sft.jsonl", sft_rows)
    exclusions_path = _write_jsonl(output_root / "exclusions.jsonl", exclusions)
    invalid_step_orders = sum(
        [int(step["order"]) for step in spec["steps"]] != sorted(int(step["order"]) for step in spec["steps"])
        for spec in procedures
    )
    unverified_positive = sum(
        bool(_exclusion_reasons(spec)) and spec["training_eligibility"]["positive_generation_supervision"]
        for spec in procedures
    )
    manifest = {
        "schema_version": "vfx_procedure_training_dataset.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "procedure_count": len(procedures),
        "family_counts": dict(sorted(family_counts.items())),
        "source_status_counts": dict(sorted(status_counts.items())),
        "planner_constraint_count": len(constraints),
        "target_verified_count": target_verified_count,
        "controller_sft_count": len(sft_rows),
        "files": {
            "procedure_index": _portable(index_path),
            "planner_constraints": _portable(constraints_path),
            "controller_sft": _portable(sft_path),
            "exclusions": _portable(exclusions_path),
        },
        "quality_gates": {
            "schema_errors": 0,
            "duplicate_procedure_ids": duplicates,
            "invalid_step_orders": invalid_step_orders,
            "unverified_positive_supervision_count": unverified_positive,
        },
        "policy": {
            "tutorials_are_causal_supervision": True,
            "prefabs_are_not_the_only_training_source": True,
            "target_unity_reproduction_required_for_sft": True,
            "professional_visual_acceptance_required_for_positive_generation": True,
        },
        "status": "ready_for_planner_training" if sft_rows else "ready_for_retrieval_only" if constraints else "empty",
    }
    schema = json.loads((_repo_root() / "workspace/data/vfx_generation/schemas/procedure_training_dataset.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"procedure training dataset schema error at {location}: {errors[0].message}")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {"manifest": manifest_path, "procedure_index": index_path, "planner_constraints": constraints_path, "controller_sft": sft_path, "exclusions": exclusions_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build tutorial procedure retrieval and Planner training datasets.")
    parser.add_argument("--procedure-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_procedure_training_dataset(args.procedure_root, args.output_root, args.dataset_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
