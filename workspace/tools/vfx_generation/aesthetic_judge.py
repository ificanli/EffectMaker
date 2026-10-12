"""Train and apply a lightweight multi-task VFX aesthetic Judge baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
from jsonschema import Draft202012Validator
from scipy import sparse
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.model_selection import GroupKFold


SCORE_TASKS = ("quality_score", "core_readability", "layer_separation", "rhythm", "material", "composition")
STYLE_TASK = "style_family"
MODEL_SCHEMA = "vfx_aesthetic_judge.v1"
TRAINER_VERSION = "aesthetic_judge.1.1.0"


class AestheticJudgeError(ValueError):
    """Raised when Judge data cannot be trained safely."""


class JudgeTrainingNotReady(AestheticJudgeError):
    """Raised when labels or groups do not meet the Judge training gate."""


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AestheticJudgeError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Judge training input does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise AestheticJudgeError(f"JSON object expected: {path}:{line_number}")
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


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path.resolve())
    seen: set[tuple[str, str]] = set()
    for row in rows:
        record_id = str(row.get("record_id") or "")
        group_id = str(row.get("group_id") or "")
        features = row.get("features")
        label = row.get("label")
        if not record_id or not group_id or not isinstance(features, dict) or not isinstance(label, dict):
            raise AestheticJudgeError(f"invalid Judge training row in {path}")
        key = (group_id, str(row.get("candidate_id") or record_id))
        if key in seen:
            raise AestheticJudgeError(f"duplicate Judge training row: {key[0]}/{key[1]}")
        seen.add(key)
    return rows


def _task_values(rows: list[dict[str, Any]], task: str) -> list[Any]:
    values: list[Any] = []
    for row in rows:
        label = row["label"]
        if task == STYLE_TASK:
            value = row.get("style_family")
            if value in {None, "", "unknown"}:
                continue
        elif task == "quality_score":
            value = label.get("quality_score")
        else:
            scores = label.get("scores") if isinstance(label.get("scores"), dict) else {}
            value = scores.get(task)
        if value is not None:
            values.append(value)
    return values


def _task_readiness(rows: list[dict[str, Any]], task: str, minimum_examples: int, minimum_groups: int, minimum_per_class: int) -> dict[str, Any]:
    values = _task_values(rows, task)
    value_groups: dict[str, set[str]] = {}
    for row in rows:
        value = row.get("style_family") if task == STYLE_TASK else row["label"].get("quality_score") if task == "quality_score" else (row["label"].get("scores") or {}).get(task)
        if value in {None, "", "unknown"}:
            continue
        value_groups.setdefault(str(value), set()).add(str(row.get("evaluation_group_id") or row["group_id"]))
    groups = {group for group_set in value_groups.values() for group in group_set}
    counts = Counter(str(value) for value in values)
    reasons: list[str] = []
    if len(values) < minimum_examples:
        reasons.append(f"need {minimum_examples} labels; found {len(values)}")
    if len(groups) < minimum_groups:
        reasons.append(f"need {minimum_groups} groups; found {len(groups)}")
    if task == STYLE_TASK:
        if len(counts) < 2:
            reasons.append("style task needs at least two classes")
        if any(count < minimum_per_class for count in counts.values()):
            reasons.append(f"each style class needs {minimum_per_class} labels")
        if any(len(value_groups.get(style, set())) < minimum_groups for style in counts):
            reasons.append(f"each style class needs labels in {minimum_groups} evaluation groups")
    elif len(counts) < 2:
        reasons.append("regression task needs at least two distinct values")
    return {
        "status": "ready" if not reasons else "blocked",
        "label_count": len(values),
        "group_count": len(groups),
        "value_counts": dict(sorted(counts.items())),
        "reasons": reasons,
    }


def build_preflight(judge_training_path: Path, *, minimum_examples: int = 32, minimum_groups: int = 2, minimum_style_per_class: int = 4) -> dict[str, Any]:
    rows = _load_rows(judge_training_path)
    task_readiness = {
        task: _task_readiness(rows, task, minimum_examples, minimum_groups, minimum_style_per_class)
        for task in (*SCORE_TASKS, STYLE_TASK)
    }
    ready_tasks = [task for task, item in task_readiness.items() if item["status"] == "ready"]
    blocked_tasks = [task for task, item in task_readiness.items() if item["status"] != "ready"]
    blocked_reasons = [f"{task}: {reason}" for task, item in task_readiness.items() for reason in item["reasons"]]
    if rows and not blocked_tasks:
        status = "ready"
        reason = "all Judge tasks have sufficient labels and independent groups"
    elif ready_tasks:
        status = "partial_ready"
        reason = f"ready tasks: {', '.join(ready_tasks)}; blocked tasks: {'; '.join(blocked_reasons)}"
    elif not rows:
        status = "no_eligible_examples"
        reason = "judge_training.jsonl has no feature-backed human labels"
    else:
        status = "blocked_insufficient_labels"
        reason = "; ".join(blocked_reasons)
    return {
        "schema_version": "vfx_aesthetic_judge_preflight.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "judge_training_path": judge_training_path.resolve().as_posix(),
        "trainer_version": TRAINER_VERSION,
        "row_count": len(rows),
        "tasks": task_readiness,
        "ready_tasks": ready_tasks,
        "blocked_tasks": blocked_tasks,
        "minimum_examples": minimum_examples,
        "minimum_groups": minimum_groups,
        "minimum_style_per_class": minimum_style_per_class,
        "status": status,
        "reason": reason,
        "weight_written": False,
        "policy": {
            "human_labels_only": True,
            "not_visible_is_not_training_data": True,
            "technical_exclusion_is_not_aesthetic_negative": True,
            "prompt_condition_feedback_is_not_quality_label": True,
        },
    }


def _matrix(rows: list[dict[str, Any]]) -> tuple[DictVectorizer, sparse.spmatrix]:
    vectorizer = DictVectorizer(sparse=True, sort=True)
    return vectorizer, vectorizer.fit_transform([row["features"] for row in rows]).tocsr()


def _label_for(row: dict[str, Any], task: str) -> Any:
    label = row["label"]
    if task == STYLE_TASK:
        return row["style_family"]
    if task == "quality_score":
        return float(label["quality_score"])
    return float(label["scores"][task])


def _task_indices(rows: list[dict[str, Any]], task: str) -> list[int]:
    indices: list[int] = []
    for index, row in enumerate(rows):
        if task == STYLE_TASK:
            value = row.get("style_family")
        elif task == "quality_score":
            value = row["label"].get("quality_score")
        else:
            value = (row["label"].get("scores") or {}).get(task)
        if value not in {None, "", "unknown"}:
            indices.append(index)
    return indices


def _group_cv_regression(matrix: sparse.spmatrix, labels: np.ndarray, groups: np.ndarray) -> dict[str, Any]:
    unique_groups = np.unique(groups)
    if unique_groups.size < 2:
        return {"status": "not_available", "reason": "fewer than two groups"}
    predictions = np.zeros(labels.shape[0], dtype=np.float64)
    splitter = GroupKFold(n_splits=min(5, int(unique_groups.size)))
    for train_index, test_index in splitter.split(matrix, labels, groups):
        model = Ridge(alpha=1.0)
        model.fit(matrix[train_index], labels[train_index])
        predictions[test_index] = model.predict(matrix[test_index])
    return {"status": "evaluated", "folds": int(min(5, unique_groups.size)), "mae": round(float(mean_absolute_error(labels, predictions)), 6)}


def _group_cv_classification(matrix: sparse.spmatrix, labels: np.ndarray, groups: np.ndarray) -> dict[str, Any]:
    unique_groups = np.unique(groups)
    if unique_groups.size < 2:
        return {"status": "not_available", "reason": "fewer than two groups"}
    predictions = np.empty(labels.shape[0], dtype=object)
    splitter = GroupKFold(n_splits=min(5, int(unique_groups.size)))
    try:
        for train_index, test_index in splitter.split(matrix, labels, groups):
            if len(np.unique(labels[train_index])) < 2:
                return {"status": "not_available", "reason": "a training fold contains one style class"}
            model = _style_model()
            model.fit(matrix[train_index], labels[train_index])
            predictions[test_index] = model.predict(matrix[test_index])
    except ValueError as error:
        return {"status": "not_available", "reason": str(error)}
    return {"status": "evaluated", "folds": int(min(5, unique_groups.size)), "accuracy": round(float(accuracy_score(labels, predictions)), 6)}


def _style_model() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=128,
        max_depth=8,
        class_weight="balanced",
        random_state=20260901,
        n_jobs=1,
    )


def _task_confidence(metric: dict[str, Any], task: str) -> float:
    if metric.get("status") != "evaluated":
        return 0.0
    if task == STYLE_TASK:
        accuracy = metric.get("accuracy")
        return float(np.clip(float(accuracy) if accuracy is not None else 0.0, 0.0, 1.0))
    mae = metric.get("mae")
    return float(np.clip(1.0 - (float(mae) if mae is not None else 5.0) / 5.0, 0.0, 1.0))


def _bootstrap_regressors(matrix: sparse.spmatrix, labels: np.ndarray, task: str, count: int = 8) -> list[Ridge]:
    seed = 20260902 + SCORE_TASKS.index(task) * 100
    random = np.random.default_rng(seed)
    models: list[Ridge] = []
    for _ in range(count):
        indices = random.integers(0, labels.shape[0], size=labels.shape[0])
        model = Ridge(alpha=1.0)
        model.fit(matrix[indices], labels[indices])
        models.append(model)
    return models


def _model_version(judge_training_path: Path, ready_tasks: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(TRAINER_VERSION.encode("utf-8"))
    digest.update("|".join(ready_tasks).encode("utf-8"))
    digest.update(judge_training_path.resolve().read_bytes())
    return f"{TRAINER_VERSION}+{digest.hexdigest()[:12]}"


def train_judge(judge_training_path: Path, output_dir: Path, *, minimum_examples: int = 32, minimum_groups: int = 2, minimum_style_per_class: int = 4) -> dict[str, Path]:
    preflight = build_preflight(judge_training_path, minimum_examples=minimum_examples, minimum_groups=minimum_groups, minimum_style_per_class=minimum_style_per_class)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    preflight_path = _write_json(output_dir / "training_preflight.json", preflight)
    if preflight["status"] not in {"ready", "partial_ready"}:
        raise JudgeTrainingNotReady(f"VFX Judge training refused: {preflight['reason']}. No model weight was written.")

    rows = _load_rows(judge_training_path.resolve())
    vectorizer, matrix = _matrix(rows)
    groups = np.asarray([str(row.get("evaluation_group_id") or row["group_id"]) for row in rows], dtype=object)
    ready_tasks = list(preflight["ready_tasks"])
    blocked_tasks = {task: preflight["tasks"][task] for task in preflight["blocked_tasks"]}
    models: dict[str, Any] = {}
    ensembles: dict[str, list[Any]] = {}
    metrics: dict[str, Any] = {}
    for task in SCORE_TASKS:
        if task not in ready_tasks:
            continue
        indices = _task_indices(rows, task)
        task_rows = [rows[index] for index in indices]
        labels = np.asarray([_label_for(row, task) for row in task_rows], dtype=np.float64)
        model = Ridge(alpha=1.0)
        model.fit(matrix[indices], labels)
        models[task] = model
        ensembles[task] = _bootstrap_regressors(matrix[indices], labels, task)
        metrics[task] = _group_cv_regression(matrix[indices], labels, groups[indices])
    if STYLE_TASK in ready_tasks:
        style_indices = _task_indices(rows, STYLE_TASK)
        style_matrix = matrix[style_indices]
        style_rows = [rows[index] for index in style_indices]
        style_labels = np.asarray([_label_for(row, STYLE_TASK) for row in style_rows], dtype=object)
        style_model = _style_model()
        style_model.fit(style_matrix, style_labels)
        models[STYLE_TASK] = style_model
        metrics[STYLE_TASK] = _group_cv_classification(style_matrix, style_labels, groups[style_indices])

    task_confidences = {task: round(_task_confidence(metrics[task], task), 6) for task in ready_tasks}
    model_version = _model_version(judge_training_path, ready_tasks)
    model_status = "experimental_lightweight_multitask" if not blocked_tasks else "experimental_lightweight_partial_multitask"
    preflight["weight_written"] = True
    _write_json(preflight_path, preflight)

    model_path = output_dir / "aesthetic_judge.joblib"
    joblib.dump({
        "schema_version": MODEL_SCHEMA,
        "trainer_version": TRAINER_VERSION,
        "model_version": model_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "vectorizer": vectorizer,
        "models": models,
        "ensembles": ensembles,
        "tasks": ready_tasks,
        "blocked_tasks": blocked_tasks,
        "task_confidences": task_confidences,
        "training_preflight": preflight,
        "judge_training_path": judge_training_path.resolve().as_posix(),
    }, model_path)
    metrics_path = _write_json(output_dir / "metrics.json", {
        "schema_version": MODEL_SCHEMA,
        "trainer_version": TRAINER_VERSION,
        "model_version": model_version,
        "preflight": preflight,
        "metrics": metrics,
        "task_confidences": task_confidences,
        "available_tasks": ready_tasks,
        "blocked_tasks": blocked_tasks,
        "feature_count": len(vectorizer.feature_names_),
        "model_status": model_status,
        "final_visual_acceptance": False,
    })
    schema_path = _write_json(output_dir / "model_feature_schema.json", {
        "schema_version": MODEL_SCHEMA,
        "feature_names": list(vectorizer.feature_names_),
        "tasks": ready_tasks,
        "blocked_tasks": list(blocked_tasks),
        "input_contract": "judge_training.jsonl rows with features and human label payload",
    })
    card_path = output_dir / "MODEL_CARD.md"
    card_path.write_text(
        "# VFX Aesthetic Judge\n\n"
        f"- Status: `{model_status}`\n- Model version: `{model_version}`\n- Rows: `{len(rows)}`\n"
        f"- Groups: `{len(set(groups))}`\n- Features: `{len(vectorizer.feature_names_)}`\n"
        f"- Available tasks: `{', '.join(ready_tasks)}`\n"
        f"- Blocked tasks: `{', '.join(blocked_tasks) if blocked_tasks else 'none'}`\n\n"
        "This model assists review and candidate routing. It does not certify visual quality, replace human review, or generate Unity assets.\n",
        encoding="utf-8",
    )
    return {"model": model_path, "metrics": metrics_path, "feature_schema": schema_path, "model_card": card_path, "preflight": preflight_path}


def predict(model_path: Path, input_path: Path, output_path: Path) -> Path:
    bundle = joblib.load(model_path.resolve())
    if bundle.get("schema_version") != MODEL_SCHEMA:
        raise AestheticJudgeError("unsupported Judge model bundle")
    rows = _read_jsonl(input_path.resolve())
    if not rows:
        raise AestheticJudgeError("no rows to predict")
    if any(not isinstance(row.get("features"), dict) for row in rows):
        raise AestheticJudgeError("Judge prediction rows require features")
    vectorizer: DictVectorizer = bundle["vectorizer"]
    matrix = vectorizer.transform([row["features"] for row in rows])
    available_tasks = list(bundle.get("tasks") or bundle["models"].keys())
    blocked_tasks = bundle.get("blocked_tasks") or {}
    model_version = str(bundle.get("model_version") or bundle.get("trainer_version") or "unknown")
    global_confidences = bundle.get("task_confidences") or {}
    ensembles = bundle.get("ensembles") or {}
    predictions: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        result: dict[str, Any] = {"candidate_id": row.get("candidate_id"), "group_id": row.get("group_id")}
        for task in SCORE_TASKS:
            if task not in available_tasks:
                continue
            value = float(bundle["models"][task].predict(matrix[index])[0])
            result[task] = round(float(np.clip(value, 0.0 if task != "quality_score" else 1.0, 5.0)), 6)
        task_confidences: dict[str, float] = {}
        task_disagreements: dict[str, float] = {}
        for task in available_tasks:
            if task == STYLE_TASK:
                continue
            ensemble_values = [float(model.predict(matrix[index])[0]) for model in ensembles.get(task, [])]
            disagreement = float(np.clip(np.std(ensemble_values) / 5.0, 0.0, 1.0)) if ensemble_values else 1.0
            task_disagreements[task] = disagreement
            task_confidences[task] = float(global_confidences.get(task) or 0.0) * (1.0 - disagreement)
        if STYLE_TASK in available_tasks:
            style_model: RandomForestClassifier = bundle["models"][STYLE_TASK]
            probabilities = style_model.predict_proba(matrix[index])[0]
            result[STYLE_TASK] = str(style_model.classes_[int(np.argmax(probabilities))])
            result["style_probabilities"] = {str(label): round(float(probability), 6) for label, probability in zip(style_model.classes_, probabilities)}
            style_disagreement = 1.0 - float(np.max(probabilities))
            task_disagreements[STYLE_TASK] = style_disagreement
            task_confidences[STYLE_TASK] = float(global_confidences.get(STYLE_TASK) or 0.0) * (1.0 - style_disagreement)
        confidence = float(np.mean(list(task_confidences.values()))) if task_confidences else 0.0
        disagreement = float(np.mean(list(task_disagreements.values()))) if task_disagreements else 1.0
        result["ai_pseudo_label"] = {
            "label_source": "ai_pseudo_label",
            "model_version": model_version,
            "confidence": round(confidence, 6),
            "task_confidences": {task: round(value, 6) for task, value in task_confidences.items()},
            "task_disagreements": {task: round(value, 6) for task, value in task_disagreements.items()},
            "model_disagreement": round(disagreement, 6),
            "training_weight": round(min(0.2, 0.2 * confidence), 6),
            "expires_with_model_version": True,
            "eligible_tasks": ["aesthetic_judge_semisupervision", "active_learning_priority"],
            "excluded_tasks": ["human_gold", "regression_evaluation", "model_promotion", "preference_training"],
        }
        predictions.append(result)
    return _write_json(output_path.resolve(), {
        "schema_version": "vfx_aesthetic_judge_predictions.v1",
        "model_path": model_path.resolve().as_posix(),
        "model_version": model_version,
        "available_tasks": available_tasks,
        "blocked_tasks": blocked_tasks,
        "prediction_count": len(predictions),
        "policy": {
            "label_source": "ai_pseudo_label",
            "maximum_training_weight": 0.2,
            "excluded_from_human_and_regression_evaluation": True,
        },
        "predictions": predictions,
    })


def _prefab_key(row: dict[str, Any]) -> str:
    return str((row.get("provenance") or {}).get("prefab_path") or "").replace("\\", "/").lower()


def evaluate_regression(model_path: Path, input_path: Path, output_path: Path, *, minimum_samples: int = 24) -> dict[str, Path]:
    if minimum_samples < 1:
        raise AestheticJudgeError("minimum regression samples must be positive")
    model_path, input_path, output_path = model_path.resolve(), input_path.resolve(), output_path.resolve()
    bundle = joblib.load(model_path)
    if bundle.get("schema_version") != MODEL_SCHEMA:
        raise AestheticJudgeError("unsupported Judge model bundle")
    regression_rows = _read_jsonl(input_path)
    if not regression_rows:
        raise AestheticJudgeError("no human regression rows to evaluate")
    training_path = Path(str(bundle.get("judge_training_path") or ""))
    if not training_path.is_file():
        raise AestheticJudgeError("Judge model training source is unavailable for contamination audit")
    training_rows = _read_jsonl(training_path)
    training_candidates = {str(row.get("candidate_id") or "") for row in training_rows}
    training_prefabs = {_prefab_key(row) for row in training_rows if _prefab_key(row)}
    overlapping = [
        row for row in regression_rows
        if str(row.get("candidate_id") or "") in training_candidates or (_prefab_key(row) and _prefab_key(row) in training_prefabs)
    ]
    if overlapping:
        raise AestheticJudgeError(f"regression contamination detected for {len(overlapping)} rows; first: {overlapping[0].get('candidate_id')}")
    prediction_path = output_path.with_name(output_path.stem + "_predictions.json")
    predict(model_path, input_path, prediction_path)
    prediction_payload = _read_json(prediction_path)
    predictions = {str(row.get("candidate_id") or ""): row for row in prediction_payload["predictions"]}
    available_tasks = list(bundle.get("tasks") or [])
    metrics: dict[str, Any] = {}
    for task in available_tasks:
        actual = []
        predicted = []
        for row in regression_rows:
            candidate_id = str(row.get("candidate_id") or "")
            if candidate_id not in predictions:
                continue
            value = row.get("style_family") if task == STYLE_TASK else row["label"].get("quality_score") if task == "quality_score" else (row["label"].get("scores") or {}).get(task)
            if value in {None, "", "unknown"}:
                continue
            actual.append(value)
            predicted.append(predictions[candidate_id][task])
        if task == STYLE_TASK:
            metrics[task] = {"sample_count": len(actual), "accuracy": round(float(accuracy_score(actual, predicted)), 6) if actual else None}
        else:
            metrics[task] = {"sample_count": len(actual), "mae": round(float(mean_absolute_error(actual, predicted)), 6) if actual else None}
    blocked_tasks = sorted((bundle.get("blocked_tasks") or {}).keys())
    promotion_eligible = len(regression_rows) >= minimum_samples and not blocked_tasks
    report = {
        "schema_version": "vfx_aesthetic_judge_regression_evaluation.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_path": model_path.as_posix(),
        "model_version": str(bundle.get("model_version") or bundle.get("trainer_version") or "unknown"),
        "training_path": training_path.resolve().as_posix(),
        "regression_input": input_path.as_posix(),
        "prediction_path": prediction_path.as_posix(),
        "sample_count": len(regression_rows),
        "minimum_samples": minimum_samples,
        "training_overlap_count": 0,
        "available_tasks": available_tasks,
        "blocked_tasks": blocked_tasks,
        "metrics": metrics,
        "promotion_eligible": promotion_eligible,
        "status": "pass" if len(regression_rows) >= minimum_samples else "underfilled",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/aesthetic_judge_regression_evaluation.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        raise AestheticJudgeError(f"Judge regression evaluation schema error: {errors[0].message}")
    return {"evaluation": _write_json(output_path, report), "predictions": prediction_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train or apply a lightweight VFX aesthetic Judge.")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--judge-training", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument("--minimum-examples", type=int, default=32)
    audit.add_argument("--minimum-groups", type=int, default=2)
    audit.add_argument("--minimum-style-per-class", type=int, default=4)
    train = commands.add_parser("train")
    train.add_argument("--judge-training", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--minimum-examples", type=int, default=32)
    train.add_argument("--minimum-groups", type=int, default=2)
    train.add_argument("--minimum-style-per-class", type=int, default=4)
    apply = commands.add_parser("predict")
    apply.add_argument("--model", type=Path, required=True)
    apply.add_argument("--input", type=Path, required=True)
    apply.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("evaluate-regression")
    evaluate.add_argument("--model", type=Path, required=True)
    evaluate.add_argument("--input", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--minimum-samples", type=int, default=24)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            result = _write_json(args.output.resolve(), build_preflight(args.judge_training, minimum_examples=args.minimum_examples, minimum_groups=args.minimum_groups, minimum_style_per_class=args.minimum_style_per_class))
        elif args.command == "train":
            result = train_judge(args.judge_training, args.output_dir, minimum_examples=args.minimum_examples, minimum_groups=args.minimum_groups, minimum_style_per_class=args.minimum_style_per_class)["preflight"]
        elif args.command == "predict":
            result = predict(args.model, args.input, args.output)
        else:
            result = evaluate_regression(args.model, args.input, args.output, minimum_samples=args.minimum_samples)["evaluation"]
    except JudgeTrainingNotReady as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    except (AestheticJudgeError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "path": result.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
