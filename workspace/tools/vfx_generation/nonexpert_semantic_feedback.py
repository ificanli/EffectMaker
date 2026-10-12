"""Reclassify non-expert active-review feedback as semantic-only supervision."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SEMANTIC_ACTIONS = {"AI判断正确"}
AESTHETIC_TASKS = {
    "aesthetic_judge", "core_readability_issue_detection", "layer_separation_issue_detection",
    "rhythm_issue_detection", "material_issue_detection", "style_error_detection",
    "quality_direction_supervision", "regression_evaluation", "model_promotion", "preference_training",
}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


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


def reclassify(review_root: Path, output_root: Path) -> dict[str, Path]:
    review_root, output_root = review_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"semantic feedback output already exists and is not empty: {output_root}")
    summary = _read_json(review_root / "review_summary.json")
    human_rows = _read_jsonl(review_root / "human_gold.jsonl")
    semantic_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    record_schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_training_layer_record.schema.json")
    validator = Draft202012Validator(record_schema)
    for row in human_rows:
        action = str((row.get("labels") or {}).get("decision") or "")
        if action not in SEMANTIC_ACTIONS:
            reason = "legacy_type_error_missing_corrected_function" if action == "特效类型错误" else "non_expert_aesthetic_feedback_not_trainable"
            exclusions.append({
                "record_id": row.get("record_id"),
                "sample_id": row.get("sample_id"),
                "prefab_path": (row.get("source") or {}).get("prefab_path"),
                "reason": reason,
                "original_action": action,
                "excluded_from": sorted(AESTHETIC_TASKS | {"human_gold", "semantic_supervision"}),
            })
            continue
        semantic = deepcopy(row)
        labels = semantic["labels"]
        labels["target_color_tags"] = []
        labels["observed_color_tags"] = []
        labels["quality_score"] = None
        labels["scores"] = {}
        labels["issues"] = []
        labels["decisions"] = [action]
        semantic["observations"]["human_scope"] = {
            "expertise": "non_expert",
            "accepted_dimensions": ["effect_function", "playability"],
            "excluded_dimensions": ["quality", "style", "core_readability", "layer_separation", "rhythm", "material", "composition"],
        }
        semantic["training"].update({
            "weight": 1.0,
            "eligible_tasks": ["effect_family_supervision", "pseudo_label_calibration"],
            "excluded_tasks": sorted(AESTHETIC_TASKS),
            "frozen": False,
            "expires_with_model_version": False,
        })
        semantic["limitations"] = sorted(set([*semantic.get("limitations", []), "non_expert_semantic_scope_only"]))
        errors = list(validator.iter_errors(semantic))
        if errors:
            raise ValueError(f"semantic human record schema error: {errors[0].message}")
        semantic_rows.append(semantic)
    semantic_path = _write_jsonl(output_root / "semantic_human_gold.jsonl", semantic_rows)
    exclusion_path = _write_jsonl(output_root / "excluded_nonexpert_aesthetic.jsonl", exclusions)
    manifest_path = _write_json(output_root / "manifest.json", {
        "schema_version": "vfx_nonexpert_semantic_feedback.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_batch": summary.get("batch_id"),
        "input_human_gold_count": len(human_rows),
        "semantic_human_gold_count": len(semantic_rows),
        "excluded_count": len(exclusions),
        "exclusion_reason_counts": {
            reason: sum(row["reason"] == reason for row in exclusions)
            for reason in sorted({row["reason"] for row in exclusions})
        },
        "accepted_human_scope": ["effect_function", "playability"],
        "aesthetic_teacher_source": "professional_vfx_materials_and_verified_unity_reproductions",
        "quality_gates": {
            "schema_errors": 0,
            "aesthetic_tasks_in_semantic_rows": sum(bool(set(row["training"]["eligible_tasks"]) & AESTHETIC_TASKS) for row in semantic_rows),
        },
        "status": "pass",
    })
    return {"manifest": manifest_path, "semantic_human_gold": semantic_path, "exclusions": exclusion_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reclassify non-expert active feedback as semantic-only supervision.")
    parser.add_argument("--review-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = reclassify(args.review_root, args.output_root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
