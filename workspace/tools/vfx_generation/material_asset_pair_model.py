"""Train a small neural ranker for technical Material x Shader x Texture pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn

from .material_asset_pair_dataset import COLORS, EFFECT_TYPES, ELEMENTS, ROLES, STYLES


MODEL_SCHEMA = "vfx_material_asset_pair_model.v1"
MODEL_VERSION = "material_asset_pair_mlp.v1"
HASH_BUCKET_COUNT = 32


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


FEATURE_SPEC = {
    "effect_type": list(EFFECT_TYPES),
    "elements": list(ELEMENTS),
    "role": list(ROLES),
    "style": list(STYLES),
    "colors": list(COLORS),
    "pipeline": ["urp", "builtin", "unknown"],
    "texture_tags": ["alpha.gradient", "alpha.sparse", "alpha.structured", "alpha.opaque", "luma.bright_core", "luma.high_contrast", "shape.horizontal_strip", "shape.circle", "slot.alpha_mask", "slot.base_map", "slot.dissolve_map", "slot.distortion_map", "semantic.spark", "semantic.ring", "semantic.trail"],
    "shader_hash_bucket_count": HASH_BUCKET_COUNT,
    "numeric": ["log2_texture_width", "log2_texture_height", "material_property_count", "shader_property_count", "prefab_graph_usage_count"],
}


def _one_hot(value: str, values: list[str]) -> list[float]:
    return [1.0 if value == item else 0.0 for item in values]


def feature_vector(row: dict[str, Any]) -> list[float]:
    values: list[float] = []
    values.extend(_one_hot(str(row.get("effect_type") or "unknown"), EFFECT_TYPES))
    elements = set(str(value) for value in row.get("effect_element_tags") or [])
    values.extend(1.0 if element in elements else 0.0 for element in ELEMENTS)
    values.extend(_one_hot(str(row.get("layer_role") or "core"), ROLES))
    values.extend(_one_hot(str(row.get("style_family") or "unknown"), STYLES))
    colors = set(str(value) for value in row.get("color_tags") or [])
    values.extend(1.0 if color in colors else 0.0 for color in COLORS)
    pipelines = set(str(value) for value in row.get("shader_pipeline_tags") or [])
    values.extend(1.0 if pipeline in pipelines else 0.0 for pipeline in ("urp", "builtin"))
    tags = set(str(value) for value in row.get("texture_tags") or [])
    values.extend(1.0 if tag in tags else 0.0 for tag in FEATURE_SPEC["texture_tags"])
    bucket = int(hashlib.sha256(str(row.get("shader_id") or "").encode("utf-8")).hexdigest()[:8], 16) % HASH_BUCKET_COUNT
    values.extend(1.0 if index == bucket else 0.0 for index in range(HASH_BUCKET_COUNT))
    values.extend([
        math.log2(max(1, int(row.get("texture_width") or 0)) + 1.0) / 12.0,
        math.log2(max(1, int(row.get("texture_height") or 0)) + 1.0) / 12.0,
        min(1.0, int(row.get("material_property_count") or 0) / 96.0),
        min(1.0, int(row.get("shader_property_count") or 0) / 96.0),
        min(1.0, int(row.get("prefab_graph_usage_count") or 0) / 16.0),
    ])
    return values


class MaterialAssetPairModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 96) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return self.network(inputs).squeeze(-1)


def load_model(checkpoint_path: Path) -> MaterialAssetPairModel:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    if payload.get("schema_version") != MODEL_SCHEMA or payload.get("model_version") != MODEL_VERSION:
        raise ValueError(f"unsupported asset pair checkpoint: {checkpoint_path}")
    config = payload.get("config") or {}
    model = MaterialAssetPairModel(int(config["input_dim"]), int(config["hidden_dim"]))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model


def score_pair(model: MaterialAssetPairModel, material: dict[str, Any], shader: dict[str, Any], texture: dict[str, Any], role: str, condition: dict[str, Any]) -> float:
    row = {
        "effect_type": condition.get("effect_type") or condition.get("effect_family") or "unknown",
        "effect_element_tags": condition.get("effect_element_tags") or ["energy"],
        "layer_role": role,
        "style_family": condition.get("style_family") or "unknown",
        "color_tags": condition.get("color_keywords") or ["unknown"],
        "shader_id": shader.get("asset_id"),
        "shader_pipeline_tags": shader.get("pipeline_tags") or [],
        "texture_tags": texture.get("tags") or [],
        "texture_width": texture.get("width") or 0,
        "texture_height": texture.get("height") or 0,
        "material_property_count": len(material.get("property_names") or []),
        "shader_property_count": len(shader.get("property_names") or []),
        "prefab_graph_usage_count": 0,
    }
    with torch.inference_mode():
        probability = torch.sigmoid(model(torch.tensor([feature_vector(row)], dtype=torch.float32)))[0]
    return float(probability.item())


def _metrics(model: MaterialAssetPairModel, rows: list[dict[str, Any]], device: torch.device) -> dict[str, float]:
    if not rows:
        return {"record_count": 0.0, "cross_entropy": 0.0, "accuracy": 0.0, "positive_recall": 0.0, "negative_recall": 0.0}
    model.eval()
    with torch.inference_mode():
        x = torch.tensor([feature_vector(row) for row in rows], dtype=torch.float32, device=device)
        y = torch.tensor([float(row["label"]) for row in rows], dtype=torch.float32, device=device)
        logits = model(x)
        loss = nn.BCEWithLogitsLoss()(logits, y)
        predictions = logits >= 0
        positive = y == 1
        negative = y == 0
    return {
        "record_count": float(len(rows)),
        "cross_entropy": float(loss.item()),
        "accuracy": float((predictions == (y == 1)).float().mean().item()),
        "positive_recall": float((predictions[positive].float().mean().item()) if positive.any() else 0.0),
        "negative_recall": float(((~predictions[negative]).float().mean().item()) if negative.any() else 0.0),
    }


def _baseline_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {"record_count": 0.0, "accuracy": 0.0, "positive_recall": 0.0, "negative_recall": 0.0}
    predictions = [float(row.get("baseline_score") or 0.0) >= 0.2 for row in rows]
    labels = [int(row["label"]) == 1 for row in rows]
    positive = [index for index, label in enumerate(labels) if label]
    negative = [index for index, label in enumerate(labels) if not label]
    return {
        "record_count": float(len(rows)),
        "accuracy": sum(prediction == label for prediction, label in zip(predictions, labels)) / len(rows),
        "positive_recall": sum(predictions[index] for index in positive) / max(1, len(positive)),
        "negative_recall": sum(not predictions[index] for index in negative) / max(1, len(negative)),
    }


def train_model(dataset_root: Path, output_dir: Path, epochs: int = 30, batch_size: int = 128, hidden_dim: int = 96, learning_rate: float = 0.002, seed: int = 20260903) -> dict[str, Path]:
    dataset_root = dataset_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"asset pair model output already exists and is not empty: {output_dir}")
    manifest = _read(dataset_root / "dataset_manifest.json")
    if manifest.get("status") != "pass" or manifest.get("schema_version") != "vfx_material_asset_pair_training_dataset.v1":
        raise ValueError(f"verified asset pair dataset expected: {dataset_root}")
    rows = _read_jsonl(dataset_root / manifest["files"]["examples"])
    if any(int(row.get("human_labels_used") or 0) != 0 for row in rows):
        raise ValueError("asset pair model must not consume human labels")
    splits = {split: [row for row in rows if row.get("split") == split] for split in ("train", "validation", "test")}
    if not all(splits.values()):
        raise ValueError("all asset pair model splits must be non-empty")
    device = torch.device("cpu")
    random.seed(seed)
    torch.manual_seed(seed)
    input_dim = len(feature_vector(rows[0]))
    model = MaterialAssetPairModel(input_dim, hidden_dim).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss()
    history: list[dict[str, float]] = []
    best_state: dict[str, Tensor] | None = None
    best_validation = float("inf")
    for epoch in range(1, epochs + 1):
        order = list(range(len(splits["train"])))
        random.Random(seed + epoch).shuffle(order)
        model.train()
        loss_sum = 0.0
        steps = 0
        for start in range(0, len(order), batch_size):
            batch = [splits["train"][index] for index in order[start:start + batch_size]]
            x = torch.tensor([feature_vector(row) for row in batch], dtype=torch.float32, device=device)
            y = torch.tensor([float(row["label"]) for row in batch], dtype=torch.float32, device=device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            loss_sum += float(loss.item())
            steps += 1
        validation = _metrics(model, splits["validation"], device)
        history.append({"epoch": float(epoch), "train_cross_entropy": loss_sum / max(1, steps), "validation_cross_entropy": validation["cross_entropy"], "validation_accuracy": validation["accuracy"]})
        if validation["cross_entropy"] < best_validation:
            best_validation = validation["cross_entropy"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError("asset pair model did not produce a checkpoint")
    model.load_state_dict(best_state)
    metrics = {split: _metrics(model, values, device) for split, values in splits.items()}
    baseline = {split: _baseline_metrics(values) for split, values in splits.items()}
    candidate_better = metrics["test"]["cross_entropy"] < 0.69314718056 and metrics["test"]["accuracy"] >= baseline["test"]["accuracy"]
    status = "experimental_technical_ranker" if candidate_better else "experimental_not_better_than_heuristic"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "material_asset_pair_model.pt"
    torch.save({"schema_version": MODEL_SCHEMA, "model_version": MODEL_VERSION, "state_dict": {key: value.cpu() for key, value in model.state_dict().items()}, "config": {"input_dim": input_dim, "hidden_dim": hidden_dim}, "feature_spec": FEATURE_SPEC}, checkpoint_path)
    feature_path = _write(output_dir / "feature_spec.json", {"schema_version": "vfx_material_asset_pair_feature_spec.v1", "model_version": MODEL_VERSION, "features": FEATURE_SPEC})
    metrics_path = _write(output_dir / "metrics.json", {
        "schema_version": MODEL_SCHEMA,
        "model_version": MODEL_VERSION,
        "dataset_id": manifest["dataset_id"],
        "registry_id": manifest["registry_id"],
        "device": str(device),
        "epochs": epochs,
        "batch_size": batch_size,
        "metrics": metrics,
        "heuristic_baseline": baseline,
        "candidate_better_than_heuristic": candidate_better,
        "original_split_record_counts": {split: len(values) for split, values in splits.items()},
        "material_cluster_counts": {split: len({row["material_cluster"] for row in values}) for split, values in splits.items()},
        "human_labels_used": 0,
        "aesthetic_labels_used": 0,
        "training_scope": "Technical source-binding and semantic-contrast ranking only; no human or aesthetic labels.",
        "history": history,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    card_path = output_dir / "MODEL_CARD.md"
    card_path.write_text(f"""# Material Asset Pair Model\n\nStatus: `{status}`.\n\nThis CPU PyTorch MLP ranks technical Material x Shader x Texture compatibility using Prompt semantic hypotheses, layer role, asset tags, Shader pipeline/property counts and source Prefab binding evidence.\n\nDataset: `{manifest['dataset_id']}`. Positive labels are source Material texture bindings. Negative labels are semantic contrast pairs only; they are not aesthetic quality labels. Material clusters are isolated across train/validation/test.\n\nThe model is not an aesthetic judge and does not prove that a selected effect looks good. Every selection remains subject to dependency closure, Unity 2022 property checks, compilation, saved-Prefab texture readback and Play Mode capture.\n""", encoding="utf-8")
    return {"checkpoint": checkpoint_path, "feature_spec": feature_path, "metrics": metrics_path, "model_card": card_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train a technical Material x Shader x Texture pair model.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=96)
    parser.add_argument("--learning-rate", type=float, default=0.002)
    parser.add_argument("--seed", type=int, default=20260903)
    args = parser.parse_args(argv)
    try:
        paths = train_model(args.dataset_root, args.output_dir, args.epochs, args.batch_size, args.hidden_dim, args.learning_rate, args.seed)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
