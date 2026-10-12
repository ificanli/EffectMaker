"""Validate Unity PrefabGraph readback reports and build a roundtrip manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_roundtrip_batch(batch_root: Path, schema_path: Path, output_path: Path) -> Path:
    batch_root = batch_root.resolve()
    schema = _read_json(schema_path.resolve())
    validator = Draft202012Validator(schema)
    rows: list[dict[str, Any]] = []
    schema_errors: list[dict[str, str]] = []
    graph_ids: list[str] = []
    for index in range(1, 11):
        sample_id = f"{index:02d}"
        result_path = batch_root / "roundtrip_results_final" / f"result_{sample_id}.json"
        graph_path = batch_root / "roundtrip_graphs_final" / f"graph_{sample_id}.json"
        result = _read_json(result_path)
        graph = _read_json(graph_path)
        for error in sorted(validator.iter_errors(graph), key=lambda value: list(value.path)):
            location = ".".join(str(part) for part in error.path) or "<root>"
            schema_errors.append({"sample_id": sample_id, "location": location, "message": error.message})
        graph_ids.append(str(graph.get("graph_id") or ""))
        rows.append({
            "sample_id": sample_id,
            "graph_id": graph.get("graph_id"),
            "status": result.get("status"),
            "unity_api_readback": result.get("unity_api_readback"),
            "source_prefab_instantiated": result.get("source_prefab_instantiated"),
            "node_count": len(graph.get("nodes") or []),
            "particle_system_count": len((graph.get("components") or {}).get("particle_systems") or []),
            "renderer_count": len((graph.get("components") or {}).get("renderers") or []),
            "difference_count": len(result.get("differences") or []),
            "allowed_normalization_count": len(result.get("allowed_normalizations") or []),
        })
    report = {
        "schema_version": "vfx_prefab_graph_roundtrip_manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_root": batch_root.as_posix(),
        "sample_count": len(rows),
        "status_counts": dict(sorted(Counter(str(row["status"]) for row in rows).items())),
        "unique_graph_id_count": len(set(graph_ids)),
        "schema_error_count": len(schema_errors),
        "rows": rows,
        "quality_gates": {
            "expected_sample_count": 10,
            "sample_count": len(rows),
            "all_readback_status_pass": all(row["status"] == "pass" for row in rows),
            "all_differences_empty": all(row["difference_count"] == 0 for row in rows),
            "all_unity_api_readback": all(row["unity_api_readback"] is True for row in rows),
            "all_no_source_prefab_instantiation": all(row["source_prefab_instantiated"] is False for row in rows),
            "unique_graph_ids": len(set(graph_ids)) == len(rows),
            "graph_schema_errors": len(schema_errors),
        },
        "schema_errors": schema_errors,
        "status": "pass" if len(rows) == 10 and not schema_errors and all(
            row["status"] == "pass"
            and row["difference_count"] == 0
            and row["unity_api_readback"] is True
            and row["source_prefab_instantiated"] is False
            for row in rows
        ) and len(set(graph_ids)) == len(rows) else "blocked",
        "limitations": [
            "Unity JsonUtility root parent null is represented as an empty parent_node_id string and accepted as an explicit serialization normalization.",
            "Material paths are generated output bindings; the input material template relationship is recorded as an allowed normalization.",
            "This report validates technical Graph -> Prefab -> Graph equivalence, not aesthetic quality.",
        ],
    }
    return _write_json(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Unity PrefabGraph roundtrip batch.")
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path("workspace/data/vfx_generation/schemas/prefab_graph.schema.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report_path = validate_roundtrip_batch(args.batch_root, args.schema, args.output)
        report = _read_json(report_path)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": report["status"] == "pass", "report": report_path.as_posix(), "status": report["status"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
