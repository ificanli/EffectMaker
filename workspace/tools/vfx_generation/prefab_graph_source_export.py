"""Finalize and validate Unity source PrefabGraph export batches."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _portable(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return path.resolve().as_posix()


def finalize_source_export(export_root: Path, source_project: Path, source_dataset_id: str, output_path: Path) -> Path:
    export_root = export_root.resolve()
    source_project = source_project.resolve()
    repo_root = Path(__file__).parents[3].resolve()
    request = _read(export_root / "export_requests.json")
    rows: list[dict[str, Any]] = []
    schema_errors: list[dict[str, str]] = []
    ids: list[str] = []
    graph_schema = _read(repo_root / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json")
    graph_validator = Draft202012Validator(graph_schema)
    for item in request.get("requests") or []:
        candidate_id = str(item["candidate_id"])
        graph_path = Path(str(item["graph_path"])).resolve()
        report_path = Path(str(item["report_path"])).resolve()
        if not graph_path.is_file() or not report_path.is_file():
            raise FileNotFoundError(f"source export output is missing for {candidate_id}")
        graph = _read(graph_path)
        report = _read(report_path)
        for error in sorted(graph_validator.iter_errors(graph), key=lambda value: list(value.path)):
            location = ".".join(str(part) for part in error.path) or "<root>"
            schema_errors.append({"candidate_id": candidate_id, "location": location, "message": error.message})
        ids.append(candidate_id)
        rows.append({
            "candidate_id": candidate_id,
            "prefab_path": item["prefab_path"],
            "graph_path": _portable(graph_path, repo_root),
            "report_path": _portable(report_path, repo_root),
            "status": report.get("status"),
            "reconstruction_status": report.get("reconstruction_status"),
            "node_count": int(report.get("node_count") or 0),
            "particle_system_count": int(report.get("particle_system_count") or 0),
            "renderer_count": int(report.get("renderer_count") or 0),
            "material_count": len(report.get("material_paths") or []),
            "mesh_count": len(report.get("mesh_paths") or []),
            "missing_fields": list(report.get("missing_fields") or []),
            "unsupported_components": list(report.get("unsupported_components") or []),
        })
    reconstructable_count = sum(row["reconstruction_status"] == "reconstructable" for row in rows)
    structure_only_count = sum(row["reconstruction_status"] == "structure_only" for row in rows)
    report = {
        "schema_version": "vfx_prefab_graph_source_export_manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project": _portable(source_project, repo_root),
        "source_dataset_id": source_dataset_id,
        "candidate_count": len(rows),
        "candidates": rows,
        "quality_gates": {
            "all_reports_pass": all(row["status"] == "pass" for row in rows),
            "graph_schema_errors": len(schema_errors),
            "unique_candidate_ids": len(ids) == len(set(ids)),
            "reconstructable_count": reconstructable_count,
            "structure_only_count": structure_only_count,
            "aesthetic_labels_consumed": 0,
        },
        "status": "pass" if len(rows) == len(request.get("requests") or []) and rows and not schema_errors and len(ids) == len(set(ids)) and all(row["status"] == "pass" for row in rows) else "blocked",
        "limitations": [
            "Source directory names and source labels are provenance only, not aesthetic supervision.",
            "structure_only graphs are retained for hierarchy/component learning but cannot be sent to particle_v1 full reconstruction.",
            "The export is technical source supervision; no human or AI aesthetic label is consumed.",
        ],
    }
    schema = _read(repo_root / "workspace/data/vfx_generation/schemas/prefab_graph_source_export_manifest.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"source export manifest schema error at {location}: {errors[0].message}")
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize a Unity source PrefabGraph export batch.")
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--source-project", type=Path, required=True)
    parser.add_argument("--source-dataset-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = finalize_source_export(args.export_root, args.source_project, args.source_dataset_id, args.output)
        status = _read(path)["status"]
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": status == "pass", "manifest": path.as_posix(), "status": status}, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
