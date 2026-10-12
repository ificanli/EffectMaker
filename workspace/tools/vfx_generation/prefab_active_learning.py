"""Cluster five-layer Prefab records and create a bounded active-learning queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from jsonschema import Draft202012Validator
from sklearn.cluster import KMeans
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler


ALLOWED_ACTIONS = (
    "AI判断正确",
    "应该更好",
    "应该更差",
    "特效类型错误",
    "风格判断错误",
    "主体不清楚",
    "层次有问题",
    "节奏有问题",
    "材质有问题",
    "无法播放",
    "无法判断",
)
SELECTION_MIX = {
    "uncertainty": 0.40,
    "new_cluster": 0.20,
    "model_disagreement": 0.15,
    "promotion_top": 0.10,
    "predicted_low": 0.05,
    "random_audit": 0.10,
}
SELECTION_SIGNAL = {
    "uncertainty": "uncertainty",
    "new_cluster": "novelty",
    "model_disagreement": "model_disagreement",
    "promotion_top": "promotion_top",
    "predicted_low": "predicted_low",
    "random_audit": "random_audit",
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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _hash_float(value: str) -> float:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16) / float(16**12 - 1)


def _cluster_split(cluster_id: str) -> str:
    bucket = int(hashlib.sha256(cluster_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def _feature_map(records: list[dict[str, Any]]) -> dict[str, float | str]:
    by_tier = {record["tier"]: record for record in records}
    technical = (by_tier.get("technical_corpus", {}).get("observations") or {}).get("technical") or {}
    source_hints = (by_tier.get("technical_corpus", {}).get("observations") or {}).get("source_hints") or {}
    visual = (by_tier.get("visual_feature_only", {}).get("observations") or {}).get("visual") or {}
    colors = (by_tier.get("visual_feature_only", {}).get("observations") or {}).get("measured_color") or {}
    pseudo = by_tier.get("ai_pseudo_label", {})
    labels = pseudo.get("labels") or {}
    result: dict[str, float | str] = {
        "technical.node_count": float(technical.get("node_count") or 0),
        "technical.particle_system_count": float(technical.get("particle_system_count") or 0),
        "technical.renderer_count": float(technical.get("renderer_count") or 0),
        "technical.material_count": float(technical.get("material_count") or 0),
        "technical.mesh_count": float(technical.get("mesh_count") or 0),
        "technical.reconstructable": float(technical.get("reconstruction_status") == "reconstructable"),
        "visual.available": float(bool(visual)),
        "visual.duration_seconds": float(visual.get("duration_seconds") or 0),
        "visual.max_visible_area_ratio": float(visual.get("max_visible_area_ratio") or 0),
        "visual.cropped_frame_count": float(visual.get("cropped_frame_count") or 0),
        "source.effect_family_hint": str(source_hints.get("effect_family_hint") or "unknown"),
        "pseudo.element": str((labels.get("observed_element_tags") or ["unknown"])[0]),
        "pseudo.type": str(labels.get("effect_type") or "unknown"),
        "visual.primary_color": str((colors.get("semantic_tags") or ["unknown"])[0]),
    }
    return result


def _recommended_rate(recent_agreement: float | None) -> float:
    if recent_agreement is None:
        return 0.06
    if recent_agreement < 0.80:
        return 0.10
    if recent_agreement < 0.90:
        return 0.05
    if recent_agreement < 0.95:
        return 0.025
    return 0.01


def build_active_learning_batch(
    dataset_root: Path,
    output_root: Path,
    batch_id: str,
    *,
    review_rate: float | None = None,
    recent_agreement: float | None = None,
    minimum_queue_size: int = 16,
    cluster_count: int | None = None,
    seed: int = 20260902,
) -> dict[str, Path]:
    dataset_root = dataset_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"active-learning output already exists and is not empty: {output_root}")
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    records = _read_jsonl(dataset_root / "records.jsonl")
    records_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_sample[record["sample_id"]].append(record)
    unit_samples: dict[str, list[str]] = defaultdict(list)
    for sample_id, sample_records in records_by_sample.items():
        technical = next(record for record in sample_records if record["tier"] == "technical_corpus")
        unit_key = technical["source"].get("prefab_path") or sample_id
        unit_samples[str(unit_key)].append(sample_id)
    unit_keys = sorted(unit_samples)
    unit_features = []
    for unit_key in unit_keys:
        maps = [_feature_map(records_by_sample[sample_id]) for sample_id in unit_samples[unit_key]]
        numeric_keys = sorted({key for row in maps for key, value in row.items() if isinstance(value, (int, float))})
        categorical = next(iter(maps))
        merged: dict[str, float | str] = {key: float(np.mean([float(row.get(key, 0.0)) for row in maps])) for key in numeric_keys}
        merged.update({key: value for key, value in categorical.items() if isinstance(value, str)})
        unit_features.append(merged)
    vectorizer = DictVectorizer(sparse=True, sort=True)
    matrix = vectorizer.fit_transform(unit_features)
    matrix = StandardScaler(with_mean=False).fit_transform(matrix)
    desired_clusters = cluster_count or max(4, min(128, int(math.ceil(math.sqrt(len(unit_keys)) * 2.0))))
    desired_clusters = min(desired_clusters, len(unit_keys))
    model = KMeans(n_clusters=desired_clusters, random_state=seed, n_init=10)
    labels = model.fit_predict(matrix)
    distances = model.transform(matrix)
    label_units: dict[int, list[str]] = defaultdict(list)
    for unit_key, label in zip(unit_keys, labels):
        label_units[int(label)].append(unit_key)
    cluster_ids = {label: "cluster_" + hashlib.sha256("|".join(sorted(keys)).encode("utf-8")).hexdigest()[:12] for label, keys in label_units.items()}
    unit_assignment = {unit_key: cluster_ids[int(label)] for unit_key, label in zip(unit_keys, labels)}
    unit_distance = {unit_key: float(distances[index, int(labels[index])]) for index, unit_key in enumerate(unit_keys)}
    cluster_sizes = Counter(unit_assignment.values())
    human_ready = {record["sample_id"] for record in records if record["tier"] == "human_gold" and record["status"] == "ready"}
    regression = {record["sample_id"] for record in records if record["tier"] == "regression_gold"}
    unit_by_sample = {
        sample_id: str(next(record for record in sample_records if record["tier"] == "technical_corpus")["source"].get("prefab_path") or sample_id)
        for sample_id, sample_records in records_by_sample.items()
    }
    human_ready_units = {unit_by_sample[sample_id] for sample_id in human_ready}
    regression_units = {unit_by_sample[sample_id] for sample_id in regression}
    regression_clusters = {unit_assignment[unit_key] for unit_key in regression_units}
    routed_records = []
    for record in records:
        unit_key = str(record["source"].get("prefab_path") or record["sample_id"])
        routed = json.loads(json.dumps(record, ensure_ascii=False))
        cluster_id = unit_assignment[unit_key]
        routed["grouping"]["cluster_id"] = cluster_id
        routed["training"]["split"] = "regression" if cluster_id in regression_clusters else _cluster_split(cluster_id)
        routed_records.append(routed)

    pseudo_by_sample = {record["sample_id"]: record for record in records if record["tier"] == "ai_pseudo_label"}
    visual_by_sample = {record["sample_id"]: record for record in records if record["tier"] == "visual_feature_only" and record["status"] == "ready"}
    candidates = []
    max_distance = max(unit_distance.values(), default=1.0) or 1.0
    max_visible = max((float((record["observations"].get("visual") or {}).get("max_visible_area_ratio") or 0.0) for record in visual_by_sample.values()), default=1.0) or 1.0
    visual_units: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for sample_id, visual_record in visual_by_sample.items():
        visual_units[unit_by_sample[sample_id]].append((sample_id, visual_record))
    for unit_key, unit_visuals in sorted(visual_units.items()):
        cluster_id = unit_assignment[unit_key]
        if unit_key in human_ready_units or cluster_id in regression_clusters:
            continue
        def sample_rank(item: tuple[str, dict[str, Any]]) -> tuple[int, str]:
            sample_id, _ = item
            technical = next(record for record in records_by_sample[sample_id] if record["tier"] == "technical_corpus")
            reconstructable = (technical["observations"].get("technical") or {}).get("reconstruction_status") == "reconstructable"
            return (0 if reconstructable else 1, sample_id)
        sample_id, visual_record = sorted(unit_visuals, key=sample_rank)[0]
        pseudo = pseudo_by_sample.get(sample_id)
        confidence = float((pseudo or {}).get("label_provenance", {}).get("confidence") or 0.0)
        uncertainty = 1.0 - confidence
        novelty = 0.55 * min(1.0, unit_distance[str(unit_key)] / max_distance) + 0.45 / max(1, cluster_sizes[cluster_id])
        disagreement = 1.0 if pseudo is None else 0.5 if confidence < 0.55 else 0.0
        visible = float((visual_record["observations"].get("visual") or {}).get("max_visible_area_ratio") or 0.0)
        promotion = min(1.0, visible / max_visible)
        predicted_low = 1.0 - promotion
        random_audit = _hash_float(f"{seed}|{sample_id}")
        combined = 0.40 * uncertainty + 0.20 * novelty + 0.15 * disagreement + 0.10 * promotion + 0.05 * predicted_low + 0.10 * random_audit
        candidates.append({
            "sample_id": sample_id,
            "record": visual_record,
            "cluster_id": cluster_id,
            "signals": {"uncertainty": uncertainty, "novelty": novelty, "model_disagreement": disagreement, "promotion_top": promotion, "predicted_low": predicted_low, "random_audit": random_audit, "combined": combined},
            "ai_draft": {
                "labels": (pseudo or {}).get("labels") or {},
                "label_provenance": (pseudo or {}).get("label_provenance") or {"label_source": "none", "confidence": 0.0, "model_version": None},
                "training": (pseudo or {}).get("training") or {"weight": 0.0, "expires_with_model_version": True},
            },
        })

    rate = review_rate if review_rate is not None else _recommended_rate(recent_agreement)
    if rate < 0.01 or rate > 0.10:
        raise ValueError("review_rate must be between 0.01 and 0.10")
    budget = min(len(candidates), max(minimum_queue_size, int(math.ceil(len(candidates) * rate)))) if candidates else 0
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for reason, ratio in SELECTION_MIX.items():
        quota = int(math.ceil(budget * ratio))
        signal_name = SELECTION_SIGNAL[reason]
        ranked = sorted(candidates, key=lambda row: (-float(row["signals"][signal_name]), row["sample_id"]))
        for row in ranked:
            if len(selected) >= budget or quota <= 0:
                break
            if row["sample_id"] in selected_ids:
                continue
            selected.append({**row, "selection_reason": reason})
            selected_ids.add(row["sample_id"])
            quota -= 1
    for row in sorted(candidates, key=lambda value: (-float(value["signals"]["combined"]), value["sample_id"])):
        if len(selected) >= budget:
            break
        if row["sample_id"] not in selected_ids:
            selected.append({**row, "selection_reason": "combined_fill"})
            selected_ids.add(row["sample_id"])
    items = []
    for index, row in enumerate(selected, start=1):
        record = row["record"]
        items.append({"queue_index": index, "sample_id": row["sample_id"], "prefab_path": record["source"].get("prefab_path"), "cluster_id": row["cluster_id"], "selection_reason": row["selection_reason"], "priority_score": round(float(row["signals"]["combined"]), 6), "signals": {key: round(float(value), 6) for key, value in row["signals"].items()}, "ai_draft": row["ai_draft"], "capture_manifest_path": record["evidence"]["capture_manifest_path"], "allowed_actions": list(ALLOWED_ACTIONS)})
    cluster_splits: dict[str, set[str]] = defaultdict(set)
    for record in routed_records:
        cluster_splits[record["grouping"]["cluster_id"]].add(record["training"]["split"])
    queue_ids = [item["sample_id"] for item in items]
    queue_prefabs = [item["prefab_path"] or item["sample_id"] for item in items]
    batch = {"schema_version": "vfx_prefab_active_learning_batch.v1", "created_at": datetime.now(timezone.utc).isoformat(), "batch_id": batch_id, "dataset_id": manifest["dataset_id"], "eligible_count": len(candidates), "review_budget": budget, "review_rate": rate, "selection_mix": SELECTION_MIX, "items": items, "quality_gates": {"duplicate_queue_samples": len(queue_ids) - len(set(queue_ids)), "duplicate_queue_prefabs": len(queue_prefabs) - len(set(queue_prefabs)), "cluster_split_leakage": sum(len(splits) > 1 for splits in cluster_splits.values()), "non_visual_items": sum(item["sample_id"] not in visual_by_sample for item in items), "already_gold_items": sum(item["sample_id"] in human_ready for item in items), "regression_items": sum(item["sample_id"] in regression for item in items)}, "status": "pass"}
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_active_learning_batch.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(batch))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"active-learning batch schema error at {location}: {errors[0].message}")
    output_root.mkdir(parents=True, exist_ok=True)
    batch_path = _write_json(output_root / "active_learning_batch.json", batch)
    assignments_path = _write_jsonl(output_root / "cluster_assignments.jsonl", ({"sample_id": sample_id, "unit_key": unit_key, "cluster_id": unit_assignment[unit_key], "split": "regression" if unit_assignment[unit_key] in regression_clusters else _cluster_split(unit_assignment[unit_key]), "distance_to_centroid": unit_distance[unit_key]} for unit_key in unit_keys for sample_id in sorted(unit_samples[unit_key])))
    routed_path = _write_jsonl(output_root / "routed_records.jsonl", routed_records)
    cluster_path = _write_json(output_root / "cluster_manifest.json", {"schema_version": "vfx_prefab_cluster_manifest.v1", "created_at": datetime.now(timezone.utc).isoformat(), "dataset_id": manifest["dataset_id"], "unit_count": len(unit_keys), "sample_count": len(records_by_sample), "cluster_count": len(cluster_sizes), "cluster_sizes": dict(sorted(cluster_sizes.items())), "feature_names": list(vectorizer.feature_names_), "algorithm": {"name": "KMeans", "random_state": seed, "n_init": 10}, "status": "pass"})
    return {"batch": batch_path, "assignments": assignments_path, "routed_records": routed_path, "clusters": cluster_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a bounded active-learning queue for Prefab review.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--review-rate", type=float)
    parser.add_argument("--recent-agreement", type=float)
    parser.add_argument("--minimum-queue-size", type=int, default=16)
    parser.add_argument("--cluster-count", type=int)
    parser.add_argument("--seed", type=int, default=20260902)
    args = parser.parse_args(argv)
    try:
        paths = build_active_learning_batch(args.dataset_root, args.output_root, args.batch_id, review_rate=args.review_rate, recent_agreement=args.recent_agreement, minimum_queue_size=args.minimum_queue_size, cluster_count=args.cluster_count, seed=args.seed)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
