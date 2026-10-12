"""Audit VFX aesthetic model coverage, leakage, and promotion readiness."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


class PromotionAuditError(ValueError):
    """Raised when promotion inputs cannot be audited safely."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PromotionAuditError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"promotion input does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise PromotionAuditError(f"JSON object expected: {path}:{line_number}")
        rows.append(value)
    return rows


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _coverage(rows: Iterable[dict[str, Any]]) -> tuple[Counter[str], Counter[str]]:
    families: Counter[str] = Counter()
    styles: Counter[str] = Counter()
    for row in rows:
        family = str(row.get("effect_family") or "unknown")
        style = str(row.get("style_family") or "unknown")
        if family != "unknown":
            families[family] += 1
        if style not in {"unknown", ""}:
            styles[style] += 1
    return families, styles


def _leakage(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    splits: dict[str, set[str]] = defaultdict(set)
    for row in assignments:
        group_id = str(row.get("group_id") or "")
        split = str(row.get("split") or "")
        if group_id and split:
            splits[group_id].add(split)
    multi = sorted(group_id for group_id, values in splits.items() if len(values) > 1)
    return {
        "status": "fail" if multi else "pass" if splits else "not_available",
        "group_count": len(splits),
        "multi_split_group_count": len(multi),
        "multi_split_groups": multi,
    }


def _model_status(model_path: Path | None, metrics_path: Path | None, model_card_path: Path | None) -> dict[str, Any]:
    if model_path is None:
        return {"status": "absent", "model_path": None, "metrics_path": None, "model_card_path": None, "final_visual_acceptance": False}
    metrics = _read_json(metrics_path) if metrics_path and metrics_path.is_file() else {}
    final = bool(metrics.get("final_visual_acceptance") is True)
    status = "candidate" if final and model_card_path and model_card_path.is_file() else "experimental"
    return {
        "status": status,
        "model_path": model_path.resolve().as_posix(),
        "metrics_path": metrics_path.resolve().as_posix() if metrics_path else None,
        "model_card_path": model_card_path.resolve().as_posix() if model_card_path else None,
        "final_visual_acceptance": final,
    }


def build_promotion_report(
    dataset_manifest_path: Path,
    output_path: Path,
    *,
    judge_model: Path | None = None,
    judge_metrics: Path | None = None,
    judge_model_card: Path | None = None,
    preference_model: Path | None = None,
    preference_metrics: Path | None = None,
    preference_model_card: Path | None = None,
    controller_model: Path | None = None,
    controller_metrics: Path | None = None,
    controller_model_card: Path | None = None,
    regression_set: Path | None = None,
    minimum_families: int = 2,
    minimum_styles: int = 2,
) -> Path:
    dataset_manifest_path = dataset_manifest_path.resolve()
    manifest = _read_json(dataset_manifest_path)
    base = dataset_manifest_path.parent
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    records_path = base / str(files.get("records") or "aesthetic_training_records.jsonl")
    judge_path = base / str(files.get("judge_training") or "judge_training.jsonl")
    preference_path = base / str(files.get("preference_training") or "preference_training.jsonl")
    assignments_path = base / str(files.get("split_assignments") or "split_assignments.jsonl")
    records = _read_jsonl(records_path)
    judge_rows = _read_jsonl(judge_path)
    preference_rows = _read_jsonl(preference_path)
    assignments = _read_jsonl(assignments_path)
    families, styles = _coverage(judge_rows)
    leakage = _leakage(assignments)
    model_status = {
        "judge": _model_status(judge_model, judge_metrics, judge_model_card),
        "preference_ranker": _model_status(preference_model, preference_metrics, preference_model_card),
        "controller": _model_status(controller_model, controller_metrics, controller_model_card),
    }
    reasons: list[str] = []
    if not judge_rows:
        reasons.append("no_judge_training_rows")
    if len(families) < minimum_families:
        reasons.append(f"need_{minimum_families}_effect_families_found_{len(families)}")
    if len(styles) < minimum_styles:
        reasons.append(f"need_{minimum_styles}_style_families_found_{len(styles)}")
    if leakage["status"] == "fail":
        reasons.append("split_leakage_detected")
    if model_status["judge"]["status"] == "absent":
        reasons.append("judge_model_absent")
    if model_status["preference_ranker"]["status"] == "absent":
        reasons.append("preference_ranker_absent")
    regression_status = "missing"
    if regression_set and regression_set.is_file():
        regression = _read_json(regression_set)
        regression_status = "pass" if regression.get("status") == "pass" else "fail"
        if regression_status == "fail":
            reasons.append("regression_set_failed")
    else:
        reasons.append("regression_set_missing")
    all_models_ready = all(model_status[name]["status"] in {"candidate", "promoted"} for name in ("judge", "preference_ranker"))
    if reasons:
        decision = "blocked"
    elif all_models_ready and regression_status == "pass":
        decision = "candidate"
    else:
        decision = "experimental"
    report = {
        "schema_version": "vfx_aesthetic_promotion_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_manifest": dataset_manifest_path.as_posix(),
        "data_coverage": {
            "judge_training_count": len(judge_rows),
            "preference_training_count": len(preference_rows),
            "effect_family_counts": dict(sorted(families.items())),
            "style_family_counts": dict(sorted(styles.items())),
        },
        "leakage_audit": leakage,
        "model_status": model_status,
        "promotion": {
            "decision": decision,
            "reasons": sorted(set(reasons)),
            "minimum_families": minimum_families,
            "minimum_styles": minimum_styles,
            "regression_set_status": regression_status,
        },
        "status": "pass",
    }
    schema_path = Path(__file__).parents[3] / "workspace/data/vfx_generation/schemas/vfx_aesthetic_promotion_report.schema.json"
    errors = sorted(Draft202012Validator(_read_json(schema_path)).iter_errors(report), key=lambda error: list(error.path))
    if errors:
        raise PromotionAuditError(f"promotion report schema error: {errors[0].message}")
    return _write_json(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit VFX aesthetic model promotion readiness.")
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model", type=Path)
    parser.add_argument("--judge-metrics", type=Path)
    parser.add_argument("--judge-model-card", type=Path)
    parser.add_argument("--preference-model", type=Path)
    parser.add_argument("--preference-metrics", type=Path)
    parser.add_argument("--preference-model-card", type=Path)
    parser.add_argument("--controller-model", type=Path)
    parser.add_argument("--controller-metrics", type=Path)
    parser.add_argument("--controller-model-card", type=Path)
    parser.add_argument("--regression-set", type=Path)
    parser.add_argument("--minimum-families", type=int, default=2)
    parser.add_argument("--minimum-styles", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        path = build_promotion_report(
            args.dataset_manifest,
            args.output,
            judge_model=args.judge_model,
            judge_metrics=args.judge_metrics,
            judge_model_card=args.judge_model_card,
            preference_model=args.preference_model,
            preference_metrics=args.preference_metrics,
            preference_model_card=args.preference_model_card,
            controller_model=args.controller_model,
            controller_metrics=args.controller_metrics,
            controller_model_card=args.controller_model_card,
            regression_set=args.regression_set,
            minimum_families=args.minimum_families,
            minimum_styles=args.minimum_styles,
        )
    except (PromotionAuditError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "path": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
