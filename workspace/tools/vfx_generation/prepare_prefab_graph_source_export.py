"""Prepare Unity source-Prefab Graph export requests from technical corpus evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def prepare(cases_path: Path, output_root: Path, count: int) -> Path:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"source export output already exists and is not empty: {output_root}")
    cases = _read_jsonl(cases_path.resolve())
    supported_modules = {"emission", "shape", "color_over_lifetime", "size_over_lifetime"}
    selected: list[dict[str, Any]] = []
    for case in cases:
        if case.get("label", {}).get("technical_status") != "particle_playable":
            continue
        outputs = case.get("outputs") if isinstance(case.get("outputs"), dict) else {}
        nodes = outputs.get("prefab_graph") if isinstance(outputs.get("prefab_graph"), list) else []
        renderers = outputs.get("renderers") if isinstance(outputs.get("renderers"), list) else []
        particle_systems = outputs.get("particle_systems") if isinstance(outputs.get("particle_systems"), list) else []
        if not nodes or not particle_systems or not renderers:
            continue
        renderer_types = {str(row.get("renderer_type")) for row in renderers}
        component_types = {str(value) for node in nodes for value in node.get("component_types", [])}
        if renderer_types != {"ParticleSystemRenderer"}:
            continue
        if not component_types.issubset({"UnityEngine.Transform", "UnityEngine.ParticleSystem", "UnityEngine.ParticleSystemRenderer"}):
            continue
        particle_node_paths = {
            str(node.get("hierarchy_path"))
            for node in nodes
            if "UnityEngine.ParticleSystem" in {str(value) for value in node.get("component_types", [])}
        }
        renderer_paths = {str(row.get("hierarchy_path")) for row in renderers}
        if not particle_node_paths.issubset(renderer_paths):
            continue
        if any(module not in supported_modules for particle in particle_systems for module in particle.get("enabled_modules", [])):
            continue
        selected.append(case)
        if len(selected) >= count:
            break
    if len(selected) < count:
        raise ValueError(f"only {len(selected)} particle_v1 source Prefabs are available, need {count}")
    requests = []
    for case in selected:
        candidate_id = str(case["candidate_id"])
        requests.append({
            "candidate_id": candidate_id,
            "prefab_path": str(case["inputs"]["prefab_path"]),
            "graph_path": (output_root / "graphs" / f"{candidate_id}.json").as_posix(),
            "report_path": (output_root / "reports" / f"{candidate_id}.json").as_posix(),
        })
    manifest = {
        "schema_version": "vfx_prefab_graph_source_export_requests.v1",
        "source_dataset_id": "prefab_structure_r005c_training_r005",
        "source_cases_path": cases_path.resolve().as_posix(),
        "requests": requests,
        "status": "prepared",
    }
    return _write(output_root / "export_requests.json", manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare Unity source PrefabGraph export requests.")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        path = prepare(args.cases, args.output_root, args.count)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "requests": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
