"""Finalize source PrefabGraph export -> Unity rebuild -> API readback evidence."""

from __future__ import annotations

import argparse
import json
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


def _candidate_result(directory: Path, candidate_id: str) -> tuple[Path, dict[str, Any]]:
    matches = sorted(directory.glob(f"{candidate_id}*.json"), key=lambda path: path.name)
    pass_matches = [(path, _read(path)) for path in matches if _read(path).get("status") == "pass"]
    if not pass_matches:
        raise FileNotFoundError(f"no passing recompile result for {candidate_id}")
    return pass_matches[-1]


def finalize(export_manifest_path: Path, recompile_results_dir: Path, readback_results_dir: Path, output_path: Path) -> Path:
    repo_root = Path(__file__).parents[3].resolve()
    export_manifest_path = export_manifest_path.resolve()
    recompile_results_dir = recompile_results_dir.resolve()
    readback_results_dir = readback_results_dir.resolve()
    export_manifest = _read(export_manifest_path)
    if export_manifest.get("status") != "pass":
        raise ValueError("source export manifest must pass")
    rows: list[dict[str, Any]] = []
    schema_errors = 0
    graph_schema = _read(repo_root / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json")
    graph_validator = Draft202012Validator(graph_schema)
    for candidate in export_manifest.get("candidates") or []:
        candidate_id = str(candidate["candidate_id"])
        recompile_path, recompile = _candidate_result(recompile_results_dir, candidate_id)
        readback_path = readback_results_dir / f"{candidate_id}.json"
        if not readback_path.is_file():
            raise FileNotFoundError(f"readback result is missing for {candidate_id}")
        readback = _read(readback_path)
        graph_path = repo_root / Path(str(readback["output_graph_path"]))
        if not graph_path.is_file():
            raise FileNotFoundError(f"readback Graph is missing for {candidate_id}: {graph_path}")
        graph = _read(graph_path)
        errors = list(graph_validator.iter_errors(graph))
        schema_errors += len(errors)
        rows.append({
            "candidate_id": candidate_id,
            "source_prefab_path": candidate["prefab_path"],
            "source_graph_path": candidate["graph_path"],
            "recompiled_prefab_path": recompile["output_prefab_path"],
            "recompile_result_path": _portable(recompile_path, repo_root),
            "readback_graph_path": _portable(graph_path, repo_root),
            "readback_result_path": _portable(readback_path, repo_root),
            "recompile_status": recompile.get("status"),
            "readback_status": readback.get("status"),
            "source_prefab_read": recompile.get("source_prefab_read"),
            "source_prefab_instantiated": readback.get("source_prefab_instantiated"),
            "node_count": readback.get("node_count"),
            "particle_system_count": readback.get("particle_system_count"),
            "renderer_count": readback.get("renderer_count"),
            "difference_count": len(readback.get("differences") or []),
            "allowed_normalization_count": len(readback.get("allowed_normalizations") or []),
            "graph_schema_error_count": len(errors),
        })
    report = {
        "schema_version": "vfx_prefab_graph_source_reconstruction_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_export_manifest": _portable(export_manifest_path, repo_root),
        "recompile_results_dir": _portable(recompile_results_dir, repo_root),
        "readback_results_dir": _portable(readback_results_dir, repo_root),
        "candidate_count": len(rows),
        "rows": rows,
        "quality_gates": {
            "source_export_pass": export_manifest.get("status") == "pass",
            "candidate_count": len(rows),
            "all_recompile_pass": all(row["recompile_status"] == "pass" for row in rows),
            "all_readback_pass": all(row["readback_status"] == "pass" for row in rows),
            "all_differences_empty": all(row["difference_count"] == 0 for row in rows),
            "all_no_source_prefab_read": all(row["source_prefab_read"] is False for row in rows),
            "all_no_source_prefab_instantiated": all(row["source_prefab_instantiated"] is False for row in rows),
            "graph_schema_errors": schema_errors,
        },
        "limitations": [
            "The source export and rebuild validate the particle_v1 technical contract, not aesthetic quality.",
            "Source material and mesh bindings remain source provenance; runtime output may use Unity-normalized asset references.",
            "Source Prefabs with unsupported modules are kept in the source export manifest but are not included in this reconstructable batch.",
        ],
        "status": "pass" if len(rows) == export_manifest.get("candidate_count") == 10 and all(
            row["recompile_status"] == "pass"
            and row["readback_status"] == "pass"
            and row["difference_count"] == 0
            and row["source_prefab_read"] is False
            and row["source_prefab_instantiated"] is False
            and row["graph_schema_error_count"] == 0
            for row in rows
        ) else "blocked",
    }
    schema = _read(repo_root / "workspace/data/vfx_generation/schemas/prefab_graph_source_reconstruction_report.schema.json")
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"source reconstruction report schema error at {location}: {errors[0].message}")
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize source PrefabGraph reconstruction evidence.")
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--recompile-results-dir", type=Path, required=True)
    parser.add_argument("--readback-results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = finalize(args.export_manifest, args.recompile_results_dir, args.readback_results_dir, args.output)
        status = _read(path)["status"]
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": status == "pass", "report": path.as_posix(), "status": status}, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
