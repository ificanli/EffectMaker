"""Train shared neural structure tasks for verified PrefabGraph sequences."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import torch
from torch import Tensor, nn

from .prefab_graph_model import (
    IGNORE_INDEX,
    PAD_TOKEN,
    UNK_TOKEN,
    _frequency_baseline,
    _read_jsonl,
    _bucketed_order,
    split_by_prefab_group,
    window_examples_for_training,
)


MODEL_SCHEMA = "vfx_prefab_graph_multitask_model.v1"
MODEL_VERSION = "prefab_graph_gru_multitask.v1"
MASK_TOKEN = "<MASK_COMPONENT>"
AE_BOS_TOKEN = "<AE_BOS>"
AE_EOS_TOKEN = "<AE_EOS>"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _read_examples(dataset_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    if manifest.get("schema_version") != "vfx_prefab_graph_training_dataset.v1" or manifest.get("status") != "pass":
        raise ValueError(f"verified PrefabGraph dataset expected: {dataset_root}")
    examples = _read_jsonl(dataset_root / "examples.jsonl")
    if len(examples) < 32:
        raise ValueError("at least 32 PrefabGraph examples are required for multitask training")
    if any("aesthetic_preference" in value.get("eligible_tasks", []) for value in examples):
        raise ValueError("structure model must not consume aesthetic preference labels")
    return manifest, examples


def build_multitask_vocabulary(examples: Iterable[dict[str, Any]]) -> dict[str, int]:
    tokens = {str(token) for example in examples for token in example.get("tokens", []) if str(token)}
    tokens.update({MASK_TOKEN, AE_BOS_TOKEN, AE_EOS_TOKEN})
    ordered = [PAD_TOKEN, UNK_TOKEN, MASK_TOKEN, AE_BOS_TOKEN, AE_EOS_TOKEN, *sorted(tokens - {MASK_TOKEN, AE_BOS_TOKEN, AE_EOS_TOKEN})]
    return {token: index for index, token in enumerate(ordered)}


def _encode_examples(examples: Iterable[dict[str, Any]], vocabulary: dict[str, int]) -> list[tuple[str, list[int], list[str]]]:
    unknown = vocabulary[UNK_TOKEN]
    encoded: list[tuple[str, list[int], list[str]]] = []
    for example in examples:
        tokens = [str(token) for token in example.get("tokens", [])]
        values = [vocabulary.get(token, unknown) for token in tokens]
        if len(values) < 2:
            raise ValueError(f"PrefabGraph token sequence is too short: {example.get('example_id')}")
        encoded.append((str(example["example_id"]), values, tokens))
    return encoded


def _pad_sequences(sequences: list[list[int]], pad_id: int) -> tuple[Tensor, Tensor]:
    if not sequences:
        raise ValueError("cannot pad an empty sequence batch")
    width = max(len(sequence) for sequence in sequences)
    values = torch.full((len(sequences), width), pad_id, dtype=torch.long)
    lengths = torch.tensor([len(sequence) for sequence in sequences], dtype=torch.long)
    for index, sequence in enumerate(sequences):
        values[index, :len(sequence)] = torch.tensor(sequence, dtype=torch.long)
    return values, lengths


def _next_batches(rows: list[tuple[str, list[int], list[str]]], batch_size: int, pad_id: int, seed: int, epoch: int, shuffle: bool) -> list[tuple[Tensor, Tensor, Tensor]]:
    order = _bucketed_order(rows, batch_size, seed, epoch, shuffle)
    batches: list[tuple[Tensor, Tensor, Tensor]] = []
    for offset in range(0, len(order), batch_size):
        selected = [rows[index][1] for index in order[offset:offset + batch_size]]
        inputs, lengths = _pad_sequences([sequence[:-1] for sequence in selected], pad_id)
        targets, _ = _pad_sequences([sequence[1:] for sequence in selected], IGNORE_INDEX)
        targets[inputs == pad_id] = IGNORE_INDEX
        batches.append((inputs, targets, lengths))
    return batches


def _masked_component_rows(rows: list[tuple[str, list[int], list[str]]]) -> list[tuple[list[int], int, str]]:
    masked: list[tuple[list[int], int, str]] = []
    for _, values, tokens in rows:
        for position, token in enumerate(tokens):
            if token.startswith("COMP_"):
                masked.append((values, position, token))
    return masked


def _sample_masked_component_rows(rows: list[tuple[str, list[int], list[str]]], seed: int, epoch: int) -> list[tuple[list[int], int, str]]:
    """Sample one component target per Prefab for efficient per-epoch training."""
    rng = random.Random(seed * 7 + epoch)
    sampled: list[tuple[list[int], int, str]] = []
    for _, values, tokens in rows:
        candidates = [(values, position, token) for position, token in enumerate(tokens) if token.startswith("COMP_")]
        if candidates:
            sampled.append(rng.choice(candidates))
    return sampled


def _masked_batches(masked_rows: list[tuple[list[int], int, str]], batch_size: int, vocabulary: dict[str, int], seed: int, epoch: int, shuffle: bool) -> list[tuple[Tensor, Tensor, Tensor]]:
    order = list(range(len(masked_rows)))
    if shuffle:
        random.Random(seed * 3 + epoch).shuffle(order)
    bucket_width = max(batch_size * 8, batch_size)
    bucketed: list[int] = []
    for offset in range(0, len(order), bucket_width):
        bucket = order[offset:offset + bucket_width]
        bucket.sort(key=lambda index: len(masked_rows[index][0]))
        bucketed.extend(bucket)
    order = bucketed
    pad_id = vocabulary[PAD_TOKEN]
    mask_id = vocabulary[MASK_TOKEN]
    batches: list[tuple[Tensor, Tensor, Tensor]] = []
    for offset in range(0, len(order), batch_size):
        selected = [masked_rows[index] for index in order[offset:offset + batch_size]]
        values = [list(row[0]) for row in selected]
        positions = torch.tensor([row[1] for row in selected], dtype=torch.long)
        targets = torch.tensor([vocabulary.get(row[2], vocabulary[UNK_TOKEN]) for row in selected], dtype=torch.long)
        inputs, lengths = _pad_sequences(values, pad_id)
        inputs[torch.arange(len(selected)), positions] = mask_id
        batches.append((inputs, positions, targets))
    return batches


def _reconstruction_batches(rows: list[tuple[str, list[int], list[str]]], batch_size: int, vocabulary: dict[str, int], seed: int, epoch: int, shuffle: bool) -> list[tuple[Tensor, Tensor, Tensor, Tensor]]:
    order = _bucketed_order(rows, batch_size, seed * 5, epoch, shuffle)
    pad_id = vocabulary[PAD_TOKEN]
    bos_id = vocabulary[AE_BOS_TOKEN]
    eos_id = vocabulary[AE_EOS_TOKEN]
    batches: list[tuple[Tensor, Tensor, Tensor, Tensor]] = []
    for offset in range(0, len(order), batch_size):
        selected = [rows[index][1] for index in order[offset:offset + batch_size]]
        source, source_lengths = _pad_sequences(selected, pad_id)
        decoder_inputs, _ = _pad_sequences([[bos_id, *sequence] for sequence in selected], pad_id)
        targets, _ = _pad_sequences([[*sequence, eos_id] for sequence in selected], IGNORE_INDEX)
        batches.append((source, source_lengths, decoder_inputs, targets))
    return batches


class PrefabGraphMultiTaskModel(nn.Module):
    def __init__(self, vocabulary_size: int, embedding_dim: int, hidden_dim: int, pad_id: int) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocabulary_size, embedding_dim, padding_idx=pad_id)
        self.encoder = nn.GRU(embedding_dim, hidden_dim, batch_first=True)
        self.decoder = nn.GRU(embedding_dim, hidden_dim, batch_first=True)
        self.next_head = nn.Linear(hidden_dim, vocabulary_size)
        self.masked_component_head = nn.Linear(hidden_dim, vocabulary_size)
        self.reconstruction_head = nn.Linear(hidden_dim, vocabulary_size)

    def encode(self, inputs: Tensor, lengths: Tensor | None = None) -> tuple[Tensor, Tensor]:
        output, _ = self.encoder(self.embedding(inputs))
        if lengths is None:
            lengths = torch.full((inputs.shape[0],), inputs.shape[1], dtype=torch.long, device=inputs.device)
        last = output[torch.arange(inputs.shape[0], device=inputs.device), lengths.to(inputs.device) - 1]
        return output, last

    def next_token(self, inputs: Tensor, lengths: Tensor | None = None) -> Tensor:
        output, _ = self.encode(inputs, lengths)
        return self.next_head(output)

    def masked_component(self, inputs: Tensor, positions: Tensor) -> Tensor:
        output, _ = self.encode(inputs)
        return self.masked_component_head(output[torch.arange(inputs.shape[0], device=inputs.device), positions.to(inputs.device)])

    def reconstruct(self, inputs: Tensor, lengths: Tensor, decoder_inputs: Tensor) -> Tensor:
        _, latent = self.encode(inputs, lengths)
        decoded, _ = self.decoder(self.embedding(decoder_inputs), latent.unsqueeze(0))
        return self.reconstruction_head(decoded)


def _evaluate_next(model: PrefabGraphMultiTaskModel, rows: list[tuple[str, list[int], list[str]]], batch_size: int, pad_id: int, device: torch.device) -> dict[str, float]:
    model.eval()
    criterion = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX, reduction="sum")
    loss_sum = 0.0
    correct = 0
    count = 0
    with torch.inference_mode():
        for inputs, targets, lengths in _next_batches(rows, batch_size, pad_id, 0, 0, False):
            inputs, targets, lengths = inputs.to(device), targets.to(device), lengths.to(device)
            logits = model.next_token(inputs, lengths)
            loss_sum += float(criterion(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1)).item())
            valid = targets != IGNORE_INDEX
            correct += int((logits.argmax(dim=-1)[valid] == targets[valid]).sum().item())
            count += int(valid.sum().item())
    cross_entropy = loss_sum / max(1, count)
    return {"token_count": float(count), "cross_entropy": cross_entropy, "perplexity": float(torch.exp(torch.tensor(cross_entropy)).item()), "token_accuracy": correct / max(1, count)}


def _evaluate_masked(model: PrefabGraphMultiTaskModel, masked_rows: list[tuple[list[int], int, str]], vocabulary: dict[str, int], batch_size: int, device: torch.device) -> dict[str, float]:
    model.eval()
    criterion = nn.CrossEntropyLoss(reduction="sum")
    loss_sum = 0.0
    correct = 0
    count = 0
    with torch.inference_mode():
        for inputs, positions, targets in _masked_batches(masked_rows, batch_size, vocabulary, 0, 0, False):
            inputs, positions, targets = inputs.to(device), positions.to(device), targets.to(device)
            logits = model.masked_component(inputs, positions)
            loss_sum += float(criterion(logits, targets).item())
            correct += int((logits.argmax(dim=-1) == targets).sum().item())
            count += int(targets.shape[0])
    cross_entropy = loss_sum / max(1, count)
    return {"masked_component_count": float(count), "cross_entropy": cross_entropy, "perplexity": float(torch.exp(torch.tensor(cross_entropy)).item()), "accuracy": correct / max(1, count)}


def _greedy_reconstruct(model: PrefabGraphMultiTaskModel, sequence: list[int], vocabulary: dict[str, int], device: torch.device) -> list[int]:
    pad_id = vocabulary[PAD_TOKEN]
    bos_id = vocabulary[AE_BOS_TOKEN]
    eos_id = vocabulary[AE_EOS_TOKEN]
    source = torch.tensor([sequence], dtype=torch.long, device=device)
    lengths = torch.tensor([len(sequence)], dtype=torch.long, device=device)
    with torch.inference_mode():
        _, latent = model.encode(source, lengths)
        hidden = latent.unsqueeze(0)
        current = torch.tensor([[bos_id]], dtype=torch.long, device=device)
        output: list[int] = []
        for _ in range(len(sequence) + 2):
            decoded, hidden = model.decoder(model.embedding(current), hidden)
            next_id = int(model.reconstruction_head(decoded[:, -1]).argmax(dim=-1).item())
            if next_id == eos_id or next_id == pad_id:
                break
            output.append(next_id)
            current = torch.tensor([[next_id]], dtype=torch.long, device=device)
        return output


def _evaluate_reconstruction(model: PrefabGraphMultiTaskModel, rows: list[tuple[str, list[int], list[str]]], vocabulary: dict[str, int], batch_size: int, device: torch.device, greedy: bool = True) -> dict[str, float]:
    model.eval()
    criterion = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX, reduction="sum")
    loss_sum = 0.0
    count = 0
    exact = 0
    token_correct = 0
    token_total = 0
    for source, source_lengths, decoder_inputs, targets in _reconstruction_batches(rows, batch_size, vocabulary, 0, 0, False):
        source, source_lengths, decoder_inputs, targets = source.to(device), source_lengths.to(device), decoder_inputs.to(device), targets.to(device)
        with torch.inference_mode():
            logits = model.reconstruct(source, source_lengths, decoder_inputs)
        loss_sum += float(criterion(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1)).item())
        count += int((targets != IGNORE_INDEX).sum().item())
    if greedy:
        for _, sequence, _ in rows:
            predicted = _greedy_reconstruct(model, sequence, vocabulary, device)
            exact += int(predicted == sequence)
            width = min(len(predicted), len(sequence))
            token_correct += sum(int(predicted[index] == sequence[index]) for index in range(width))
            token_total += len(sequence)
    cross_entropy = loss_sum / max(1, count)
    return {"sequence_count": float(len(rows)), "cross_entropy": cross_entropy, "perplexity": float(torch.exp(torch.tensor(cross_entropy)).item()), "exact_match_rate": exact / max(1, len(rows)), "token_accuracy": token_correct / max(1, token_total)}


def train_multitask_model(
    dataset_root: Path,
    output_dir: Path,
    epochs: int = 12,
    batch_size: int = 16,
    embedding_dim: int = 64,
    hidden_dim: int = 128,
    learning_rate: float = 0.002,
    seed: int = 20260902,
    device_name: str = "auto",
    max_tokens: int = 512,
    window_overlap: int = 64,
) -> dict[str, Path]:
    dataset_root = dataset_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"model output already exists and is not empty: {output_dir}")
    manifest, examples = _read_examples(dataset_root)
    splits = split_by_prefab_group(examples)
    vocabulary = build_multitask_vocabulary(splits["train"])
    encoded_original = {name: _encode_examples(values, vocabulary) for name, values in splits.items()}
    encoded = {}
    for name, rows in encoded_original.items():
        windowed_rows: list[tuple[str, list[int], list[str]]] = []
        for row_id, values, tokens in rows:
            for window_id, window_values in window_examples_for_training([(row_id, values)], max_tokens, window_overlap):
                if window_id == row_id:
                    window_tokens = tokens
                else:
                    start = int(window_id.rsplit("_", 1)[-1]) * (max_tokens - window_overlap)
                    window_tokens = tokens[start:start + len(window_values)]
                windowed_rows.append((window_id, window_values, window_tokens))
        encoded[name] = windowed_rows
    masked = {name: _masked_component_rows(values) for name, values in encoded.items()}
    if not all(masked.values()):
        raise ValueError("each split needs at least one component mask target")
    pad_id = vocabulary[PAD_TOKEN]
    device = torch.device("cuda" if device_name == "auto" and torch.cuda.is_available() else device_name if device_name != "auto" else "cpu")
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model = PrefabGraphMultiTaskModel(len(vocabulary), embedding_dim, hidden_dim, pad_id).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    next_criterion = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)
    masked_criterion = nn.CrossEntropyLoss()
    reconstruction_criterion = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)
    history: list[dict[str, float]] = []
    best_state: dict[str, Tensor] | None = None
    best_validation = float("inf")
    for epoch in range(1, epochs + 1):
        model.train()
        next_epoch = _next_batches(encoded["train"], batch_size, pad_id, seed, epoch, True)
        masked_epoch = _masked_batches(_sample_masked_component_rows(encoded["train"], seed, epoch), batch_size, vocabulary, seed, epoch, True)
        reconstruction_epoch = _reconstruction_batches(encoded["train"], batch_size, vocabulary, seed, epoch, True)
        steps = max(len(next_epoch), len(masked_epoch), len(reconstruction_epoch))
        train_loss = 0.0
        for step in range(steps):
            optimizer.zero_grad(set_to_none=True)
            total_loss = torch.zeros((), device=device)
            if next_epoch:
                inputs, targets, lengths = next_epoch[step % len(next_epoch)]
                inputs, targets, lengths = inputs.to(device), targets.to(device), lengths.to(device)
                logits = model.next_token(inputs, lengths)
                total_loss = total_loss + next_criterion(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1))
            if masked_epoch:
                inputs, positions, targets = masked_epoch[step % len(masked_epoch)]
                inputs, positions, targets = inputs.to(device), positions.to(device), targets.to(device)
                total_loss = total_loss + masked_criterion(model.masked_component(inputs, positions), targets)
            if reconstruction_epoch:
                source, source_lengths, decoder_inputs, targets = reconstruction_epoch[step % len(reconstruction_epoch)]
                source, source_lengths, decoder_inputs, targets = source.to(device), source_lengths.to(device), decoder_inputs.to(device), targets.to(device)
                logits = model.reconstruct(source, source_lengths, decoder_inputs)
                total_loss = total_loss + 0.5 * reconstruction_criterion(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1))
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += float(total_loss.item())
        validation_next = _evaluate_next(model, encoded["validation"], batch_size, pad_id, device)
        validation_masked = _evaluate_masked(model, masked["validation"], vocabulary, batch_size, device)
        validation_reconstruction = _evaluate_reconstruction(model, encoded["validation"], vocabulary, batch_size, device, greedy=False)
        validation_score = validation_next["cross_entropy"] + validation_masked["cross_entropy"] + validation_reconstruction["cross_entropy"]
        history.append({
            "epoch": float(epoch),
            "train_loss": train_loss / max(1, steps),
            "validation_next_cross_entropy": validation_next["cross_entropy"],
            "validation_masked_cross_entropy": validation_masked["cross_entropy"],
            "validation_reconstruction_cross_entropy": validation_reconstruction["cross_entropy"],
        })
        if validation_score < best_validation:
            best_validation = validation_score
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError("multitask training did not produce a checkpoint")
    model.load_state_dict(best_state)
    metrics = {
        split: {
            "next_token": _evaluate_next(model, encoded[split], batch_size, pad_id, device),
            "masked_component": _evaluate_masked(model, masked[split], vocabulary, batch_size, device),
            "structure_reconstruction": _evaluate_reconstruction(model, encoded[split], vocabulary, batch_size, device),
        }
        for split in ("train", "validation", "test")
    }
    frequency = {split: _frequency_baseline([(row[0], row[1]) for row in encoded["train"]], [(row[0], row[1]) for row in encoded[split]]) for split in ("train", "validation", "test")}
    test_improves_frequency = metrics["test"]["next_token"]["cross_entropy"] < frequency["test"]["cross_entropy"]
    status = "experimental" if test_improves_frequency else "smoke_not_better_than_frequency"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "prefab_graph_multitask.pt"
    torch.save({
        "schema_version": MODEL_SCHEMA,
        "model_version": MODEL_VERSION,
        "state_dict": {key: value.cpu() for key, value in model.state_dict().items()},
        "vocabulary": vocabulary,
        "config": {"embedding_dim": embedding_dim, "hidden_dim": hidden_dim, "pad_id": pad_id},
        "special_tokens": {"mask": MASK_TOKEN, "autoencoder_bos": AE_BOS_TOKEN, "autoencoder_eos": AE_EOS_TOKEN},
    }, checkpoint_path)
    vocabulary_path = _write_json(output_dir / "vocabulary.json", {"schema_version": "vfx_prefab_graph_multitask_vocabulary.v1", "token_to_id": vocabulary})
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
        "vocabulary_size": len(vocabulary),
        "metrics": metrics,
        "frequency_baseline": frequency,
        "test_improves_frequency_baseline": test_improves_frequency,
        "history": history,
        "training_scope": "Shared technical PrefabGraph encoder with next-token, masked component and denoising-free sequence reconstruction tasks; no Prompt, aesthetic or human preference labels were consumed.",
        "source_group_note": "Source group remains provenance metadata; split isolation is enforced by prefab_group and is not an aesthetic generalization claim.",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    card_path = _write_text(output_dir / "MODEL_CARD.md", f"""# PrefabGraph Multitask Structure Model

Status: `{status}`.

This PyTorch GRU shares an encoder across three technical tasks:

- next-token prediction for deterministic PrefabGraph sequences;
- masked component recovery for `COMP_*` tokens;
- sequence reconstruction from an encoded structure representation.

Dataset: `{manifest['dataset_id']}`. Train, validation and test partitions are disjoint by `structure_cluster_id` (also routed through `prefab_group`). The source graphs retain their source Prefab, material, Shader, texture and Mesh provenance inside the Graph, but those paths are not model tokens and are not aesthetic supervision.

Long sequences are trained through overlapping windows (`max_tokens={max_tokens}`, `window_overlap={window_overlap}`) after the structure split. Window metrics are reported separately from original Prefab counts.

This is an experimental structure model. It cannot generate a complete high-quality Unity Prefab from Prompt text, cannot synthesize Mesh, texture or Shader assets, and does not make an aesthetic judgment. Its output still requires Grammar constraints, AssetPlan routing, Unity compilation, runtime capture and visual review.
""")
    return {"checkpoint": checkpoint_path, "vocabulary": vocabulary_path, "metrics": metrics_path, "model_card": card_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a multitask PrefabGraph structure model.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--embedding-dim", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.002)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--window-overlap", type=int, default=64)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = train_multitask_model(args.dataset_root, args.output_dir, args.epochs, args.batch_size, args.embedding_dim, args.hidden_dim, args.learning_rate, args.seed, args.device, args.max_tokens, args.window_overlap)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
