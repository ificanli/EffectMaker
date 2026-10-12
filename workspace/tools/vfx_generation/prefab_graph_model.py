"""Train a small neural next-token model on deterministic PrefabGraph tokens."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import torch
from torch import Tensor, nn


MODEL_SCHEMA = "vfx_prefab_graph_model.v1"
MODEL_VERSION = "prefab_graph_gru_next_token.v1"
PAD_TOKEN = "<PAD>"
UNK_TOKEN = "<UNK>"
IGNORE_INDEX = -100


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


def _write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _split_bucket(group_id: str) -> int:
    return int(hashlib.sha256(group_id.encode("utf-8")).hexdigest()[:8], 16) % 100


def _declared_split(example: dict[str, Any]) -> str | None:
    split_group = example.get("split_group") or {}
    declared = split_group.get("structure_split")
    if declared is None:
        return None
    value = str(declared)
    if value not in {"train", "validation", "test"}:
        raise ValueError(f"invalid structure_split for {example.get('example_id')}: {value}")
    return value


def split_by_prefab_group(examples: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {"train": [], "validation": [], "test": []}
    for example in examples:
        group = str((example.get("split_group") or {}).get("prefab_group") or "")
        if not group:
            raise ValueError(f"prefab_group is missing: {example.get('example_id')}")
        split = _declared_split(example)
        if split is None:
            bucket = _split_bucket(group)
            split = "train" if bucket < 70 else "validation" if bucket < 85 else "test"
        result[split].append(example)
    for split in result:
        result[split].sort(key=lambda value: str(value["example_id"]))
    if not all(result.values()):
        raise ValueError(f"group split has an empty partition: { {key: len(value) for key, value in result.items()} }")
    groups = {split: {str((value.get("split_group") or {}).get("prefab_group")) for value in rows} for split, rows in result.items()}
    if groups["train"] & groups["validation"] or groups["train"] & groups["test"] or groups["validation"] & groups["test"]:
        raise ValueError("prefab group leakage across graph-model splits")
    return result


def build_vocabulary(examples: Iterable[dict[str, Any]]) -> dict[str, int]:
    tokens = sorted({str(token) for example in examples for token in example.get("tokens", []) if str(token)})
    return {token: index for index, token in enumerate([PAD_TOKEN, UNK_TOKEN, *tokens])}


def encode_examples(examples: Iterable[dict[str, Any]], vocabulary: dict[str, int]) -> list[tuple[str, list[int]]]:
    unknown = vocabulary[UNK_TOKEN]
    encoded: list[tuple[str, list[int]]] = []
    for example in examples:
        values = [vocabulary.get(str(token), unknown) for token in example.get("tokens", [])]
        if len(values) < 2:
            raise ValueError(f"PrefabGraph token sequence is too short: {example.get('example_id')}")
        encoded.append((str(example["example_id"]), values))
    return encoded


def window_examples_for_training(
    rows: Iterable[tuple[str, list[int]]],
    max_tokens: int = 512,
    overlap: int = 64,
) -> list[tuple[str, list[int]]]:
    """Split long token sequences after the structure split, preserving provenance in IDs."""
    if max_tokens < 2:
        raise ValueError("max_tokens must be at least 2")
    if overlap < 0 or overlap >= max_tokens:
        raise ValueError("window overlap must be non-negative and smaller than max_tokens")
    step = max_tokens - overlap
    windowed: list[tuple[str, list[int]]] = []
    for example_id, sequence in rows:
        if len(sequence) < 2:
            raise ValueError(f"PrefabGraph token sequence is too short: {example_id}")
        if len(sequence) <= max_tokens:
            windowed.append((example_id, sequence))
            continue
        start = 0
        window_index = 0
        while start < len(sequence) - 1:
            end = min(start + max_tokens, len(sequence))
            values = sequence[start:end]
            if len(values) >= 2:
                windowed.append((f"{example_id}::window_{window_index:04d}", values))
            if end == len(sequence):
                break
            start += step
            window_index += 1
    return windowed


def _bucketed_order(rows: list[Any], batch_size: int, seed: int, epoch: int, shuffle: bool) -> list[int]:
    order = list(range(len(rows)))
    if shuffle:
        random.Random(seed + epoch).shuffle(order)
    bucket_width = max(batch_size * 8, batch_size)
    grouped: list[int] = []
    for offset in range(0, len(order), bucket_width):
        bucket = order[offset:offset + bucket_width]
        bucket.sort(key=lambda index: len(rows[index][1]))
        grouped.extend(bucket)
    return grouped


def _batches(rows: list[tuple[str, list[int]]], batch_size: int, pad_id: int, seed: int, epoch: int, shuffle: bool) -> Iterable[tuple[Tensor, Tensor]]:
    order = _bucketed_order(rows, batch_size, seed, epoch, shuffle)
    for offset in range(0, len(order), batch_size):
        selected = [rows[index][1] for index in order[offset:offset + batch_size]]
        longest = max(len(value) - 1 for value in selected)
        inputs = torch.full((len(selected), longest), pad_id, dtype=torch.long)
        targets = torch.full((len(selected), longest), IGNORE_INDEX, dtype=torch.long)
        for row, values in enumerate(selected):
            width = len(values) - 1
            inputs[row, :width] = torch.tensor(values[:-1], dtype=torch.long)
            targets[row, :width] = torch.tensor(values[1:], dtype=torch.long)
        yield inputs, targets


class PrefabGraphNextTokenModel(nn.Module):
    def __init__(self, vocabulary_size: int, embedding_dim: int, hidden_dim: int, pad_id: int) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocabulary_size, embedding_dim, padding_idx=pad_id)
        self.gru = nn.GRU(embedding_dim, hidden_dim, batch_first=True)
        self.head = nn.Linear(hidden_dim, vocabulary_size)

    def forward(self, inputs: Tensor) -> Tensor:
        embedded = self.embedding(inputs)
        hidden, _ = self.gru(embedded)
        return self.head(hidden)


def _evaluate(model: nn.Module, rows: list[tuple[str, list[int]]], batch_size: int, pad_id: int, device: torch.device) -> dict[str, float]:
    model.eval()
    loss_sum = 0.0
    correct = 0
    count = 0
    criterion = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX, reduction="sum")
    with torch.inference_mode():
        for inputs, targets in _batches(rows, batch_size, pad_id, 0, 0, False):
            inputs, targets = inputs.to(device), targets.to(device)
            logits = model(inputs)
            loss_sum += float(criterion(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1)).item())
            valid = targets != IGNORE_INDEX
            prediction = logits.argmax(dim=-1)
            correct += int((prediction[valid] == targets[valid]).sum().item())
            count += int(valid.sum().item())
    return {
        "token_count": float(count),
        "cross_entropy": loss_sum / max(1, count),
        "perplexity": float(torch.exp(torch.tensor(loss_sum / max(1, count))).item()),
        "token_accuracy": correct / max(1, count),
    }


def _frequency_baseline(train_rows: list[tuple[str, list[int]]], evaluation_rows: list[tuple[str, list[int]]]) -> dict[str, float]:
    counts = Counter(token for _, sequence in train_rows for token in sequence[1:])
    total = sum(counts.values())
    vocabulary_size = max(1, len(counts))
    winner = counts.most_common(1)[0][0]
    correct = 0
    count = 0
    loss_sum = 0.0
    for _, sequence in evaluation_rows:
        for token in sequence[1:]:
            probability = (counts[token] + 1) / (total + vocabulary_size)
            loss_sum -= float(torch.log(torch.tensor(probability)).item())
            correct += int(token == winner)
            count += 1
    return {
        "token_count": float(count),
        "cross_entropy": loss_sum / max(1, count),
        "perplexity": float(torch.exp(torch.tensor(loss_sum / max(1, count))).item()),
        "token_accuracy": correct / max(1, count),
    }


def train_prefab_graph_model(
    dataset_root: Path,
    output_dir: Path,
    epochs: int = 30,
    batch_size: int = 16,
    embedding_dim: int = 64,
    hidden_dim: int = 128,
    learning_rate: float = 0.003,
    seed: int = 20260901,
    device_name: str = "auto",
    max_tokens: int = 512,
    window_overlap: int = 64,
) -> dict[str, Path]:
    dataset_root = dataset_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"model output already exists and is not empty: {output_dir}")
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    if manifest.get("schema_version") != "vfx_prefab_graph_training_dataset.v1" or manifest.get("status") != "pass":
        raise ValueError(f"verified PrefabGraph dataset expected: {dataset_root}")
    examples = _read_jsonl(dataset_root / "examples.jsonl")
    if len(examples) < 32:
        raise ValueError("at least 32 PrefabGraph examples are required for neural structure training")
    if any("aesthetic_preference" in value.get("eligible_tasks", []) for value in examples):
        raise ValueError("PrefabGraph structure model must not consume aesthetic preference labels")
    splits = split_by_prefab_group(examples)
    vocabulary = build_vocabulary(splits["train"])
    encoded_original = {name: encode_examples(values, vocabulary) for name, values in splits.items()}
    encoded = {
        name: window_examples_for_training(rows, max_tokens=max_tokens, overlap=window_overlap)
        for name, rows in encoded_original.items()
    }
    pad_id = vocabulary[PAD_TOKEN]
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model = PrefabGraphNextTokenModel(len(vocabulary), embedding_dim, hidden_dim, pad_id).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)
    history: list[dict[str, float]] = []
    best_state: dict[str, Tensor] | None = None
    best_validation = float("inf")
    for epoch in range(1, epochs + 1):
        model.train()
        loss_sum = 0.0
        batch_count = 0
        for inputs, targets in _batches(encoded["train"], batch_size, pad_id, seed, epoch, True):
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(inputs)
            loss = criterion(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            loss_sum += float(loss.item())
            batch_count += 1
        validation = _evaluate(model, encoded["validation"], batch_size, pad_id, device)
        history.append({"epoch": float(epoch), "train_cross_entropy": loss_sum / max(1, batch_count), **{f"validation_{key}": value for key, value in validation.items()}})
        if validation["cross_entropy"] < best_validation:
            best_validation = validation["cross_entropy"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError("PrefabGraph training did not produce a checkpoint")
    model.load_state_dict(best_state)
    metrics = {split: _evaluate(model, rows, batch_size, pad_id, device) for split, rows in encoded.items()}
    frequency = {split: _frequency_baseline(encoded["train"], rows) for split, rows in encoded.items()}
    test_improves_frequency = metrics["test"]["cross_entropy"] < frequency["test"]["cross_entropy"]
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "prefab_graph_next_token.pt"
    torch.save({
        "schema_version": MODEL_SCHEMA,
        "model_version": MODEL_VERSION,
        "state_dict": {key: value.cpu() for key, value in model.state_dict().items()},
        "vocabulary": vocabulary,
        "config": {"embedding_dim": embedding_dim, "hidden_dim": hidden_dim, "pad_id": pad_id},
    }, checkpoint_path)
    vocabulary_path = _write_json(output_dir / "vocabulary.json", {"schema_version": "vfx_prefab_graph_model_vocabulary.v1", "token_to_id": vocabulary})
    status = "experimental" if test_improves_frequency else "smoke_not_better_than_frequency"
    metrics_path = _write_json(output_dir / "metrics.json", {
        "schema_version": MODEL_SCHEMA,
        "model_version": MODEL_VERSION,
        "dataset_id": manifest["dataset_id"],
        "source_dataset_id": manifest["source_dataset_id"],
        "device": str(device),
        "epochs": epochs,
        "batch_size": batch_size,
        "max_tokens": max_tokens,
        "window_overlap": window_overlap,
        "windowed": True,
        "original_split_example_counts": {name: len(rows) for name, rows in splits.items()},
        "training_window_counts": {name: len(rows) for name, rows in encoded.items()},
        "long_original_sequence_counts": {name: sum(len(row[1]) > max_tokens for row in rows) for name, rows in encoded_original.items()},
        "training_view_id": manifest.get("dataset_id"),
        "split_example_counts": {name: len(rows) for name, rows in splits.items()},
        "split_window_counts": {name: len(rows) for name, rows in encoded.items()},
        "split_prefab_group_counts": {name: len({str((row.get("split_group") or {}).get("prefab_group")) for row in rows}) for name, rows in splits.items()},
        "metrics": metrics,
        "frequency_baseline": frequency,
        "test_improves_frequency_baseline": test_improves_frequency,
        "history": history,
        "training_scope": "PrefabGraph structure tokens only; no aesthetic labels, Prompt labels, or human preference labels were consumed.",
        "source_group_limitation": "The current corpus has one source_group, so source-group holdout is not available; Prefab group isolation is enforced.",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    card_path = _write_text(output_dir / "MODEL_CARD.md", f"""# PrefabGraph Next-Token Model

Status: `{status}`.

This is a PyTorch GRU that predicts the next deterministic `PrefabGraph` structure token. It is trained only on hierarchy, component and extracted particle-parameter tokens. It does not receive Prompt text, aesthetic scores, A/B labels, source Prefab paths, material paths, or texture paths.

Dataset: `{manifest['dataset_id']}` with structure-cluster-disjoint train/validation/test partitions. Long sequences are trained through overlapping windows (`max_tokens={max_tokens}`, `window_overlap={window_overlap}`) after splitting, so a long Prefab cannot leak across partitions and cannot force full-batch padding to its raw length.

The checkpoint cannot generate a complete Unity Prefab by itself. It is a structural prior for a later schema-constrained graph generator and Unity compiler.
""")
    return {"checkpoint": checkpoint_path, "vocabulary": vocabulary_path, "metrics": metrics_path, "model_card": card_path}


def predict_held_out_next_token(checkpoint_path: Path, dataset_root: Path, output_path: Path, prefix_token_count: int = 12, top_k: int = 8) -> Path:
    checkpoint_path = checkpoint_path.resolve()
    dataset_root = dataset_root.resolve()
    if output_path.exists():
        raise FileExistsError(f"prediction output already exists: {output_path}")
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if payload.get("schema_version") != MODEL_SCHEMA or payload.get("model_version") != MODEL_VERSION:
        raise ValueError(f"trusted PrefabGraph model checkpoint expected: {checkpoint_path}")
    vocabulary = payload.get("vocabulary")
    if not isinstance(vocabulary, dict) or PAD_TOKEN not in vocabulary or UNK_TOKEN not in vocabulary:
        raise ValueError("PrefabGraph model vocabulary is invalid")
    examples = _read_jsonl(dataset_root / "examples.jsonl")
    held_out = split_by_prefab_group(examples)["test"]
    example = held_out[0]
    sequence = [int(vocabulary.get(str(token), vocabulary[UNK_TOKEN])) for token in example["tokens"]]
    prefix_width = min(max(1, prefix_token_count), len(sequence) - 1)
    config = payload["config"]
    model = PrefabGraphNextTokenModel(len(vocabulary), int(config["embedding_dim"]), int(config["hidden_dim"]), int(config["pad_id"]))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    with torch.inference_mode():
        logits = model(torch.tensor([sequence[:prefix_width]], dtype=torch.long))[0, -1]
        probabilities = torch.softmax(logits, dim=-1)
        values, indices = torch.topk(probabilities, min(top_k, len(vocabulary)))
    reverse_vocabulary = {int(index): str(token) for token, index in vocabulary.items()}
    actual_id = sequence[prefix_width]
    ranked = [int(index) for index in indices.tolist()]
    result = {
        "schema_version": "vfx_prefab_graph_model_prediction.v1",
        "model_version": MODEL_VERSION,
        "checkpoint_path": checkpoint_path.as_posix(),
        "dataset_root": dataset_root.as_posix(),
        "split": "test",
        "source_example_id": example["example_id"],
        "source_prefab_group": (example.get("split_group") or {}).get("prefab_group"),
        "prefix_tokens": list(example["tokens"][:prefix_width]),
        "expected_next_token": reverse_vocabulary[actual_id],
        "expected_token_rank": ranked.index(actual_id) + 1 if actual_id in ranked else None,
        "predictions": [
            {"token": reverse_vocabulary[int(index)], "probability": float(value)}
            for value, index in zip(values.tolist(), indices.tolist())
        ],
        "training_scope": "Structure-token inference only. This is not Prompt conditioning, a Unity Prefab, or an aesthetic prediction.",
    }
    return _write_json(output_path.resolve(), result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a neural PrefabGraph next-token structure model.")
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--embedding-dim", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--window-overlap", type=int, default=64)
    parser.add_argument("--predict-checkpoint", type=Path)
    parser.add_argument("--predict-dataset-root", type=Path)
    parser.add_argument("--predict-output", type=Path)
    parser.add_argument("--prefix-token-count", type=int, default=12)
    parser.add_argument("--top-k", type=int, default=8)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.predict_checkpoint is not None or args.predict_dataset_root is not None or args.predict_output is not None:
            if args.predict_checkpoint is None or args.predict_dataset_root is None or args.predict_output is None:
                raise ValueError("prediction requires --predict-checkpoint, --predict-dataset-root, and --predict-output together")
            path = predict_held_out_next_token(args.predict_checkpoint, args.predict_dataset_root, args.predict_output, args.prefix_token_count, args.top_k)
            print(json.dumps({"success": True, "prediction": path.as_posix()}, ensure_ascii=False, indent=2))
            return 0
        if args.dataset_root is None or args.output_dir is None:
            raise ValueError("training requires --dataset-root and --output-dir")
        paths = train_prefab_graph_model(
            args.dataset_root, args.output_dir, args.epochs, args.batch_size,
            args.embedding_dim, args.hidden_dim, args.learning_rate, args.seed, args.device,
            args.max_tokens, args.window_overlap,
        )
    except (FileExistsError, FileNotFoundError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
