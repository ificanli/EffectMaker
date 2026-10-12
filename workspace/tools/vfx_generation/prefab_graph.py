"""Normalize Unity audit evidence into deterministic PrefabGraph training data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


GRAPH_SCHEMA = "vfx_prefab_graph.v1"
DATASET_SCHEMA = "vfx_prefab_graph_training_dataset.v1"
EXPORTER = "prefab_graph.v1"
_SEGMENT_PATTERN = re.compile(r"^(?P<name>.+)\[(?P<index>[0-9]+)\]$")
_STRUCTURAL_COMPONENTS = {
    "UnityEngine.Transform",
    "UnityEngine.RectTransform",
    "UnityEngine.ParticleSystem",
    "UnityEngine.ParticleSystemRenderer",
    "UnityEngine.MeshFilter",
    "UnityEngine.MeshRenderer",
    "UnityEngine.SkinnedMeshRenderer",
    "UnityEngine.Animator",
    "UnityEngine.Animation",
    "UnityEngine.Playables.PlayableDirector",
}


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _schema_root() -> Path:
    return Path(__file__).parents[2] / "data/vfx_generation/schemas"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_read_json(_schema_root() / name))


def _validate(validator: Draft202012Validator, value: dict[str, Any], label: str) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if not errors:
        return
    location = ".".join(str(part) for part in errors[0].path) or "<root>"
    raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def parse_hierarchy_path(path: str) -> list[tuple[str, int]]:
    normalized = _normalize_path(path)
    if not normalized:
        raise ValueError("hierarchy path is empty")
    result: list[tuple[str, int]] = []
    for segment in normalized.split("/"):
        match = _SEGMENT_PATTERN.fullmatch(segment)
        if match is None:
            raise ValueError(f"invalid hierarchy path segment: {segment}")
        result.append((match.group("name"), int(match.group("index"))))
    return result


def _transform(node: dict[str, Any]) -> dict[str, Any]:
    source = node.get("transform") if isinstance(node.get("transform"), dict) else node
    position = source.get("local_position")
    rotation = source.get("local_rotation")
    scale = source.get("local_scale")
    return {
        "local_position": list(position) if isinstance(position, list) and len(position) == 3 else None,
        "local_rotation": list(rotation) if isinstance(rotation, list) and len(rotation) == 4 else None,
        "local_scale": list(scale) if isinstance(scale, list) and len(scale) == 3 else None,
    }


def _component_parameters(source: dict[str, Any], omitted: set[str]) -> dict[str, Any]:
    return {key: source[key] for key in sorted(source) if key not in omitted}


def _paths(source: dict[str, Any], key: str) -> list[str]:
    values = source.get(key) if isinstance(source.get(key), list) else []
    return sorted({_normalize_path(str(value)) for value in values if str(value).strip()})


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _number_bucket(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        return "UNKNOWN"
    number = abs(float(value))
    if number == 0:
        return "ZERO"
    exponent = max(-4, min(14, math.floor(math.log2(number))))
    return f"LOG2_{exponent}"


def _enum_token(prefix: str, value: Any) -> str:
    text = re.sub(r"[^A-Z0-9]+", "_", str(value).upper()).strip("_") or "UNKNOWN"
    return f"{prefix}_{text}"


def tokenize_prefab_graph(graph: dict[str, Any]) -> list[str]:
    tokens = ["<PREFAB>", _enum_token("RECON", graph["reconstruction"]["status"])]
    particles_by_node: dict[str, list[dict[str, Any]]] = {}
    for particle in graph["components"]["particle_systems"]:
        particles_by_node.setdefault(particle["node_id"], []).append(particle)
    renderers_by_node: dict[str, list[dict[str, Any]]] = {}
    for renderer in graph["components"]["renderers"]:
        renderers_by_node.setdefault(renderer["node_id"], []).append(renderer)
    for node in graph["nodes"]:
        tokens.extend(["<NODE>", f"DEPTH_{node['depth']}", f"SIBLING_{min(node['sibling_index'], 15)}", f"ACTIVE_{int(node['active_self'])}"])
        if node.get("role"):
            tokens.append(_enum_token("ROLE", node["role"]))
        for component_type in node["component_types"]:
            tokens.append(_enum_token("COMP", component_type.rsplit(".", 1)[-1]))
        for particle in particles_by_node.get(node["node_id"], []):
            parameters = particle["parameters"]
            tokens.extend([
                "<PARTICLE>",
                _enum_token("SIM", parameters.get("simulation_space")),
                f"LOOP_{int(bool(parameters.get('looping')))}",
                _enum_token("SHAPE", parameters.get("shape_type")),
                _enum_token("RENDER", parameters.get("renderer_mode")),
                f"LIFETIME_{_number_bucket(parameters.get('start_lifetime_max'))}",
                f"SIZE_{_number_bucket(parameters.get('start_size_max'))}",
                f"SPEED_{_number_bucket(parameters.get('start_speed_max'))}",
                f"MATERIALS_{min(len(particle['material_paths']), 8)}",
                "</PARTICLE>",
            ])
        for renderer in renderers_by_node.get(node["node_id"], []):
            tokens.extend(["<RENDERER>", _enum_token("TYPE", renderer["renderer_type"]), f"ENABLED_{int(renderer['enabled'])}", "</RENDERER>"])
        tokens.append("</NODE>")
    tokens.append("</PREFAB>")
    return tokens


def assign_graph_id(graph_without_id: dict[str, Any]) -> dict[str, Any]:
    """Return a graph with a deterministic id without mutating the caller value."""
    payload = json.loads(json.dumps(graph_without_id, ensure_ascii=False))
    payload.pop("graph_id", None)
    return {"graph_id": f"pfg_{_canonical_hash(payload)[:20]}", **payload}


def build_prefab_graph(example: dict[str, Any], source_dataset_id: str) -> dict[str, Any]:
    outputs = example.get("outputs") if isinstance(example.get("outputs"), dict) else {}
    source_nodes = outputs.get("prefab_graph") if isinstance(outputs.get("prefab_graph"), list) else []
    if not source_nodes:
        raise ValueError(f"Prefab graph nodes are missing: {example.get('example_id')}")
    parsed: list[tuple[str, list[tuple[str, int]], dict[str, Any]]] = []
    seen_paths: set[str] = set()
    for source in source_nodes:
        path = _normalize_path(str(source.get("hierarchy_path") or ""))
        if path in seen_paths:
            raise ValueError(f"duplicate hierarchy path: {path}")
        seen_paths.add(path)
        parsed.append((path, parse_hierarchy_path(path), source))
    parsed.sort(key=lambda item: (len(item[1]), tuple((segment[1], segment[0]) for segment in item[1])))
    roots = [item for item in parsed if len(item[1]) == 1]
    if len(roots) != 1:
        raise ValueError(f"exactly one root node expected, found {len(roots)}")
    path_ids = {path: f"n{index:04d}" for index, (path, _, _) in enumerate(parsed)}
    nodes: list[dict[str, Any]] = []
    missing_fields: set[str] = set()
    unsupported: set[str] = set()
    for path, segments, source in parsed:
        parent_path = "/".join(path.split("/")[:-1])
        if len(segments) > 1 and parent_path not in path_ids:
            raise ValueError(f"parent hierarchy path is missing: {parent_path}")
        transform = _transform(source)
        if any(value is None for value in transform.values()):
            missing_fields.add("nodes[].transform")
        component_types = sorted({str(value) for value in source.get("component_types", []) if str(value)})
        transform_types = {"UnityEngine.Transform", "UnityEngine.RectTransform"}
        if not transform_types.intersection(component_types):
            raise ValueError(f"Transform or RectTransform component is missing: {path}")
        if "UnityEngine.RectTransform" in component_types:
            missing_fields.add("nodes[].rect_transform")
        unsupported.update(component for component in component_types if component not in _STRUCTURAL_COMPONENTS)
        nodes.append({
            "node_id": path_ids[path],
            "name": segments[-1][0],
            "sibling_index": segments[-1][1],
            "depth": len(segments) - 1,
            "parent_node_id": path_ids.get(parent_path),
            "hierarchy_path": path,
            "active_self": bool(source.get("active_self", True)),
            "component_types": component_types,
            "transform": transform,
        })
    particle_components: list[dict[str, Any]] = []
    for index, source in enumerate(outputs.get("particle_systems") or []):
        path = _normalize_path(str(source.get("hierarchy_path") or ""))
        if path not in path_ids:
            raise ValueError(f"ParticleSystem node path is missing: {path}")
        if not isinstance(source.get("serialized_modules"), dict):
            missing_fields.add("particle_systems[].serialized_modules")
        omitted = {"hierarchy_path", "material_paths", "mesh_paths"}
        particle_components.append({
            "component_id": f"p{index:04d}",
            "node_id": path_ids[path],
            "parameters": _component_parameters(source, omitted),
            "material_paths": _paths(source, "material_paths"),
            "mesh_paths": _paths(source, "mesh_paths"),
        })
    renderer_components: list[dict[str, Any]] = []
    for index, source in enumerate(outputs.get("renderers") or []):
        path = _normalize_path(str(source.get("hierarchy_path") or ""))
        if path not in path_ids:
            raise ValueError(f"Renderer node path is missing: {path}")
        omitted = {"hierarchy_path", "renderer_type", "enabled", "material_paths", "mesh_paths"}
        renderer_components.append({
            "component_id": f"r{index:04d}",
            "node_id": path_ids[path],
            "renderer_type": str(source.get("renderer_type") or "UnknownRenderer"),
            "enabled": bool(source.get("enabled", True)),
            "parameters": _component_parameters(source, omitted),
            "material_paths": _paths(source, "material_paths"),
            "mesh_paths": _paths(source, "mesh_paths"),
        })
    animation_components: list[dict[str, Any]] = []
    for index, source in enumerate(outputs.get("animations") or []):
        path = _normalize_path(str(source.get("hierarchy_path") or ""))
        if path not in path_ids:
            raise ValueError(f"Animation node path is missing: {path}")
        animation_type = str(source.get("animation_type") or source.get("component_type") or "UnknownAnimation")
        animation_components.append({
            "component_id": f"a{index:04d}",
            "node_id": path_ids[path],
            "animation_type": animation_type,
            "parameters": _component_parameters(source, {"hierarchy_path", "animation_type", "component_type"}),
        })
    all_components = [*particle_components, *renderer_components]
    material_paths = sorted({path for component in all_components for path in component["material_paths"]})
    mesh_paths = sorted({path for component in all_components for path in component["mesh_paths"]})
    reconstructable = not missing_fields and not unsupported
    eligible_tasks = ["hierarchy_modeling", "component_prediction"]
    if particle_components:
        eligible_tasks.append("particle_parameter_modeling")
    excluded_tasks = ["aesthetic_preference", "prompt_condition"]
    if reconstructable:
        eligible_tasks.append("full_reconstruction")
    else:
        excluded_tasks.append("full_reconstruction")
    graph_without_id = {
        "schema_version": GRAPH_SCHEMA,
        "source": {
            "source_kind": "unity_audit",
            "prefab_path": str(example.get("inputs", {}).get("prefab_path") or "") or None,
            "source_example_id": str(example.get("example_id") or "") or None,
        },
        "root_node_id": nodes[0]["node_id"],
        "nodes": nodes,
        "components": {
            "particle_systems": particle_components,
            "renderers": renderer_components,
            "animations": animation_components,
        },
        "asset_bindings": {"materials": material_paths, "meshes": mesh_paths},
        "reconstruction": {
            "status": "reconstructable" if reconstructable else "structure_only",
            "compiler_profile": "particle_v1" if reconstructable else "none",
            "missing_fields": sorted(missing_fields),
            "unsupported_components": sorted(unsupported),
        },
        "training": {
            "eligible_tasks": sorted(eligible_tasks),
            "excluded_tasks": sorted(excluded_tasks),
            "aesthetic_label_source": "none",
        },
        "provenance": {
            "source_dataset_id": source_dataset_id,
            "source_run_id": str(example.get("run_id") or "") or None,
            "exporter": EXPORTER,
            "assumptions": [
                "Unity audit values are technical structure supervision only.",
                "No human or AI aesthetic preference is consumed by this graph export.",
            ],
        },
    }
    return assign_graph_id(graph_without_id)


def export_prefab_graph_dataset(source_root: Path, output_root: Path, dataset_id: str) -> dict[str, Path]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"dataset output already exists and is not empty: {output_root}")
    source_manifest = _read_json(source_root / "dataset_manifest.json")
    source_dataset_id = str(source_manifest.get("dataset_id") or "")
    if not source_dataset_id or source_manifest.get("status") != "pass":
        raise ValueError(f"verified source dataset expected: {source_root}")
    source_examples = _read_jsonl(source_root / "examples.jsonl")
    graph_validator = _validator("prefab_graph.schema.json")
    graphs: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    vocabulary: Counter[str] = Counter()
    graph_ids: set[str] = set()
    for source in source_examples:
        graph = build_prefab_graph(source, source_dataset_id)
        _validate(graph_validator, graph, f"PrefabGraph {source.get('example_id')}")
        if graph["graph_id"] in graph_ids:
            raise ValueError(f"duplicate PrefabGraph id: {graph['graph_id']}")
        graph_ids.add(graph["graph_id"])
        tokens = tokenize_prefab_graph(graph)
        vocabulary.update(tokens)
        graphs.append(graph)
        examples.append({
            "schema_version": "vfx_prefab_graph_training_example.v1",
            "example_id": f"{dataset_id}_{source['candidate_id']}",
            "graph_id": graph["graph_id"],
            "tokens": tokens,
            "eligible_tasks": graph["training"]["eligible_tasks"],
            "split_group": source.get("split_group") or {},
            "source_example_id": source["example_id"],
        })
    examples.sort(key=lambda value: value["example_id"])
    graphs.sort(key=lambda value: value["source"]["source_example_id"] or "")
    graphs_path = _write_jsonl(output_root / "graphs.jsonl", graphs)
    examples_path = _write_jsonl(output_root / "examples.jsonl", examples)
    vocabulary_path = _write_json(output_root / "vocabulary.json", {
        "schema_version": "vfx_prefab_graph_vocabulary.v1",
        "tokens": [{"token": token, "count": count} for token, count in sorted(vocabulary.items())],
    })
    manifest = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_dataset_id": source_dataset_id,
        "example_count": len(examples),
        "reconstruction_status_counts": dict(sorted(Counter(graph["reconstruction"]["status"] for graph in graphs).items())),
        "token_count": sum(vocabulary.values()),
        "files": {
            "examples": _portable(examples_path),
            "graphs": _portable(graphs_path),
            "vocabulary": _portable(vocabulary_path),
        },
        "quality_gates": {
            "source_example_count": len(source_examples),
            "graph_schema_errors": 0,
            "duplicate_graph_ids": 0,
            "aesthetic_labels_consumed": 0,
        },
        "status": "pass",
    }
    _validate(_validator("prefab_graph_training_dataset.schema.json"), manifest, "PrefabGraph dataset manifest")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {"dataset_manifest": manifest_path, "examples": examples_path, "graphs": graphs_path, "vocabulary": vocabulary_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export deterministic PrefabGraph structure training data.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = export_prefab_graph_dataset(args.source_root, args.output_root, args.dataset_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
