"""Compare PrefabGraph next-token checkpoints on one fixed leakage-aware view."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch

from .prefab_graph_model import (
    MODEL_SCHEMA,
    MODEL_VERSION,
    PAD_TOKEN,
    PrefabGraphNextTokenModel,
    _evaluate,
    _read_json,
    _read_jsonl,
    build_vocabulary,
    encode_examples,
    split_by_prefab_group,
    window_examples_for_training,
)


def _evaluate_checkpoint(checkpoint_path: Path, splits: dict[str, list[dict[str, Any]]], max_tokens: int, overlap: int) -> dict[str, Any]:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    if payload.get("schema_version") != MODEL_SCHEMA or payload.get("model_version") != MODEL_VERSION:
        raise ValueError(f"unsupported next-token checkpoint: {checkpoint_path}")
    vocabulary = payload.get("vocabulary")
    if not isinstance(vocabulary, dict) or PAD_TOKEN not in vocabulary:
        raise ValueError(f"checkpoint vocabulary is invalid: {checkpoint_path}")
    encoded = {
        split: window_examples_for_training(encode_examples(rows, vocabulary), max_tokens, overlap)
        for split, rows in splits.items()
    }
    config = payload["config"]
    model = PrefabGraphNextTokenModel(len(vocabulary), int(config["embedding_dim"]), int(config["hidden_dim"]), int(config["pad_id"]))
    model.load_state_dict(payload["state_dict"])
    return {
        "checkpoint_path": checkpoint_path.resolve().as_posix(),
        "model_version": payload.get("model_version"),
        "vocabulary_size": len(vocabulary),
        "metrics": {split: _evaluate(model, rows, 8, int(config["pad_id"]), torch.device("cpu")) for split, rows in encoded.items()},
        "window_counts": {split: len(rows) for split, rows in encoded.items()},
    }


def compare_checkpoints(dataset_root: Path, candidate_checkpoint: Path, baseline_checkpoint: Path, output_path: Path, max_tokens: int = 512, overlap: int = 64) -> Path:
    manifest = _read_json(dataset_root.resolve() / "dataset_manifest.json")
    if manifest.get("status") != "pass":
        raise ValueError(f"verified training view expected: {dataset_root}")
    splits = split_by_prefab_group(_read_jsonl(dataset_root.resolve() / "examples.jsonl"))
    candidate = _evaluate_checkpoint(candidate_checkpoint, splits, max_tokens, overlap)
    baseline = _evaluate_checkpoint(baseline_checkpoint, splits, max_tokens, overlap)
    comparison = {
        "schema_version": "vfx_prefab_graph_model_comparison.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": manifest["dataset_id"],
        "original_split_example_counts": {split: len(rows) for split, rows in splits.items()},
        "max_tokens": max_tokens,
        "window_overlap": overlap,
        "baseline": baseline,
        "candidate": candidate,
        "candidate_minus_baseline_test": {
            key: candidate["metrics"]["test"][key] - baseline["metrics"]["test"][key]
            for key in ("cross_entropy", "perplexity", "token_accuracy")
        },
        "comparison_scope": "Both checkpoints are evaluated on the same structure-cluster-disjoint full view after identical token-windowing. The baseline maps unseen full-view tokens to UNK; this is reported as a conservative compatibility baseline, not a retrained baseline.",
        "status": "pass",
    }
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two PrefabGraph next-token checkpoints on the same view.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--baseline-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--window-overlap", type=int, default=64)
    args = parser.parse_args(argv)
    try:
        path = compare_checkpoints(args.dataset_root, args.candidate_checkpoint, args.baseline_checkpoint, args.output, args.max_tokens, args.window_overlap)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "output": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
