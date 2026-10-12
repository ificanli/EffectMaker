"""Build an all-Assets technical corpus and PrefabGraph dataset from Unity API audit evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .prefab_graph import build_prefab_graph, tokenize_prefab_graph


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _schema_root() -> Path:
    return _repo_root() / "workspace/data/vfx_generation/schemas"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


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


def _validate(name: str, value: dict[str, Any], label: str) -> None:
    schema = _read_json(_schema_root() / name)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _stable_id(prefix: str, *values: str) -> str:
    return f"{prefix}_" + hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:20]


def _source_group(prefab_path: str) -> str:
    parts = prefab_path.replace("\\", "/").split("/")
    return parts[1] if len(parts) > 2 else "Assets"


def _graph_example(record: dict[str, Any], baseline_id: str) -> dict[str, Any]:
    prefab_path = str(record["prefab_path"])
    prefab_id = _stable_id("prefab", prefab_path)
    animations = []
    for animation in record.get("animations") or []:
        animations.append({
            "hierarchy_path": animation.get("hierarchy_path"),
            "animation_type": animation.get("source_type") or "UnknownAnimation",
            "clip_name": animation.get("clip_name") or "",
            "duration_seconds": animation.get("duration_seconds") or 0.0,
            "looping": bool(animation.get("looping")),
        })
    return {
        "example_id": f"{baseline_id}_{prefab_id}",
        "run_id": baseline_id,
        "candidate_id": prefab_id,
        "inputs": {"prefab_path": prefab_path},
        "outputs": {
            "prefab_graph": record.get("nodes") or [],
            "particle_systems": record.get("particle_systems") or [],
            "renderers": record.get("renderers") or [],
            "animations": animations,
        },
        "split_group": {
            "prefab_group": hashlib.sha1(prefab_path.encode("utf-8")).hexdigest()[:12],
            "source_group": _source_group(prefab_path),
        },
    }


def build_full_prefab_baseline(audit_path: Path, unity_project: Path, output_root: Path, baseline_id: str) -> dict[str, Path]:
    audit_path, unity_project, output_root = audit_path.resolve(), unity_project.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"full Prefab baseline output already exists and is not empty: {output_root}")
    audit = _read_json(audit_path)
    _validate("prefab_structure_audit.schema.json", audit, "full Prefab audit")
    if audit.get("import_root") != "Assets":
        raise ValueError(f"full Prefab audit must cover Assets; found {audit.get('import_root')}")
    disk_prefabs = sorted((unity_project / "Assets").rglob("*.prefab"))
    records = list(audit.get("prefabs") or [])
    paths = [str(row.get("prefab_path") or "") for row in records]
    if len(disk_prefabs) != len(records):
        raise ValueError(f"disk/audit Prefab count mismatch: {len(disk_prefabs)} != {len(records)}")
    if len(paths) != len(set(path.lower() for path in paths)):
        raise ValueError("full Prefab audit contains duplicate paths")

    technical_records = []
    graphs = []
    graph_examples = []
    graph_exclusions = []
    vocabulary: Counter[str] = Counter()
    graph_validator = Draft202012Validator(_read_json(_schema_root() / "prefab_graph.schema.json"))
    for record in records:
        prefab_path = str(record["prefab_path"])
        technical_records.append({
            "schema_version": "vfx_full_prefab_technical_record.v1",
            "record_id": _stable_id("technical", prefab_path),
            "prefab_path": prefab_path,
            "source_group": _source_group(prefab_path),
            "technical_status": record.get("status"),
            "technical_reasons": list(record.get("reasons") or []),
            "node_count": int(record.get("node_count") or 0),
            "particle_system_count": int(record.get("particle_system_count") or 0),
            "renderer_count": int(record.get("renderer_count") or 0),
            "material_paths": sorted({path for renderer in record.get("renderers") or [] for path in renderer.get("material_paths") or []}),
            "mesh_paths": sorted({path for renderer in record.get("renderers") or [] for path in renderer.get("mesh_paths") or []}),
            "missing_script_count": int(record.get("missing_script_count") or 0),
            "missing_material_slot_count": int(record.get("missing_material_slot_count") or 0),
            "missing_shader_count": int(record.get("missing_shader_count") or 0),
            "aesthetic_label_source": "none",
            "source_audit": _portable(audit_path),
        })
        if not record.get("nodes"):
            graph_exclusions.append({"prefab_path": prefab_path, "reason": "unity_audit_has_no_nodes", "technical_status": record.get("status")})
            continue
        try:
            graph = build_prefab_graph(_graph_example(record, baseline_id), baseline_id)
        except ValueError as error:
            graph_exclusions.append({"prefab_path": prefab_path, "reason": "prefab_graph_conversion_failed", "error": str(error), "technical_status": record.get("status")})
            continue
        graph_errors = list(graph_validator.iter_errors(graph))
        if graph_errors:
            raise ValueError(f"PrefabGraph schema error for {prefab_path}: {graph_errors[0].message}")
        tokens = tokenize_prefab_graph(graph)
        vocabulary.update(tokens)
        graphs.append(graph)
        example = _graph_example(record, baseline_id)
        graph_examples.append({
            "schema_version": "vfx_prefab_graph_training_example.v1",
            "example_id": example["example_id"],
            "graph_id": graph["graph_id"],
            "tokens": tokens,
            "eligible_tasks": graph["training"]["eligible_tasks"],
            "split_group": example["split_group"],
            "source_example_id": example["example_id"],
        })

    graph_ids = [row["graph_id"] for row in graphs]
    if len(graph_ids) != len(set(graph_ids)):
        raise ValueError("full PrefabGraph dataset contains duplicate graph IDs")
    technical_path = _write_jsonl(output_root / "technical_records.jsonl", technical_records)
    exclusions_path = _write_jsonl(output_root / "graph_exclusions.jsonl", graph_exclusions)
    graphs_path = _write_jsonl(output_root / "graphs.jsonl", sorted(graphs, key=lambda row: str(row["source"]["prefab_path"])))
    examples_path = _write_jsonl(output_root / "examples.jsonl", sorted(graph_examples, key=lambda row: row["example_id"]))
    vocabulary_path = _write_json(output_root / "vocabulary.json", {
        "schema_version": "vfx_prefab_graph_vocabulary.v1",
        "tokens": [{"token": token, "count": count} for token, count in sorted(vocabulary.items())],
    })
    graph_manifest = {
        "schema_version": "vfx_prefab_graph_training_dataset.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": baseline_id,
        "source_dataset_id": baseline_id,
        "example_count": len(graph_examples),
        "reconstruction_status_counts": dict(sorted(Counter(row["reconstruction"]["status"] for row in graphs).items())),
        "token_count": sum(vocabulary.values()),
        "files": {"examples": _portable(examples_path), "graphs": _portable(graphs_path), "vocabulary": _portable(vocabulary_path)},
        "quality_gates": {"source_example_count": len(graph_examples), "graph_schema_errors": 0, "duplicate_graph_ids": 0, "aesthetic_labels_consumed": 0},
        "status": "pass",
    }
    _validate("prefab_graph_training_dataset.schema.json", graph_manifest, "full PrefabGraph manifest")
    graph_manifest_path = _write_json(output_root / "dataset_manifest.json", graph_manifest)
    baseline = {
        "schema_version": "vfx_full_prefab_technical_baseline.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_id": baseline_id,
        "source_audit": _portable(audit_path),
        "unity_project": _portable(unity_project),
        "disk_prefab_count": len(disk_prefabs),
        "audit_prefab_count": len(records),
        "technical_record_count": len(technical_records),
        "graph_count": len(graphs),
        "graph_exclusion_count": len(graph_exclusions),
        "source_group_counts": dict(sorted(Counter(row["source_group"] for row in technical_records).items())),
        "technical_status_counts": dict(sorted(Counter(str(row["technical_status"]) for row in technical_records).items())),
        "dependency_totals": {
            "material_references": sum(len(row["material_paths"]) for row in technical_records),
            "mesh_references": sum(len(row["mesh_paths"]) for row in technical_records),
            "missing_scripts": sum(row["missing_script_count"] for row in technical_records),
            "missing_material_slots": sum(row["missing_material_slot_count"] for row in technical_records),
            "missing_shaders": sum(row["missing_shader_count"] for row in technical_records),
        },
        "files": {"technical_records": _portable(technical_path), "graph_exclusions": _portable(exclusions_path), "prefab_graph_manifest": _portable(graph_manifest_path)},
        "quality_gates": {
            "audit_schema_errors": 0,
            "disk_audit_count_mismatch": 0,
            "technical_coverage": len(technical_records) / max(1, len(disk_prefabs)),
            "graph_schema_errors": 0,
            "duplicate_prefab_paths": 0,
            "duplicate_graph_ids": 0,
            "aesthetic_labels_consumed": 0,
        },
        "status": "pass",
    }
    _validate("full_prefab_technical_baseline.schema.json", baseline, "full Prefab technical baseline")
    baseline_path = _write_json(output_root / "technical_baseline_manifest.json", baseline)
    return {"baseline_manifest": baseline_path, "prefab_graph_manifest": graph_manifest_path, "technical_records": technical_path, "graphs": graphs_path, "examples": examples_path, "graph_exclusions": exclusions_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build all-Assets technical Prefab corpus and PrefabGraph data.")
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--unity-project", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--baseline-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_full_prefab_baseline(args.audit, args.unity_project, args.output_root, args.baseline_id)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
