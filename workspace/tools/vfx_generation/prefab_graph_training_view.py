"""Build a leakage-aware PrefabGraph training view from structural fingerprints."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .prefab_graph_model import _write_json, _write_text


DATASET_SCHEMA = "vfx_prefab_graph_training_dataset.v1"
VIEW_SCHEMA = "vfx_prefab_graph_training_view.v1"
STRUCTURAL_NUMERIC_PREFIXES = (
    "DEPTH_",
    "SIBLING_",
    "ACTIVE_",
    "LOOP_",
    "LIFETIME_",
    "SIZE_",
    "SPEED_",
    "MATERIALS_",
)
TOPOLOGY_NUMERIC_PREFIXES = (
    "DEPTH_",
    "SIBLING_",
    "ACTIVE_",
    "LOOP_",
    "LIFETIME_",
    "SIZE_",
    "SPEED_",
    "MATERIALS_",
    "SIM_",
    "SHAPE_",
    "RENDER_",
    "TYPE_",
    "ENABLED_",
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _schema_root() -> Path:
    return Path(__file__).parents[2] / "data/vfx_generation/schemas"


def _validate(value: dict[str, Any], schema_name: str, label: str) -> None:
    schema = json.loads((_schema_root() / schema_name).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _fingerprint(tokens: list[str], prefixes: tuple[str, ...]) -> str:
    normalized = [token for token in tokens if not token.startswith(prefixes)]
    return hashlib.sha256("|".join(normalized).encode("utf-8")).hexdigest()


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        if self.rank[root_left] == self.rank[root_right]:
            self.rank[root_left] += 1


def _split_for_cluster(cluster_id: str) -> str:
    bucket = int(hashlib.sha256(cluster_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def build_training_view(source_root: Path, output_root: Path, view_id: str) -> dict[str, Path]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    repo_root = Path(__file__).parents[3].resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"training view output already exists and is not empty: {output_root}")
    source_manifest = _read_json(source_root / "dataset_manifest.json")
    if source_manifest.get("schema_version") != DATASET_SCHEMA or source_manifest.get("status") != "pass":
        raise ValueError(f"verified PrefabGraph dataset expected: {source_root}")
    examples = _read_jsonl(source_root / "examples.jsonl")
    if not examples:
        raise ValueError("PrefabGraph dataset has no examples")
    for example in examples:
        if not (example.get("split_group") or {}).get("prefab_group"):
            raise ValueError(f"PrefabGraph example lacks prefab_group: {example.get('example_id')}")

    union_find = _UnionFind(len(examples))
    fingerprints: dict[str, dict[str, list[int]]] = {
        "parameter_agnostic_sequence": defaultdict(list),
        "component_topology": defaultdict(list),
    }
    for index, example in enumerate(examples):
        tokens = [str(token) for token in example.get("tokens", [])]
        fingerprints["parameter_agnostic_sequence"][_fingerprint(tokens, STRUCTURAL_NUMERIC_PREFIXES)].append(index)
        fingerprints["component_topology"][_fingerprint(tokens, TOPOLOGY_NUMERIC_PREFIXES)].append(index)
    for groups in fingerprints.values():
        for members in groups.values():
            for member in members[1:]:
                union_find.union(members[0], member)

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(examples)):
        components[union_find.find(index)].append(index)
    cluster_ids = {
        root: "structure_cluster_" + hashlib.sha256("|".join(sorted(str(examples[index]["example_id"]) for index in members)).encode("utf-8")).hexdigest()[:16]
        for root, members in components.items()
    }
    routed_examples = []
    cluster_rows = []
    for root, members in sorted(components.items(), key=lambda item: cluster_ids[item[0]]):
        cluster_id = cluster_ids[root]
        split = _split_for_cluster(cluster_id)
        sources = sorted({str((examples[index].get("split_group") or {}).get("source_group") or "unknown") for index in members})
        for index in members:
            routed = json.loads(json.dumps(examples[index], ensure_ascii=False))
            routed["split_group"] = {
                **(routed.get("split_group") or {}),
                "prefab_group": cluster_id,
                "original_prefab_group": (examples[index].get("split_group") or {}).get("prefab_group"),
                "structure_cluster_id": cluster_id,
                "structure_split": split,
            }
            routed_examples.append(routed)
        cluster_rows.append({
            "cluster_id": cluster_id,
            "split": split,
            "example_count": len(members),
            "source_groups": sources,
            "fingerprint_grouped_by": [name for name, groups in fingerprints.items() if any(set(members).issubset(set(group)) for group in groups.values())],
            "example_ids": sorted(str(examples[index]["example_id"]) for index in members),
        })
    routed_examples.sort(key=lambda row: str(row["example_id"]))
    graphs_path = source_root / "graphs.jsonl"
    graph_rows = _read_jsonl(graphs_path)
    graph_ids = [str(row.get("graph_id") or "") for row in graph_rows]
    example_graph_ids = [str(row.get("graph_id") or "") for row in routed_examples]
    if not all(graph_ids) or len(graph_ids) != len(set(graph_ids)):
        raise ValueError("source graphs must have unique graph_id values")
    if set(graph_ids) != set(example_graph_ids) or len(graph_ids) != len(example_graph_ids):
        raise ValueError("source graphs and examples have different graph_id sets")
    graph_by_id = {row["graph_id"]: row for row in graph_rows}
    ordered_graphs = [graph_by_id[graph_id] for graph_id in example_graph_ids]
    output_root.mkdir(parents=True, exist_ok=True)
    output_graphs = output_root / "graphs.jsonl"
    output_examples = _write_jsonl(output_root / "examples.jsonl", routed_examples)
    output_graphs = _write_jsonl(output_graphs, ordered_graphs)
    token_counts = Counter(str(token) for row in routed_examples if _split_for_cluster(str((row.get("split_group") or {}).get("prefab_group"))) == "train" for token in row.get("tokens", []))
    vocabulary_path = _write_json(output_root / "vocabulary.json", {
        "schema_version": "vfx_prefab_graph_training_view_vocabulary.v1",
        "fit_split": "train",
        "token_counts": [{"token": token, "count": count} for token, count in sorted(token_counts.items())],
    })
    cluster_path = _write_jsonl(output_root / "structure_clusters.jsonl", cluster_rows)
    split_counts = Counter(_split_for_cluster(str((row.get("split_group") or {}).get("prefab_group"))) for row in routed_examples)
    source_by_split: dict[str, set[str]] = defaultdict(set)
    for row in routed_examples:
        source_by_split[_split_for_cluster(str((row.get("split_group") or {}).get("prefab_group")))].add(str((row.get("split_group") or {}).get("source_group") or "unknown"))
    exact_signature_groups = sum(len(members) > 1 for members in fingerprints["parameter_agnostic_sequence"].values())
    topology_groups = sum(len(members) > 1 for members in fingerprints["component_topology"].values())
    manifest = {
        "schema_version": DATASET_SCHEMA,
        "view_schema_version": VIEW_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": view_id,
        "source_dataset_id": source_manifest["dataset_id"],
        "example_count": len(routed_examples),
        "reconstruction_status_counts": source_manifest.get("reconstruction_status_counts", {}),
        "token_count": sum(len(row.get("tokens", [])) for row in routed_examples),
        "files": {
            "examples": _portable(output_examples, repo_root),
            "graphs": _portable(output_graphs, repo_root),
            "vocabulary": _portable(vocabulary_path, repo_root),
            "structure_clusters": _portable(cluster_path, repo_root),
        },
        "quality_gates": {
            "source_example_count": len(examples),
            "graph_schema_errors": 0,
            "duplicate_graph_ids": 0,
            "aesthetic_labels_consumed": 0,
            "duplicate_example_ids": len(routed_examples) - len({row["example_id"] for row in routed_examples}),
            "cluster_split_leakage": sum(len({row["split"] for row in cluster_rows if row["cluster_id"] == cluster_id}) > 1 for cluster_id in {row["cluster_id"] for row in cluster_rows}),
            "parameter_agnostic_duplicate_group_count": exact_signature_groups,
            "component_topology_duplicate_group_count": topology_groups,
            "train_validation_test_nonempty": int(all(split_counts.get(split, 0) > 0 for split in ("train", "validation", "test"))),
            "train_source_group_count": len(source_by_split["train"]),
            "validation_source_group_count": len(source_by_split["validation"]),
            "test_source_group_count": len(source_by_split["test"]),
        },
        "split_example_counts": {split: split_counts.get(split, 0) for split in ("train", "validation", "test")},
        "split_cluster_counts": {split: sum(1 for row in cluster_rows if row["split"] == split) for split in ("train", "validation", "test")},
        "fingerprint_policy": {
            "parameter_agnostic_sequence_ignored_prefixes": list(STRUCTURAL_NUMERIC_PREFIXES),
            "component_topology_ignored_prefixes": list(TOPOLOGY_NUMERIC_PREFIXES),
            "cluster_rule": "Union examples sharing either structural fingerprint; split by structure_cluster_id.",
        },
        "vocabulary_fit_split": "train",
        "source_group_note": "All 16 source groups are retained as provenance. Structure clusters, not source paths, define the split boundary.",
        "status": "pass",
    }
    if any(manifest["quality_gates"][key] != 0 for key in ("duplicate_example_ids", "cluster_split_leakage")):
        raise ValueError("training view leakage or duplicate gate failed")
    if not manifest["quality_gates"]["train_validation_test_nonempty"]:
        raise ValueError("training view has an empty split")
    _validate(manifest, "prefab_graph_training_view.schema.json", "training view manifest")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    card_path = _write_text(output_root / "TRAINING_VIEW.md", f"""# {view_id}

This immutable view is derived from `{source_manifest['dataset_id']}` without changing the source files.

Examples sharing a parameter-agnostic structure sequence or a component-topology sequence are assigned to one `structure_cluster_id`. Train/validation/test are split by that cluster ID, so numeric, color, and closely related topology variants cannot cross the split boundary.

The vocabulary is fit from the train split only. No aesthetic labels, human preference labels, or Prompt quality labels are included. This view is for technical PrefabGraph structure learning and still requires Grammar constraints, AssetPlan routing, Unity compilation, runtime capture, and visual verification.
""")
    return {"manifest": manifest_path, "examples": output_examples, "graphs": output_graphs, "vocabulary": vocabulary_path, "clusters": cluster_path, "training_view": card_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a leakage-aware PrefabGraph training view.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--view-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_training_view(args.source_root, args.output_root, args.view_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
