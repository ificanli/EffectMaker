"""Adapt canonical aesthetic preference records to the existing pairwise ranker."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from workspace.tools.vfx_preference_ranker import rank_candidates, train_pairwise_ranker


class AestheticPreferenceError(ValueError):
    """Raised when preference records cannot be used safely."""


class AestheticPreferenceNotReady(AestheticPreferenceError):
    """Raised when pairwise labels do not meet the training gate."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AestheticPreferenceError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"preference input does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise AestheticPreferenceError(f"JSON object expected: {path}:{line_number}")
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


def _run_id(row: dict[str, Any]) -> str:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    return str(provenance.get("run_id") or row.get("group_id") or "")


def _eligible(row: dict[str, Any]) -> tuple[bool, str | None]:
    if row.get("schema_version") != "vfx_aesthetic_preference_example.v1":
        return False, "unsupported_preference_schema"
    if row.get("split") not in {"train", "validation", "test"}:
        return False, "missing_split"
    if row.get("preference") not in {"a", "b"}:
        return False, "preference_not_comparable"
    if not isinstance(row.get("features_a"), dict) or not isinstance(row.get("features_b"), dict):
        return False, "missing_preference_feature_vector"
    if not str(row.get("candidate_a") or "") or not str(row.get("candidate_b") or ""):
        return False, "missing_candidate_id"
    if row["candidate_a"] == row["candidate_b"]:
        return False, "same_candidate_pair"
    if not _run_id(row):
        return False, "missing_run_group"
    return True, None


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return _read_jsonl(path.resolve())


def build_preflight(
    preference_path: Path,
    *,
    minimum_comparisons: int = 20,
    minimum_candidates: int = 8,
    minimum_runs: int = 2,
) -> dict[str, Any]:
    rows = _load_rows(preference_path)
    reasons: Counter[str] = Counter()
    eligible: list[dict[str, Any]] = []
    for row in rows:
        valid, reason = _eligible(row)
        if not valid:
            reasons[str(reason)] += 1
            continue
        if row["split"] != "train":
            reasons["non_train_split_not_used_for_fit"] += 1
            continue
        eligible.append(row)
    candidates = {str(value) for row in eligible for value in (row["candidate_a"], row["candidate_b"])}
    runs = {_run_id(row) for row in eligible}
    comparisons = len(eligible)
    threshold_reasons: list[str] = []
    if comparisons < minimum_comparisons:
        threshold_reasons.append(f"need {minimum_comparisons} comparisons; found {comparisons}")
    if len(candidates) < minimum_candidates:
        threshold_reasons.append(f"need {minimum_candidates} candidates; found {len(candidates)}")
    if len(runs) < minimum_runs:
        threshold_reasons.append(f"need {minimum_runs} runs; found {len(runs)}")
    all_reasons = [*threshold_reasons, *[f"{key}: {value}" for key, value in sorted(reasons.items())]]
    if not rows or not eligible:
        status = "no_eligible_examples"
        reason = "preference_training.jsonl has no comparable train-split pairs with both feature vectors"
    elif all_reasons and threshold_reasons:
        status = "blocked_insufficient_labels"
        reason = "; ".join(all_reasons)
    else:
        status = "ready"
        reason = "pairwise preference labels meet the training gate"
    return {
        "schema_version": "vfx_aesthetic_preference_preflight.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preference_path": preference_path.resolve().as_posix(),
        "row_count": len(rows),
        "train_pair_count": comparisons,
        "candidate_count": len(candidates),
        "run_count": len(runs),
        "ignored_counts": dict(sorted(reasons.items())),
        "minimum_comparisons": minimum_comparisons,
        "minimum_candidates": minimum_candidates,
        "minimum_runs": minimum_runs,
        "status": status,
        "reason": reason,
        "weight_written": False,
        "policy": {
            "same_prompt_and_family_required": True,
            "not_comparable_is_not_training": True,
            "technical_exclusion_is_not_preference_negative": True,
            "validation_and_test_not_used_for_fit": True,
        },
    }


def _prepare_ranker_inputs(rows: list[dict[str, Any]], root: Path) -> tuple[Path, Path]:
    features: dict[tuple[str, str], dict[str, Any]] = {}
    feedback: list[dict[str, Any]] = []
    for row in rows:
        valid, reason = _eligible(row)
        if not valid or row["split"] != "train":
            continue
        run_id = _run_id(row)
        for candidate_id, feature_key in ((str(row["candidate_a"]), "features_a"), (str(row["candidate_b"]), "features_b")):
            key = (run_id, candidate_id)
            candidate_features = {str(name): value for name, value in row[feature_key].items() if isinstance(value, (str, int, float, bool)) and value is not None}
            existing = features.get(key)
            if existing is not None and existing != candidate_features:
                raise AestheticPreferenceError(f"conflicting feature vectors for {run_id}/{candidate_id}")
            features[key] = candidate_features
        feedback.append({
            "run_id": run_id,
            "candidate_id": str(row["candidate_a"]),
            "pairwise": {
                "compared_candidate_id": str(row["candidate_b"]),
                "preference": "candidate" if row["preference"] == "a" else "compared",
                "reason": str(row.get("human_note") or ""),
            },
        })
    feature_rows = [{"run_id": run_id, "candidate_id": candidate_id, "features": values} for (run_id, candidate_id), values in sorted(features.items())]
    return _write_jsonl(root / "candidate_features.jsonl", feature_rows), _write_jsonl(root / "pairwise_feedback.jsonl", feedback)


def train_preference_ranker(
    preference_path: Path,
    output_dir: Path,
    *,
    minimum_comparisons: int = 20,
    minimum_candidates: int = 8,
    minimum_runs: int = 2,
) -> dict[str, Path]:
    preflight = build_preflight(preference_path, minimum_comparisons=minimum_comparisons, minimum_candidates=minimum_candidates, minimum_runs=minimum_runs)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    preflight_path = _write_json(output_dir / "training_preflight.json", preflight)
    if preflight["status"] != "ready":
        raise AestheticPreferenceNotReady(f"VFX preference training refused: {preflight['reason']}. No model weight was written.")
    rows = _load_rows(preference_path.resolve())
    with tempfile.TemporaryDirectory() as temporary:
        feature_path, feedback_path = _prepare_ranker_inputs(rows, Path(temporary))
        ranker_paths = train_pairwise_ranker(
            [feature_path],
            [feedback_path],
            output_dir,
            min_comparisons=minimum_comparisons,
            min_candidates=minimum_candidates,
            min_runs=minimum_runs,
        )
    manifest = _write_json(output_dir / "aesthetic_preference_ranker_manifest.json", {
        "schema_version": "vfx_aesthetic_preference_ranker.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preference_path": preference_path.resolve().as_posix(),
        "training_preflight": preflight,
        "ranker_outputs": {key: path.name for key, path in ranker_paths.items()},
        "status": "experimental_pairwise_ranker",
    })
    ranker_paths["manifest"] = manifest
    ranker_paths["preflight"] = preflight_path
    return ranker_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train or apply the canonical VFX aesthetic preference ranker.")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--preference-training", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument("--minimum-comparisons", type=int, default=20)
    audit.add_argument("--minimum-candidates", type=int, default=8)
    audit.add_argument("--minimum-runs", type=int, default=2)
    train = commands.add_parser("train")
    train.add_argument("--preference-training", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--minimum-comparisons", type=int, default=20)
    train.add_argument("--minimum-candidates", type=int, default=8)
    train.add_argument("--minimum-runs", type=int, default=2)
    rank = commands.add_parser("rank")
    rank.add_argument("--model", type=Path, required=True)
    rank.add_argument("--features", type=Path, action="append", required=True)
    rank.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            result = _write_json(args.output.resolve(), build_preflight(args.preference_training, minimum_comparisons=args.minimum_comparisons, minimum_candidates=args.minimum_candidates, minimum_runs=args.minimum_runs))
        elif args.command == "train":
            result = train_preference_ranker(args.preference_training, args.output_dir, minimum_comparisons=args.minimum_comparisons, minimum_candidates=args.minimum_candidates, minimum_runs=args.minimum_runs)["manifest"]
        else:
            result = rank_candidates(args.model, args.features, args.output)
    except AestheticPreferenceNotReady as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    except (AestheticPreferenceError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "path": result.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
