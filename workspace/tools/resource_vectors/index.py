"""NumPy persistence and brute-force cosine search for image vectors."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np

from .query import is_within_root


class Encoder(Protocol):
    model_id: str
    revision: str

    def encode_images(self, paths: Sequence[Path]) -> np.ndarray: ...
    def encode_text(self, text: str) -> np.ndarray: ...


def normalize(vectors: np.ndarray) -> np.ndarray:
    values = np.asarray(vectors, dtype=np.float32)
    one_dimensional = values.ndim == 1
    matrix = values.reshape(1, -1) if one_dimensional else values
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("cannot normalize a zero vector")
    result = matrix / norms
    return result[0] if one_dimensional else result


def search_vectors(
    query: np.ndarray,
    vectors: np.ndarray,
    metadata: Sequence[dict[str, str]],
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Rank metadata by NumPy cosine similarity with deterministic tie-breaking."""
    matrix = normalize(np.asarray(vectors, dtype=np.float32))
    needle = normalize(np.asarray(query, dtype=np.float32))
    if matrix.ndim != 2 or matrix.shape[0] != len(metadata):
        raise ValueError("vector and metadata counts do not match")
    if matrix.shape[1] != needle.shape[0]:
        raise ValueError("query and index dimensions do not match")
    scores = matrix @ needle
    order = sorted(
        range(len(metadata)),
        key=lambda index: (-float(scores[index]), metadata[index]["asset_id"]),
    )
    return [
        {**metadata[index], "score": float(scores[index])}
        for index in order[:max(0, limit)]
    ]


def _paths(output: Path) -> tuple[Path, Path, Path]:
    return output / "vectors.npy", output / "metadata.jsonl", output / "manifest.json"


def load_vector_index(output: Path) -> tuple[np.ndarray, list[dict[str, str]], dict[str, object]]:
    vectors_path, metadata_path, manifest_path = _paths(Path(output))
    vectors = np.load(vectors_path, allow_pickle=False)
    metadata = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return vectors, metadata, manifest


def _previous(output: Path, encoder: Encoder) -> dict[str, np.ndarray]:
    try:
        vectors, metadata, manifest = load_vector_index(output)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if manifest.get("model_id") != encoder.model_id or manifest.get("revision") != encoder.revision:
        return {}
    return {row["sha256"]: vectors[index] for index, row in enumerate(metadata)}


def build_vector_index(
    sample: Sequence[dict[str, str]],
    root: Path,
    output: Path,
    encoder: Encoder,
) -> dict[str, object]:
    """Build an index, reusing vectors when content hash and model identity match."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output in root.parents or root in output.parents:
        raise ValueError("resource root and vector output must not overlap")
    output.mkdir(parents=True, exist_ok=True)
    resolved_paths = []
    for row in sample:
        candidate = (root / row["relative_path"]).resolve()
        if not is_within_root(candidate, root):
            raise ValueError(f"sample path is outside resource root: {row['relative_path']}")
        resolved_paths.append(candidate)
    previous = _previous(output, encoder)
    pending_indices = [index for index, row in enumerate(sample) if row["sha256"] not in previous]
    pending = [sample[index] for index in pending_indices]
    pending_paths = [resolved_paths[index] for index in pending_indices]
    fresh = normalize(encoder.encode_images(pending_paths)) if pending else np.empty((0, 0), dtype=np.float32)
    new_by_hash = {row["sha256"]: fresh[index] for index, row in enumerate(pending)}
    ordered_vectors = [previous.get(row["sha256"], new_by_hash.get(row["sha256"])) for row in sample]
    if not ordered_vectors:
        raise ValueError("sample is empty")
    vectors = np.asarray(ordered_vectors, dtype=np.float32)
    vectors_path, metadata_path, manifest_path = _paths(output)
    np.save(vectors_path, vectors, allow_pickle=False)
    with metadata_path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in sample:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "format_version": 1,
        "model_id": encoder.model_id,
        "revision": encoder.revision,
        "dimensions": int(vectors.shape[1]),
        "count": len(sample),
        "normalized": True,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {**manifest, "encoded": len(pending), "reused": len(sample) - len(pending), "output": str(output)}


def build_full_vector_index(
    records: Sequence[dict[str, str]],
    root: Path,
    output: Path,
    encoder: Encoder,
    *,
    batch_size: int = 32,
) -> dict[str, object]:
    """Build a resumable full index using bounded image batches."""
    if batch_size <= 0:
        raise ValueError("batch size must be positive")
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output in root.parents or root in output.parents:
        raise ValueError("resource root and vector output must not overlap")
    output.mkdir(parents=True, exist_ok=True)
    progress_path = output / "progress.jsonl"
    checkpoint = output / "checkpoint"
    identity_path = checkpoint / "identity.json"
    identity = {"model_id": encoder.model_id, "revision": encoder.revision}
    try:
        checkpoint_identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        checkpoint_identity = None
    if checkpoint_identity != identity:
        if checkpoint.is_dir():
            for path in checkpoint.glob("*.npy"):
                path.unlink()
        checkpoint.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(json.dumps(identity, sort_keys=True) + "\n", encoding="utf-8")
    previous: dict[str, tuple[dict[str, str], np.ndarray]] = {}
    try:
        vectors, metadata, manifest = load_vector_index(output)
        if manifest.get("model_id") == encoder.model_id and manifest.get("revision") == encoder.revision:
            previous = {row["sha256"]: (row, vectors[index]) for index, row in enumerate(metadata)}
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    for row in records:
        vector_path = checkpoint / f"{row['sha256']}.npy"
        if row["sha256"] not in previous and vector_path.is_file():
            try:
                previous[row["sha256"]] = (row, np.load(vector_path, allow_pickle=False))
            except (OSError, ValueError):
                pass

    successful: dict[str, tuple[dict[str, str], np.ndarray]] = dict(previous)
    failed: dict[str, str] = {}
    encoded = reused = batches = 0
    with progress_path.open("a", encoding="utf-8", newline="\n") as progress:
        for start in range(0, len(records), batch_size):
            batch = list(records[start:start + batch_size])
            pending = [row for row in batch if row["sha256"] not in successful]
            if not pending:
                reused += len(batch)
                continue
            batches += 1
            paths = []
            valid = []
            for row in pending:
                candidate = (root / row["relative_path"]).resolve()
                if not is_within_root(candidate, root):
                    failed[row["sha256"]] = "path outside resource root"
                elif not candidate.is_file():
                    failed[row["sha256"]] = "image file missing"
                else:
                    valid.append(row)
                    paths.append(candidate)
            vectors_batch = None
            if paths:
                try:
                    vectors_batch = normalize(encoder.encode_images(paths))
                    if len(vectors_batch) != len(valid):
                        raise ValueError("encoder returned an unexpected vector count")
                except Exception:
                    vectors_batch = None
            if vectors_batch is not None:
                for row, vector in zip(valid, vectors_batch):
                    successful[row["sha256"]] = (row, vector)
                    np.save(checkpoint / f"{row['sha256']}.npy", vector, allow_pickle=False)
                    encoded += 1
                    progress.write(json.dumps({"sha256": row["sha256"], "status": "indexed"}, sort_keys=True) + "\n")
            else:
                for row, path in zip(valid, paths):
                    try:
                        vector = normalize(encoder.encode_images([path]))
                        successful[row["sha256"]] = (row, vector)
                        encoded += 1
                        progress.write(json.dumps({"sha256": row["sha256"], "status": "indexed"}, sort_keys=True) + "\n")
                    except Exception as error:
                        failed[row["sha256"]] = str(error)
                        progress.write(json.dumps({"sha256": row["sha256"], "status": "failed", "error": str(error)}, sort_keys=True) + "\n")
            progress.flush()

    ordered = [successful[row["sha256"]] for row in records if row["sha256"] in successful]
    if ordered:
        vectors = np.asarray([item[1] for item in ordered], dtype=np.float32)
        metadata = [item[0] for item in ordered]
    else:
        vectors = np.empty((0, 0), dtype=np.float32)
        metadata = []
    vectors_path, metadata_path, manifest_path = _paths(output)
    np.save(vectors_path, vectors, allow_pickle=False)
    metadata_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in metadata), encoding="utf-8")
    manifest = {"format_version": 2, "model_id": encoder.model_id, "revision": encoder.revision, "dimensions": int(vectors.shape[1]) if vectors.ndim == 2 and vectors.shape[0] else 0, "count": len(metadata), "normalized": True, "built_at": datetime.now(timezone.utc).isoformat()}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {**manifest, "indexed": len(metadata), "encoded": encoded, "reused": reused, "failed": len(failed), "batches": batches, "output": str(output)}


__all__ = ["build_full_vector_index", "build_vector_index", "load_vector_index", "normalize", "search_vectors"]
