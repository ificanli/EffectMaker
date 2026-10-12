"""Pretrain a technical visual-dynamics representation without an aesthetic head."""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn


MODEL_SCHEMA = "vfx_visual_dynamics_model.v1"
MODEL_VERSION = "visual_dynamics_mlp.v1"
EFFECT_TYPES = ("impact", "explosion", "slash", "magic_circle", "laser", "lightning", "fire", "shield", "smoke", "water", "unknown")
STYLES = ("realistic", "cartoon", "stylized", "anime", "unknown")
SAMPLE_KINDS = ("generated_prefab", "material_trajectory")
IMAGE_FEATURES = ("image.visible_ratio.mean", "image.visible_ratio.max", "image.visible_ratio.std", "image.temporal_delta.mean", "image.temporal_delta.max", "image.edge_density.mean", "image.mean_saturation.mean", "image.bbox_area_ratio.mean", "image.mean_luma.mean", "image.std_luma.mean")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def feature_vector(row: dict[str, Any]) -> list[float]:
    values: list[float] = []
    values.extend(1.0 if row.get("effect_type") == value else 0.0 for value in EFFECT_TYPES)
    values.extend(1.0 if row.get("style_family") == value else 0.0 for value in STYLES)
    values.extend(1.0 if row.get("sample_kind") == value else 0.0 for value in SAMPLE_KINDS)
    image = row.get("image_features") or {}
    values.extend(float(image.get(name) or 0.0) for name in IMAGE_FEATURES)
    timeline = row.get("material_timeline") or {}
    values.extend([
        min(1.0, float(timeline.get("frame_count") or 0) / 64.0),
        min(1.0, float(timeline.get("delta_count") or 0) / 32.0),
        min(1.0, float(timeline.get("changed_frame_count") or 0) / 32.0),
        float(bool(timeline.get("has_unenumerated_property_block_values"))),
        float(str(timeline.get("global_shader_state_status") or "") == "instrumented"),
        min(1.0, float(timeline.get("global_shader_value_count") or 0) / 8.0),
        min(1.0, float(timeline.get("global_shader_delta_count") or 0) / 32.0),
    ])
    return values


class VisualDynamicsModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64) -> None:
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
        self.dynamic_head = nn.Linear(hidden_dim, 1)
        self.delta_head = nn.Linear(hidden_dim, 1)

    def forward(self, inputs: Tensor) -> tuple[Tensor, Tensor]:
        latent = self.encoder(inputs)
        return self.dynamic_head(latent).squeeze(-1), self.delta_head(latent).squeeze(-1)


def _evaluate(model: VisualDynamicsModel, rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {"record_count": 0.0, "dynamic_accuracy": 0.0, "dynamic_cross_entropy": 0.0, "delta_mae": 0.0}
    model.eval()
    with torch.inference_mode():
        x = torch.tensor([feature_vector(row) for row in rows], dtype=torch.float32)
        dynamic_logits, delta_prediction = model(x)
        dynamic_target = torch.tensor([float((row.get("material_timeline") or {}).get("has_dynamic_material_state")) for row in rows], dtype=torch.float32)
        delta_target = torch.tensor([math.log1p(float((row.get("material_timeline") or {}).get("delta_count") or 0)) for row in rows], dtype=torch.float32)
        dynamic_probability = torch.sigmoid(dynamic_logits)
    return {
        "record_count": float(len(rows)),
        "dynamic_accuracy": float(((dynamic_probability >= 0.5) == (dynamic_target >= 0.5)).float().mean().item()),
        "dynamic_cross_entropy": float(nn.BCEWithLogitsLoss()(dynamic_logits, dynamic_target).item()),
        "delta_mae": float(torch.abs(delta_prediction - delta_target).mean().item()),
    }


def train_model(dataset_root: Path, output_dir: Path, epochs: int = 60, batch_size: int = 32, hidden_dim: int = 64, learning_rate: float = 0.002, seed: int = 20260903) -> dict[str, Path]:
    dataset_root = dataset_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"visual dynamics model output already exists and is not empty: {output_dir}")
    manifest = _read(dataset_root / "dataset_manifest.json")
    if manifest.get("status") != "pass_technical_self_supervision_quality_head_blocked":
        raise ValueError("technical visual dynamics view with blocked quality head is required")
    rows = _read_jsonl(dataset_root / manifest["files"]["records"])
    splits = {split: [row for row in rows if row.get("split") == split] for split in ("train", "validation", "test")}
    if not all(splits.values()):
        raise ValueError("visual dynamics model splits must be non-empty")
    torch.manual_seed(seed)
    random.seed(seed)
    input_dim = len(feature_vector(rows[0]))
    model = VisualDynamicsModel(input_dim, hidden_dim)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    dynamic_loss = nn.BCEWithLogitsLoss()
    delta_loss = nn.MSELoss()
    history: list[dict[str, float]] = []
    best_state: dict[str, Tensor] | None = None
    best_validation = float("inf")
    for epoch in range(1, epochs + 1):
        order = list(range(len(splits["train"])))
        random.Random(seed + epoch).shuffle(order)
        model.train()
        for start in range(0, len(order), batch_size):
            batch = [splits["train"][index] for index in order[start:start + batch_size]]
            x = torch.tensor([feature_vector(row) for row in batch], dtype=torch.float32)
            dynamic_target = torch.tensor([float((row.get("material_timeline") or {}).get("has_dynamic_material_state")) for row in batch], dtype=torch.float32)
            delta_target = torch.tensor([math.log1p(float((row.get("material_timeline") or {}).get("delta_count") or 0)) for row in batch], dtype=torch.float32)
            optimizer.zero_grad(set_to_none=True)
            dynamic_logits, delta_prediction = model(x)
            loss = dynamic_loss(dynamic_logits, dynamic_target) + 0.25 * delta_loss(delta_prediction, delta_target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        validation = _evaluate(model, splits["validation"])
        history.append({"epoch": float(epoch), **validation})
        if validation["dynamic_cross_entropy"] + validation["delta_mae"] < best_validation:
            best_validation = validation["dynamic_cross_entropy"] + validation["delta_mae"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError("visual dynamics model did not produce a checkpoint")
    model.load_state_dict(best_state)
    metrics = {split: _evaluate(model, values) for split, values in splits.items()}
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "visual_dynamics_model.pt"
    torch.save({"schema_version": MODEL_SCHEMA, "model_version": MODEL_VERSION, "state_dict": {key: value.cpu() for key, value in model.state_dict().items()}, "config": {"input_dim": input_dim, "hidden_dim": hidden_dim}, "feature_names": {"effect_types": EFFECT_TYPES, "styles": STYLES, "sample_kinds": SAMPLE_KINDS, "image_features": IMAGE_FEATURES}}, checkpoint)
    metrics_path = _write(output_dir / "metrics.json", {"schema_version": MODEL_SCHEMA, "model_version": MODEL_VERSION, "dataset_id": manifest["view_id"], "metrics": metrics, "input_dim": input_dim, "hidden_dim": hidden_dim, "history": history, "human_labels_used": 0, "aesthetic_quality_head": "blocked_no_professional_teacher", "training_scope": "Technical visual and material-state self-supervision only; predicts dynamic state and delta magnitude, not aesthetic quality.", "status": "technical_pretraining_only", "created_at": datetime.now(timezone.utc).isoformat()})
    card = output_dir / "MODEL_CARD.md"
    card.write_text(f"""# Visual Dynamics Model\n\nStatus: `technical_pretraining_only`.\n\nThis shared MLP is trained on `{manifest['view_id']}` to predict runtime material dynamic state and material change magnitude from continuous-frame image features and MaterialTimeline evidence. It has no aesthetic quality head because the professional Teacher readiness count is `{manifest['teacher_ready_count']}`.\n\nThe output is a technical representation for later model work. It does not judge whether an effect looks good, does not use nonexpert aesthetic feedback, and does not promote visibility or dynamic state to aesthetic truth.\n""", encoding="utf-8")
    return {"checkpoint": checkpoint, "metrics": metrics_path, "model_card": card}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train a technical visual dynamics model without an aesthetic head.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=64)
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
