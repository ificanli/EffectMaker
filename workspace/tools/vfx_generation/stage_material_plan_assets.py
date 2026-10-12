"""Stage selected MaterialPlan asset closures into an isolated Unity project."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workspace.tools.vfx_source_ingest import collect_dependency_closure, scan_guid_map


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and _sha256(source) == _sha256(destination):
        return "reused"
    status = "replaced" if destination.exists() else "copied"
    shutil.copy2(source, destination)
    return status


def _selected_asset_paths(manifest_path: Path) -> list[str]:
    manifest = _read(manifest_path)
    values: set[str] = set()
    plan_paths = [candidate.get("asset_plan_path") for candidate in manifest.get("candidates") or []]
    if manifest.get("material_plan_path"):
        plan_paths.append(manifest["material_plan_path"])
    for raw_plan_path in plan_paths:
        plan_path = Path(str(raw_plan_path or ""))
        if not plan_path.is_absolute():
            plan_path = Path(__file__).parents[3] / plan_path
        plan_path = plan_path.resolve()
        plan = _read(plan_path)
        if plan.get("status") != "pass":
            raise ValueError(f"passing MaterialPlan expected: {plan_path}")
        for layer in plan.get("layers") or []:
            selected_id = layer.get("selected_candidate_id")
            selected = next((row for row in layer.get("candidates") or [] if row.get("candidate_id") == selected_id), None)
            if selected is None:
                raise ValueError(f"MaterialPlan selected candidate is missing: {selected_id}")
            for path in (selected["material"]["path"], selected["texture"]["path"], selected["shader"]["path"]):
                normalized = str(path).replace("\\", "/")
                if not normalized.startswith("Assets/"):
                    raise ValueError(f"selected asset is not project relative: {normalized}")
                values.add(normalized)
    if not values:
        raise ValueError("MaterialPlan manifest has no selected assets")
    return sorted(values)


def stage_assets(manifest_path: Path, source_project: Path, target_project: Path, output_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    source_project = source_project.resolve()
    target_project = target_project.resolve()
    output_path = output_path.resolve()
    source_assets = source_project / "Assets"
    target_assets = target_project / "Assets"
    if not (source_project / "ProjectSettings/ProjectVersion.txt").is_file():
        raise ValueError(f"source Unity project expected: {source_project}")
    if not (target_project / "ProjectSettings/ProjectVersion.txt").is_file():
        raise ValueError(f"target Unity project expected: {target_project}")

    selected_paths = _selected_asset_paths(manifest_path)
    initial = [source_project / Path(path) for path in selected_paths]
    missing = [path for path, source in zip(selected_paths, initial) if not source.is_file()]
    if missing:
        raise FileNotFoundError(f"selected source asset is missing: {missing[0]}")
    guid_map = scan_guid_map(source_assets, source_project)
    closure, ignored_guids = collect_dependency_closure(initial, guid_map, source_project=source_project, include_scripts=False)
    counts = {"copied": 0, "replaced": 0, "reused": 0}
    copied_rows = []
    parent_directories: set[Path] = set()
    for source in closure:
        relative = source.relative_to(source_project)
        destination = target_project / relative
        status = _copy(source, destination)
        counts[status] += 1
        source_meta = Path(str(source) + ".meta")
        if source_meta.is_file():
            _copy(source_meta, Path(str(destination) + ".meta"))
        current = source.parent
        while current != source_project and current != source_assets.parent:
            parent_directories.add(current)
            if current == source_assets:
                break
            current = current.parent
        copied_rows.append({"path": relative.as_posix(), "status": status, "sha256": _sha256(source)})
    for directory in sorted(parent_directories, key=lambda path: len(path.parts)):
        if directory == source_project:
            continue
        meta = Path(str(directory) + ".meta")
        if not meta.is_file():
            continue
        relative_meta = meta.relative_to(source_project)
        _copy(meta, target_project / relative_meta)

    integrity_errors = []
    for row in copied_rows:
        source = source_project / Path(row["path"])
        target = target_project / Path(row["path"])
        if not target.is_file() or _sha256(source) != _sha256(target):
            integrity_errors.append(row["path"])
        source_meta = Path(str(source) + ".meta")
        target_meta = Path(str(target) + ".meta")
        if source_meta.is_file() and (not target_meta.is_file() or _sha256(source_meta) != _sha256(target_meta)):
            integrity_errors.append(row["path"] + ".meta")
    report = {
        "schema_version": "vfx_material_plan_staging_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": manifest_path.as_posix(),
        "source_project": source_project.as_posix(),
        "target_project": target_project.as_posix(),
        "selected_asset_count": len(selected_paths),
        "closure_asset_count": len(closure),
        "copied_count": counts["copied"],
        "replaced_count": counts["replaced"],
        "reused_count": counts["reused"],
        "ignored_script_guid_count": len(ignored_guids),
        "ignored_script_guids": sorted(ignored_guids),
        "integrity_errors": sorted(set(integrity_errors)),
        "selected_asset_paths": selected_paths,
        "closure": copied_rows,
        "status": "pass" if not integrity_errors else "blocked",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if integrity_errors:
        raise ValueError(f"staged asset integrity failed: {integrity_errors[0]}")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage selected MaterialPlan assets into an isolated Unity project.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-project", type=Path, required=True)
    parser.add_argument("--target-project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = stage_assets(args.manifest, args.source_project, args.target_project, args.output)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "report": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
