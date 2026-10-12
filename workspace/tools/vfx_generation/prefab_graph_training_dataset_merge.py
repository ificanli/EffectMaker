"""Merge verified PrefabGraph sources into one leakage-safe training dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .prefab_graph import _schema_root, tokenize_prefab_graph


DATASET_SCHEMA = "vfx_prefab_graph_training_dataset.v1"
EXAMPLE_SCHEMA = "vfx_prefab_graph_training_example.v1"


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


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _validate_schema(schema_name: str, value: dict[str, Any], label: str) -> None:
    schema = _read_json(_schema_root() / schema_name)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _prefab_group(route: str, prefab_path: str) -> str:
    payload = f"{route}|{prefab_path}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _source_example(dataset_id: str, candidate: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate["candidate_id"])
    prefab_path = str(candidate["prefab_path"])
    return {
        "schema_version": EXAMPLE_SCHEMA,
        "example_id": f"{dataset_id}_{candidate_id}",
        "graph_id": str(graph["graph_id"]),
        "tokens": tokenize_prefab_graph(graph),
        "eligible_tasks": list(graph["training"]["eligible_tasks"]),
        "split_group": {
            "prefab_group": _prefab_group("unity_api_source_r003", prefab_path),
            "source_group": "TRN_FX_ALL_001",
        },
        "source_example_id": candidate_id,
    }


def merge_training_datasets(base_root: Path, source_export_root: Path, output_root: Path, dataset_id: str) -> dict[str, Path]:
    base_root = base_root.resolve()
    source_export_root = source_export_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"dataset output already exists and is not empty: {output_root}")

    base_manifest = _read_json(base_root / "dataset_manifest.json")
    if base_manifest.get("schema_version") != DATASET_SCHEMA or base_manifest.get("status") != "pass":
        raise ValueError(f"verified base PrefabGraph dataset expected: {base_root}")
    source_manifest = _read_json(source_export_root / "source_export_manifest.json")
    if source_manifest.get("status") != "pass":
        raise ValueError(f"verified source export manifest expected: {source_export_root}")
    if int(source_manifest.get("quality_gates", {}).get("aesthetic_labels_consumed", 1)) != 0:
        raise ValueError("source export contains aesthetic supervision")

    graph_validator = Draft202012Validator(_read_json(_schema_root() / "prefab_graph.schema.json"))
    base_graphs = _read_jsonl(base_root / "graphs.jsonl")
    base_examples = _read_jsonl(base_root / "examples.jsonl")
    graph_ids: set[str] = set()
    graphs: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    token_counts: Counter[str] = Counter()

    for graph in base_graphs:
        errors = list(graph_validator.iter_errors(graph))
        if errors:
            raise ValueError(f"base graph schema error: {errors[0].message}")
        graph_id = str(graph["graph_id"])
        if graph_id in graph_ids:
            raise ValueError(f"duplicate graph_id in base dataset: {graph_id}")
        graph_ids.add(graph_id)
        graphs.append(graph)

    base_example_ids = set()
    for example in base_examples:
        if str(example.get("graph_id")) not in graph_ids:
            raise ValueError(f"base example references missing graph: {example.get('example_id')}")
        example_id = str(example["example_id"])
        if example_id in base_example_ids:
            raise ValueError(f"duplicate example_id in base dataset: {example_id}")
        base_example_ids.add(example_id)
        examples.append(example)
        token_counts.update(str(token) for token in example.get("tokens", []))

    source_examples: list[dict[str, Any]] = []
    source_candidate_ids: set[str] = set()
    for candidate in source_manifest.get("candidates") or []:
        candidate_id = str(candidate["candidate_id"])
        if candidate_id in source_candidate_ids:
            raise ValueError(f"duplicate source candidate_id: {candidate_id}")
        source_candidate_ids.add(candidate_id)
        graph_path = _resolve_repo_path(str(candidate["graph_path"]))
        graph = _read_json(graph_path)
        errors = list(graph_validator.iter_errors(graph))
        if errors:
            raise ValueError(f"source graph schema error for {candidate_id}: {errors[0].message}")
        graph_id = str(graph["graph_id"])
        if graph_id in graph_ids:
            raise ValueError(f"duplicate graph_id across merged sources: {graph_id}")
        graph_ids.add(graph_id)
        graphs.append(graph)
        example = _source_example(dataset_id, candidate, graph)
        source_examples.append(example)
        token_counts.update(example["tokens"])

    examples.extend(source_examples)
    examples.sort(key=lambda value: str(value["example_id"]))
    graphs.sort(key=lambda value: str((value.get("source") or {}).get("source_example_id") or value["graph_id"]))
    if len(examples) != len(graphs):
        raise ValueError(f"merged graph/example count mismatch: {len(graphs)} != {len(examples)}")
    if len({str(example["graph_id"]) for example in examples}) != len(examples):
        raise ValueError("merged examples contain duplicate graph references")
    if any(example.get("eligible_tasks") and "aesthetic_preference" in example["eligible_tasks"] for example in examples):
        raise ValueError("aesthetic preference task leaked into structure dataset")

    graphs_path = _write_jsonl(output_root / "graphs.jsonl", graphs)
    examples_path = _write_jsonl(output_root / "examples.jsonl", examples)
    vocabulary_path = _write_json(output_root / "vocabulary.json", {
        "schema_version": "vfx_prefab_graph_vocabulary.v1",
        "tokens": [{"token": token, "count": count} for token, count in sorted(token_counts.items())],
    })
    manifest = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_dataset_id": f"{base_manifest['dataset_id']}+{source_manifest['source_dataset_id']}",
        "example_count": len(examples),
        "reconstruction_status_counts": dict(sorted(Counter(graph["reconstruction"]["status"] for graph in graphs).items())),
        "token_count": sum(token_counts.values()),
        "files": {
            "examples": _portable(examples_path),
            "graphs": _portable(graphs_path),
            "vocabulary": _portable(vocabulary_path),
        },
        "quality_gates": {
            "source_example_count": len(base_examples) + len(source_examples),
            "graph_schema_errors": 0,
            "duplicate_graph_ids": 0,
            "aesthetic_labels_consumed": 0,
        },
        "status": "pass",
    }
    _validate_schema("prefab_graph_training_dataset.schema.json", manifest, "merged PrefabGraph dataset")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {
        "dataset_manifest": manifest_path,
        "examples": examples_path,
        "graphs": graphs_path,
        "vocabulary": vocabulary_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge verified PrefabGraph training sources.")
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--source-export-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = merge_training_datasets(args.base_root, args.source_export_root, args.output_root, args.dataset_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
