"""Train a gated, multi-task VFX Prompt-condition scorer from human frame labels."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import joblib
import numpy as np
from jsonschema import Draft202012Validator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


CONDITION_FIELDS = ("风格", "主色", "特效类别", "节奏", "无长拖尾", "整体")
LABELS = ("符合", "部分符合", "不符合")
UNKNOWN = "无法判断"
SCHEMA_VERSION = "vfx_prompt_condition_scorer_dataset.v1"
MODEL_SCHEMA_VERSION = "vfx_prompt_condition_scorer.v1"


class ScorerNotReady(ValueError):
    pass


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _read_image(path: Path) -> np.ndarray:
    try:
        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError as error:
        raise ValueError(f"could not read frame {path}: {error}") from error
    if image is None:
        raise ValueError(f"could not decode frame {path}")
    return image


def _frame_features(path: Path) -> dict[str, float]:
    image = _read_image(path)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners = np.concatenate((
        image[:8, :8].reshape(-1, 3), image[:8, -8:].reshape(-1, 3),
        image[-8:, :8].reshape(-1, 3), image[-8:, -8:].reshape(-1, 3),
    ))
    background = np.median(corners, axis=0).astype(np.uint8)
    visible = cv2.cvtColor(cv2.absdiff(image, background), cv2.COLOR_BGR2GRAY) > 8
    saturated = hsv[:, :, 1] >= 45
    colored = visible & saturated
    total = float(visible.size or 1)
    blue = (hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 132)
    warm = (hsv[:, :, 0] <= 30) | (hsv[:, :, 0] >= 170)
    edges = cv2.Canny(gray, 40, 120)
    return {
        "visible_ratio": float(visible.mean()),
        "saturation": float(hsv[:, :, 1][colored].mean() / 255.0) if colored.any() else 0.0,
        "brightness": float(gray[visible].mean() / 255.0) if visible.any() else 0.0,
        "blue_fraction": float(blue[colored].mean()) if colored.any() else 0.0,
        "warm_fraction": float(warm[colored].mean()) if colored.any() else 0.0,
        "edge_density": float((edges > 0).sum() / total),
        "overexposed_ratio": float((gray >= 245).mean()),
    }


def extract_sequence_features(frame_paths: list[Path]) -> dict[str, float]:
    if not frame_paths:
        raise ValueError("at least one frame is required")
    frames = [_frame_features(path) for path in frame_paths]
    result: dict[str, float] = {"frame_count": float(len(frames))}
    for name in frames[0]:
        values = np.asarray([frame[name] for frame in frames], dtype=np.float64)
        result[f"{name}_mean"] = float(values.mean())
        result[f"{name}_max"] = float(values.max())
        result[f"{name}_min"] = float(values.min())
        result[f"{name}_std"] = float(values.std())
    visible = np.asarray([frame["visible_ratio"] for frame in frames], dtype=np.float64)
    result["peak_frame_ratio"] = float(visible.argmax()) / max(1, len(frames) - 1)
    result["active_frame_ratio"] = float((visible >= 0.01).mean())
    result["late_visible_ratio"] = float(visible[len(frames) // 2 :].mean())
    previews = [cv2.resize(_read_image(path), (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32) for path in frame_paths]
    if len(previews) > 1:
        deltas = [float(cv2.absdiff(previews[index], previews[index - 1]).mean() / 255.0) for index in range(1, len(previews))]
        result["temporal_delta_mean"] = float(np.mean(deltas))
        result["temporal_delta_max"] = float(np.max(deltas))
        result["temporal_delta_std"] = float(np.std(deltas))
    else:
        result.update({"temporal_delta_mean": 0.0, "temporal_delta_max": 0.0, "temporal_delta_std": 0.0})
    return {key: round(value, 8) for key, value in result.items()}


def _feature_names(rows: list[dict[str, Any]]) -> list[str]:
    names = set()
    for row in rows:
        names.update(row["features"])
    return sorted(names)


def build_dataset(overlay_paths: Iterable[Path], output_dir: Path, dataset_id: str) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"scorer output already exists and is not empty: {output_dir}")
    overlay_paths = [Path(path).resolve() for path in overlay_paths]
    overlays: list[dict[str, Any]] = []
    for path in overlay_paths:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"condition overlay does not exist: {path}")
        overlays.extend(_read_jsonl(path))
    rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    unknown_counts: Counter[str] = Counter()
    condition_counts: dict[str, Counter[str]] = {field: Counter() for field in CONDITION_FIELDS}
    for overlay in overlays:
        candidate_id = str(overlay.get("candidate_id") or "")
        trace = overlay.get("trace") if isinstance(overlay.get("trace"), dict) else {}
        render_paths = [str(path) for path in trace.get("render_paths", []) if str(path) != "not_rendered"]
        frame_paths = [_resolve_repo_path(path) for path in render_paths]
        conditions = overlay.get("human_conditions") if isinstance(overlay.get("human_conditions"), dict) else {}
        reasons: list[str] = []
        if not candidate_id:
            reasons.append("missing_candidate_id")
        if not frame_paths or any(not path.is_file() for path in frame_paths):
            reasons.append("no_independent_visual_evidence")
        known = {field: str(conditions[field]) for field in CONDITION_FIELDS if conditions.get(field) in LABELS}
        for field in CONDITION_FIELDS:
            if field not in known:
                unknown_counts[field] += 1
            else:
                condition_counts[field][known[field]] += 1
        if not known:
            reasons.append("all_prompt_conditions_not_judgable")
        if reasons and reasons == ["all_prompt_conditions_not_judgable"]:
            exclusions.append({"candidate_id": candidate_id, "source_overlay": "unknown", "reasons": reasons})
            continue
        if reasons:
            exclusions.append({"candidate_id": candidate_id, "source_overlay": "unknown", "reasons": reasons})
            continue
        features = extract_sequence_features(frame_paths)
        rows.append({
            "schema_version": "vfx_prompt_condition_scorer_row.v1",
            "candidate_id": candidate_id,
            "group_id": str(overlay.get("batch_id") or overlay.get("source_composition_manifest") or candidate_id),
            "features": features,
            "labels": known,
            "provenance": {"overlay_paths": [path.as_posix() for path in overlay_paths], "render_paths": [path.as_posix() for path in frame_paths]},
        })
    names = _feature_names(rows)
    rows_path = _write_jsonl(output_dir / "scorer_feature_rows.jsonl", rows)
    exclusions_path = _write_jsonl(output_dir / "scorer_exclusions.jsonl", exclusions)
    feature_schema_path = _write_json(output_dir / "feature_schema.json", {"schema_version": "vfx_prompt_condition_scorer_features.v1", "feature_names": names, "feature_count": len(names)})
    blocked = {field: "awaiting complete class coverage and independent evaluation groups" for field in CONDITION_FIELDS}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "overlay_count": len(overlays),
        "feature_row_count": len(rows),
        "condition_counts": {field: dict(sorted(counts.items())) for field, counts in condition_counts.items()},
        "unknown_condition_counts": dict(sorted(unknown_counts.items())),
        "exclusion_count": len(exclusions),
        "files": {"feature_rows": rows_path.name, "exclusions": exclusions_path.name, "feature_schema": feature_schema_path.name},
        "training_gate": {"status": "no_labeled_conditions" if not rows else "insufficient_labels", "minimum_per_class": 4, "minimum_groups": 2, "ready_conditions": [], "blocked_conditions": blocked},
        "policy": {"not_visible_is_not_training_data": True, "unknown_condition_is_not_training_data": True, "ai_draft_is_not_human_label": True, "quality_label_is_not_prompt_condition_label": True},
        "status": "pass",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/vfx_prompt_condition_scorer_dataset.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise ValueError(f"scorer dataset manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "scorer_dataset_manifest.json", manifest)
    return {"manifest": manifest_path, "features": rows_path, "exclusions": exclusions_path, "feature_schema": feature_schema_path}


def _training_rows(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = manifest_path.resolve()
    manifest = _read_json(manifest_path)
    rows_path = manifest_path.parent / str(manifest["files"]["feature_rows"])
    return manifest, _read_jsonl(rows_path)


def _check_training(rows: list[dict[str, Any]], minimum_per_class: int, minimum_groups: int) -> tuple[list[str], dict[str, str]]:
    ready: list[str] = []
    blocked: dict[str, str] = {}
    for field in CONDITION_FIELDS:
        labeled = [row for row in rows if row.get("labels", {}).get(field) in LABELS]
        counts = Counter(row["labels"][field] for row in labeled)
        groups = {str(row.get("group_id")) for row in labeled}
        missing = [label for label in LABELS if counts[label] < minimum_per_class]
        if missing:
            blocked[field] = f"class coverage insufficient: {dict(counts)}; missing {missing}"
        elif len(groups) < minimum_groups:
            blocked[field] = f"need at least {minimum_groups} independent groups; found {len(groups)}"
        else:
            ready.append(field)
    return ready, blocked


def train_scorer(manifest_path: Path, output_dir: Path, *, minimum_per_class: int = 4, minimum_groups: int = 2) -> dict[str, Path]:
    manifest, rows = _training_rows(manifest_path)
    ready, blocked = _check_training(rows, minimum_per_class, minimum_groups)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    preflight = {"schema_version": "vfx_prompt_condition_scorer_training_preflight.v1", "created_at": datetime.now(timezone.utc).isoformat(), "dataset_manifest": manifest_path.resolve().as_posix(), "status": "ready" if ready else "blocked_insufficient_labels", "ready_conditions": ready, "blocked_conditions": blocked, "weight_written": False}
    preflight_path = _write_json(output_dir / "training_preflight.json", preflight)
    if len(ready) != len(CONDITION_FIELDS):
        raise ScorerNotReady("Prompt condition scorer training refused: " + "; ".join(f"{field}: {reason}" for field, reason in blocked.items()) + ". No model weight was written.")
    names = _feature_names(rows)
    models: dict[str, Pipeline] = {}
    metrics: dict[str, Any] = {}
    for field in CONDITION_FIELDS:
        subset = [row for row in rows if row.get("labels", {}).get(field) in LABELS]
        x = np.asarray([[float(row["features"].get(name, 0.0)) for name in names] for row in subset], dtype=np.float64)
        y = np.asarray([row["labels"][field] for row in subset])
        groups = np.asarray([row["group_id"] for row in subset])
        model = Pipeline([("scale", StandardScaler()), ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=20260901))])
        folds = min(5, len(set(groups)))
        if folds >= 2:
            predictions = cross_val_predict(model, x, y, cv=GroupKFold(n_splits=folds), groups=groups)
            metrics[field] = {"status": "evaluated", "folds": folds, "accuracy": round(float(accuracy_score(y, predictions)), 6), "balanced_accuracy": round(float(balanced_accuracy_score(y, predictions)), 6), "macro_f1": round(float(f1_score(y, predictions, labels=list(LABELS), average="macro", zero_division=0)), 6)}
        else:
            metrics[field] = {"status": "not_available", "reason": "fewer than two groups"}
        model.fit(x, y)
        models[field] = model
    model_path = output_dir / "prompt_condition_scorer.joblib"
    joblib.dump({"schema_version": MODEL_SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "feature_names": names, "condition_fields": list(CONDITION_FIELDS), "labels": list(LABELS), "models": models, "dataset_manifest": manifest_path.resolve().as_posix()}, model_path)
    metrics_path = _write_json(output_dir / "metrics.json", {"schema_version": MODEL_SCHEMA_VERSION, "feature_count": len(names), "metrics": metrics, "final_visual_acceptance": False})
    card_path = output_dir / "MODEL_CARD.md"
    card_path.write_text("# VFX Prompt Condition Scorer\n\nThis scorer predicts Prompt-condition labels from rendered sequence features. It does not generate Unity assets and never treats `无法判断` as a class. Human review and Unity evidence remain authoritative.\n", encoding="utf-8")
    return {"model": model_path, "preflight": preflight_path, "metrics": metrics_path, "model_card": card_path}


def predict(model_path: Path, frame_paths: Iterable[Path], output_path: Path) -> Path:
    bundle = joblib.load(model_path.resolve())
    if bundle.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise ValueError("unsupported prompt condition scorer bundle")
    paths = [path.resolve() for path in frame_paths]
    features = extract_sequence_features(paths)
    names = list(bundle["feature_names"])
    x = np.asarray([[float(features.get(name, 0.0)) for name in names]], dtype=np.float64)
    result = {field: bundle["models"][field].predict(x)[0] for field in bundle["condition_fields"]}
    return _write_json(output_path.resolve(), {"schema_version": "vfx_prompt_condition_prediction.v1", "model_path": model_path.resolve().as_posix(), "frame_paths": [path.as_posix() for path in paths], "features": features, "predicted_conditions": result, "human_review_required": True})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, train, or apply a VFX Prompt condition scorer.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--overlay", type=Path, action="append", required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--dataset-id", required=True)
    train = commands.add_parser("train")
    train.add_argument("--dataset-manifest", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--minimum-per-class", type=int, default=4)
    train.add_argument("--minimum-groups", type=int, default=2)
    apply = commands.add_parser("predict")
    apply.add_argument("--model", type=Path, required=True)
    apply.add_argument("--frame", type=Path, action="append", required=True)
    apply.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            paths = build_dataset(args.overlay, args.output_dir, args.dataset_id)
        elif args.command == "train":
            paths = train_scorer(args.dataset_manifest, args.output_dir, minimum_per_class=args.minimum_per_class, minimum_groups=args.minimum_groups)
        else:
            paths = {"prediction": predict(args.model, args.frame, args.output)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
