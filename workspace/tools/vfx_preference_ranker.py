"""Train and apply a lightweight pairwise VFX candidate preference ranker."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
from scipy import sparse
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


MODEL_SCHEMA_VERSION = "vfx_pairwise_ranker.v1"
TRAINER_VERSION = "vfx_preference_ranker.1.0.0"


class TrainingDataError(ValueError):
    """Raised when the available evidence cannot support preference training."""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise TrainingDataError(f"JSONL file does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TrainingDataError(f"invalid JSONL {path}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise TrainingDataError(f"JSON object expected at {path}:{line_number}")
        rows.append(row)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_candidate_features(paths: Iterable[Path]) -> dict[tuple[str, str], dict[str, Any]]:
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for path in paths:
        for row in _load_jsonl(path.resolve()):
            run_id = row.get("run_id")
            candidate_id = row.get("candidate_id")
            features = row.get("features")
            if not isinstance(run_id, str) or not isinstance(candidate_id, str) or not isinstance(features, dict):
                raise TrainingDataError(f"invalid candidate feature record in {path}")
            key = (run_id, candidate_id)
            if key in candidates:
                raise TrainingDataError(f"duplicate candidate feature record: {run_id}/{candidate_id}")
            clean_features = {
                str(name): value
                for name, value in features.items()
                if isinstance(value, (str, int, float, bool)) and value is not None
            }
            candidates[key] = {
                "run_id": run_id,
                "candidate_id": candidate_id,
                "features": clean_features,
                "source_path": path.resolve().as_posix(),
            }
    if not candidates:
        raise TrainingDataError("no candidate feature records were loaded")
    return candidates


def load_pairwise_feedback(paths: Iterable[Path], candidates: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for path in paths:
        for line_number, row in enumerate(_load_jsonl(path.resolve()), start=1):
            pairwise = row.get("pairwise")
            if not isinstance(pairwise, dict):
                continue
            preference = pairwise.get("preference")
            if preference == "tie":
                continue
            if preference not in {"candidate", "compared"}:
                raise TrainingDataError(f"invalid pairwise preference at {path}:{line_number}")
            run_id = row.get("run_id")
            candidate_id = row.get("candidate_id")
            compared_id = pairwise.get("compared_candidate_id")
            if not all(isinstance(value, str) and value for value in (run_id, candidate_id, compared_id)):
                raise TrainingDataError(f"incomplete pairwise reference at {path}:{line_number}")
            candidate_key = (run_id, candidate_id)
            compared_key = (run_id, compared_id)
            if candidate_key not in candidates or compared_key not in candidates:
                raise TrainingDataError(f"feedback references missing features at {path}:{line_number}")
            winner_key = candidate_key if preference == "candidate" else compared_key
            loser_key = compared_key if preference == "candidate" else candidate_key
            comparisons.append(
                {
                    "pair_id": f"{run_id}:{path.name}:{line_number}",
                    "run_id": run_id,
                    "winner_key": winner_key,
                    "loser_key": loser_key,
                    "source_path": path.resolve().as_posix(),
                }
            )
    return comparisons


def _check_thresholds(
    comparisons: list[dict[str, Any]],
    *,
    min_comparisons: int,
    min_candidates: int,
    min_runs: int,
    allow_single_run: bool,
) -> dict[str, Any]:
    unique_candidates = {item["winner_key"] for item in comparisons} | {item["loser_key"] for item in comparisons}
    unique_runs = {item["run_id"] for item in comparisons}
    problems: list[str] = []
    if len(comparisons) < min_comparisons:
        problems.append(f"need at least {min_comparisons} non-tie comparisons; found {len(comparisons)}")
    if len(unique_candidates) < min_candidates:
        problems.append(f"need at least {min_candidates} unique candidates; found {len(unique_candidates)}")
    if not allow_single_run and len(unique_runs) < min_runs:
        problems.append(f"need at least {min_runs} independent runs; found {len(unique_runs)}")
    if problems:
        raise TrainingDataError("; ".join(problems))
    return {
        "comparison_count": len(comparisons),
        "candidate_count": len(unique_candidates),
        "run_count": len(unique_runs),
        "run_ids": sorted(unique_runs),
    }


def _fit_components(x: sparse.spmatrix, y: np.ndarray) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler(with_mean=False)
    scaled = scaler.fit_transform(x)
    model = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=20260828)
    model.fit(scaled, y)
    return scaler, model


def _cross_validate(
    x: sparse.spmatrix,
    y: np.ndarray,
    groups: np.ndarray,
) -> dict[str, Any]:
    unique_groups = np.unique(groups)
    if unique_groups.size < 2:
        return {
            "status": "not_available",
            "reason": "fewer than two evaluation groups",
            "roc_auc": None,
            "accuracy": None,
            "log_loss": None,
        }
    folds = min(5, int(unique_groups.size))
    probabilities = np.zeros(y.shape[0], dtype=np.float64)
    predictions = np.zeros(y.shape[0], dtype=np.int64)
    splitter = GroupKFold(n_splits=folds)
    for train_indices, test_indices in splitter.split(x, y, groups):
        scaler, model = _fit_components(x[train_indices], y[train_indices])
        scaled_test = scaler.transform(x[test_indices])
        probabilities[test_indices] = model.predict_proba(scaled_test)[:, 1]
        predictions[test_indices] = model.predict(scaled_test)
    return {
        "status": "evaluated",
        "folds": folds,
        "roc_auc": round(float(roc_auc_score(y, probabilities)), 6),
        "accuracy": round(float(accuracy_score(y, predictions)), 6),
        "log_loss": round(float(log_loss(y, probabilities, labels=[0, 1])), 6),
    }


def train_pairwise_ranker(
    feature_paths: Iterable[Path],
    feedback_paths: Iterable[Path],
    output_dir: Path,
    *,
    min_comparisons: int = 20,
    min_candidates: int = 8,
    min_runs: int = 2,
    allow_single_run: bool = False,
) -> dict[str, Path]:
    feature_paths = [Path(path).resolve() for path in feature_paths]
    feedback_paths = [Path(path).resolve() for path in feedback_paths]
    candidates = load_candidate_features(feature_paths)
    comparisons = load_pairwise_feedback(feedback_paths, candidates)
    readiness = _check_thresholds(
        comparisons,
        min_comparisons=min_comparisons,
        min_candidates=min_candidates,
        min_runs=min_runs,
        allow_single_run=allow_single_run,
    )

    keys = sorted(candidates)
    key_to_index = {key: index for index, key in enumerate(keys)}
    vectorizer = DictVectorizer(sparse=True, sort=True)
    candidate_matrix = vectorizer.fit_transform([candidates[key]["features"] for key in keys]).tocsr()

    pair_rows: list[sparse.spmatrix] = []
    labels: list[int] = []
    evaluation_groups: list[str] = []
    use_run_groups = readiness["run_count"] >= 2
    for comparison in comparisons:
        winner = candidate_matrix[key_to_index[comparison["winner_key"]]]
        loser = candidate_matrix[key_to_index[comparison["loser_key"]]]
        difference = winner - loser
        pair_rows.extend((difference, -difference))
        labels.extend((1, 0))
        group = comparison["run_id"] if use_run_groups else comparison["pair_id"]
        evaluation_groups.extend((group, group))
    x = sparse.vstack(pair_rows, format="csr")
    y = np.asarray(labels, dtype=np.int64)
    groups = np.asarray(evaluation_groups, dtype=object)
    evaluation = _cross_validate(x, y, groups)
    evaluation["grouping"] = "run_id" if use_run_groups else "pair_id"
    evaluation["candidate_leakage_risk"] = not use_run_groups

    scaler, model = _fit_components(x, y)
    feature_names = vectorizer.get_feature_names_out().tolist()
    coefficients = model.coef_[0]
    positive_indices = np.argsort(coefficients)[-15:][::-1]
    negative_indices = np.argsort(coefficients)[:15]
    coefficient_summary = {
        "positive": [{"feature": feature_names[index], "coefficient": float(coefficients[index])} for index in positive_indices],
        "negative": [{"feature": feature_names[index], "coefficient": float(coefficients[index])} for index in negative_indices],
    }

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "preference_ranker.joblib"
    bundle = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "trainer_version": TRAINER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "vectorizer": vectorizer,
        "scaler": scaler,
        "model": model,
        "feature_names": feature_names,
        "training_readiness": readiness,
        "evaluation": evaluation,
    }
    joblib.dump(bundle, model_path)

    metrics_path = _write_json(
        output_dir / "metrics.json",
        {
            "schema_version": MODEL_SCHEMA_VERSION,
            "trainer_version": TRAINER_VERSION,
            "readiness": readiness,
            "evaluation": evaluation,
            "feature_count": len(feature_names),
            "coefficient_summary": coefficient_summary,
            "feature_sources": [path.as_posix() for path in feature_paths],
            "feedback_sources": [path.as_posix() for path in feedback_paths],
            "model_status": "experimental_single_run" if not use_run_groups else "experimental_multi_run",
            "final_visual_acceptance": False,
        },
    )
    schema_path = _write_json(
        output_dir / "model_feature_schema.json",
        {
            "schema_version": MODEL_SCHEMA_VERSION,
            "feature_extractor_contract": "vfx_candidate_features.v1",
            "feature_names": feature_names,
            "pairwise_input": "feature(winner) - feature(loser)",
        },
    )
    card_path = output_dir / "MODEL_CARD.md"
    card_path.write_text(
        "# VFX Pairwise Preference Ranker\n\n"
        f"- Status: `{'experimental_single_run' if not use_run_groups else 'experimental_multi_run'}`\n"
        f"- Trainer: `{TRAINER_VERSION}`\n"
        f"- Candidates: `{readiness['candidate_count']}`\n"
        f"- Human comparisons: `{readiness['comparison_count']}`\n"
        f"- Independent runs: `{readiness['run_count']}`\n"
        f"- Evaluation grouping: `{evaluation['grouping']}`\n"
        f"- ROC-AUC: `{evaluation.get('roc_auc')}`\n\n"
        "This model ranks candidates. It does not certify visual quality, generate Unity assets, or replace human review.\n"
        "Never load this joblib file from an untrusted source.\n",
        encoding="utf-8",
    )
    return {"model": model_path, "metrics": metrics_path, "feature_schema": schema_path, "model_card": card_path}


def rank_candidates(model_path: Path, feature_paths: Iterable[Path], output_path: Path) -> Path:
    bundle = joblib.load(model_path.resolve())
    if bundle.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise TrainingDataError("unsupported model bundle")
    candidates = load_candidate_features(feature_paths)
    keys = sorted(candidates)
    vectorizer: DictVectorizer = bundle["vectorizer"]
    scaler: StandardScaler = bundle["scaler"]
    model: LogisticRegression = bundle["model"]
    matrix = vectorizer.transform([candidates[key]["features"] for key in keys]).tocsr()
    scores: list[dict[str, Any]] = []
    for index, key in enumerate(keys):
        probabilities: list[float] = []
        for other_index in range(len(keys)):
            if index == other_index:
                continue
            difference = matrix[index] - matrix[other_index]
            probability = float(model.predict_proba(scaler.transform(difference))[:, 1][0])
            probabilities.append(probability)
        scores.append(
            {
                "run_id": key[0],
                "candidate_id": key[1],
                "preference_score": round(float(np.mean(probabilities)) if probabilities else 0.5, 6),
            }
        )
    scores.sort(key=lambda row: (-row["preference_score"], row["candidate_id"]))
    return _write_json(
        output_path.resolve(),
        {
            "schema_version": "vfx_preference_ranking.v1",
            "model_path": model_path.resolve().as_posix(),
            "candidate_count": len(scores),
            "ranking": scores,
            "final_visual_acceptance": False,
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train or apply a pairwise VFX preference ranker.")
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train")
    train.add_argument("--features", type=Path, action="append", required=True)
    train.add_argument("--feedback", type=Path, action="append", required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--min-comparisons", type=int, default=20)
    train.add_argument("--min-candidates", type=int, default=8)
    train.add_argument("--min-runs", type=int, default=2)
    train.add_argument("--allow-single-run", action="store_true")
    rank = commands.add_parser("rank")
    rank.add_argument("--model", type=Path, required=True)
    rank.add_argument("--features", type=Path, action="append", required=True)
    rank.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "train":
            paths = train_pairwise_ranker(
                args.features,
                args.feedback,
                args.output_dir,
                min_comparisons=args.min_comparisons,
                min_candidates=args.min_candidates,
                min_runs=args.min_runs,
                allow_single_run=args.allow_single_run,
            )
            print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
            return 0
        output = rank_candidates(args.model, args.features, args.output)
        print(json.dumps({"success": True, "ranking": output.as_posix()}, ensure_ascii=False, indent=2))
        return 0
    except (TrainingDataError, OSError, ValueError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
