"""Validate and retrieve tutorial procedures for VFX proposal planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


TARGET_UNITY_VERSION = "2022.3.16f1c1"
TARGET_RENDER_PIPELINE = "URP 14.0.9"


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _schema() -> dict[str, Any]:
    return json.loads((_repo_root() / "workspace/data/vfx_generation/schemas/procedure_spec.schema.json").read_text(encoding="utf-8"))


def validate_procedure_spec(spec: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(_schema()).iter_errors(spec), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"ProcedureSpec schema error at {location}: {errors[0].message}")
    orders = [int(step["order"]) for step in spec["steps"]]
    if orders != sorted(orders) or len(orders) != len(set(orders)):
        raise ValueError("ProcedureSpec steps must have unique ascending order values")
    step_ids = [str(step["step_id"]) for step in spec["steps"]]
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("ProcedureSpec step ids must be unique")


def load_procedure_library(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"procedure library does not exist: {root}")
    specs = []
    for path in sorted(root.rglob("procedure_spec.json"), key=lambda value: value.as_posix().casefold()):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"ProcedureSpec JSON object expected: {path}")
        validate_procedure_spec(value)
        specs.append(value)
    return specs


def retrieve_procedures(
    procedures: Iterable[dict[str, Any]],
    *,
    effect_family: str,
    style_family: str,
) -> list[dict[str, Any]]:
    matches = []
    for procedure in procedures:
        applicability = procedure["applicability"]
        if effect_family not in applicability["effect_families"]:
            continue
        styles = set(applicability.get("style_families") or [])
        style_score = 2 if style_family in styles else 1 if "unspecified" in styles or style_family == "unspecified" else 0
        if style_score == 0:
            continue
        source_score = {"verified": 3, "partially_verified": 2, "unverified": 1}[procedure["source"]["source_status"]]
        target_score = {"verified": 3, "partial": 2, "pending": 1}[procedure["validation"]["target_project_reproduction_status"]]
        matches.append((source_score, target_score, style_score, procedure["procedure_id"], procedure))
    matches.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))
    return [row[-1] for row in matches]


def build_procedure_context(
    procedures: Iterable[dict[str, Any]],
    *,
    effect_family: str,
    style_family: str,
    target_unity_version: str = TARGET_UNITY_VERSION,
    target_render_pipeline: str = TARGET_RENDER_PIPELINE,
) -> dict[str, Any]:
    matches = retrieve_procedures(procedures, effect_family=effect_family, style_family=style_family)
    verified = []
    applied_steps = []
    hypothesis_steps = []
    timing = []
    for procedure in matches:
        validation = procedure["validation"]
        prerequisites = procedure["prerequisites"]
        if (
            validation["target_project_reproduction_status"] == "verified"
            and target_unity_version in prerequisites["unity_versions"]
            and target_render_pipeline in prerequisites["render_pipelines"]
        ):
            verified.append(procedure["procedure_id"])
        if procedure["training_eligibility"]["planner_constraint"]:
            applied_steps.extend(f"{procedure['procedure_id']}:{step['step_id']}" for step in procedure["steps"] if step["evidence_status"] != "inferred")
            hypothesis_steps.extend(f"{procedure['procedure_id']}:{step['step_id']}" for step in procedure["steps"] if step["evidence_status"] == "inferred")
            timing.extend(procedure["output_contract"]["timing_relationships"])
    status = "verified" if verified else "candidate" if matches else "missing"
    return {
        "required": True,
        "matched_procedure_ids": [row["procedure_id"] for row in matches],
        "target_verified_procedure_ids": verified,
        "applied_step_ids": sorted(set(applied_steps)),
        "hypothesis_step_ids": sorted(set(hypothesis_steps)),
        "timing_relationships": sorted(set(timing)),
        "status": status,
    }


def steps_for_role(procedures: Iterable[dict[str, Any]], role: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows = []
    for procedure in procedures:
        if not procedure["training_eligibility"]["planner_constraint"]:
            continue
        for step in procedure["steps"]:
            if step["target_role"] == role and step["evidence_status"] != "inferred":
                rows.append((procedure, step))
    rows.sort(key=lambda row: (row[0]["procedure_id"], int(row[1]["order"]), row[1]["step_id"]))
    return rows
