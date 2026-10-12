"""Build dataset-ready Prefab cases from an imported Unity VFX source sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


STYLE_AXES = (
    "realism",
    "graphic_stylization",
    "texture_detail",
    "color_saturation",
    "edge_definition",
    "glow_exaggeration",
    "motion_exaggeration",
)
RESOLVED_STATUSES = {"resolved", "resolved_shared"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def blank_style_profile(*, source: str, scene_context: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "schema_version": "vfx_style_profile.v1",
        "family": "unknown",
        "keywords": [],
        "axes": {axis: None for axis in STYLE_AXES},
        "scene_context": sorted(set(scene_context)),
        "source": source,
        "confidence": 0.0,
        "notes": "Needs style annotation or a style-conditioned prompt.",
    }


def _source_category(prefab_path: str) -> list[str]:
    lower = prefab_path.replace("\\", "/").lower()
    segments = set(lower.split("/"))
    categories: list[str] = []
    for segment, category in (
        ("ui", "ui"),
        ("scene", "scene"),
        ("enemy", "enemy"),
        ("battle", "battle"),
        ("juese", "character"),
    ):
        if segment in segments:
            categories.append(category)
    return categories or ["unclassified"]


def _effect_family_hint(prefab_path: str) -> str:
    lower = prefab_path.lower()
    for token, family in (
        ("shield", "shield"),
        ("sheilder", "shield"),
        ("smoke", "smoke"),
        ("yanwu", "smoke"),
        ("fire", "fire"),
        ("huo", "fire"),
        ("thunder", "lightning"),
        ("leidian", "lightning"),
        ("lightning", "lightning"),
        ("explosion", "explosion"),
        ("baozha", "explosion"),
        ("water", "water"),
        ("ice", "ice"),
        ("bing", "ice"),
    ):
        if token in lower:
            return family
    return "unclassified"


def _case_id(index: int, prefab_path: str) -> str:
    stem = Path(prefab_path).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "prefab"
    return f"trains_fx_{index:03d}_{slug}"


def _load_texture_tags(path: Path | None) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if path is None or not path.is_file():
        return {}, {}
    tags_by_asset_id: dict[str, dict[str, Any]] = {}
    tags_by_source_path: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        asset_id = row.get("asset_id")
        if isinstance(asset_id, str):
            tags_by_asset_id[asset_id] = row
        source_file_path = row.get("source_file_path")
        if isinstance(source_file_path, str):
            tags_by_source_path[Path(source_file_path).resolve().as_posix()] = row
    return tags_by_asset_id, tags_by_source_path


def _asset_id(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _texture_descriptor(
    path_text: str,
    unity_project: Path | None,
    tags_by_asset_id: dict[str, dict[str, Any]],
    tags_by_source_path: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {"path": path_text, "tags": [], "tag_status": "unavailable"}
    if unity_project is None or not path_text.startswith("Assets/"):
        return result
    asset_id = _asset_id(unity_project / path_text)
    if asset_id is None:
        result["tag_status"] = "target_asset_missing"
        return result
    result["asset_id"] = asset_id
    tag_record = tags_by_asset_id.get(asset_id) or tags_by_source_path.get((unity_project / path_text).resolve().as_posix())
    if tag_record is None:
        result["tag_status"] = "not_indexed"
        return result
    result.update(
        {
            "tags": list(tag_record.get("tags") or []),
            "slot_roles": [tag for tag in tag_record.get("tags") or [] if str(tag).startswith("slot.")],
            "tag_status": "loaded",
            "width": tag_record.get("width"),
            "height": tag_record.get("height"),
        }
    )
    return result


def _dependency_graph(dependencies: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    graph: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for dependency in dependencies:
        source = dependency.get("from_path")
        if isinstance(source, str):
            graph[source].append(dependency)
    return graph


def _reachable_health(prefab_path: str, graph: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    queue: deque[str] = deque([prefab_path])
    visited: set[str] = set()
    missing: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for dependency in graph.get(current, []):
            status = dependency.get("status")
            if status == "missing":
                missing.append(dependency)
            elif status == "ignored":
                ignored.append(dependency)
            target = dependency.get("to_path")
            if isinstance(target, str) and status in RESOLVED_STATUSES:
                queue.append(target)
    missing_types = Counter(str(row.get("dependency_type") or "unknown") for row in missing)
    ignored_types = Counter(str(row.get("dependency_type") or "unknown") for row in ignored)
    return {
        "reachable_asset_count": len(visited),
        "missing_dependency_count": len(missing),
        "missing_dependency_types": dict(missing_types),
        "ignored_dependency_count": len(ignored),
        "ignored_dependency_types": dict(ignored_types),
        "status": "source_missing" if missing else "runtime_context_required" if ignored else "structurally_closed",
    }


def _material_selection(
    prefab_path: str,
    graph: dict[str, list[dict[str, Any]]],
    *,
    unity_project: Path | None,
    tags_by_asset_id: dict[str, dict[str, Any]],
    tags_by_source_path: dict[str, dict[str, Any]],
    material_audit: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    material_paths = sorted(
        {
            str(edge["to_path"])
            for edge in graph.get(prefab_path, [])
            if edge.get("dependency_type") == "material" and edge.get("status") in RESOLVED_STATUSES and isinstance(edge.get("to_path"), str)
        }
    )
    materials: list[dict[str, Any]] = []
    for material_path in material_paths:
        edges = graph.get(material_path, [])
        shaders = sorted(
            {
                str(edge["to_path"])
                for edge in edges
                if edge.get("dependency_type") == "shader" and edge.get("status") in RESOLVED_STATUSES and isinstance(edge.get("to_path"), str)
            }
        )
        texture_paths = sorted(
            {
                str(edge["to_path"])
                for edge in edges
                if edge.get("dependency_type") == "texture" and edge.get("status") in RESOLVED_STATUSES and isinstance(edge.get("to_path"), str)
            }
        )
        unresolved = [edge for edge in edges if edge.get("status") == "missing"]
        audit = material_audit.get(material_path, {})
        materials.append(
            {
                "material_path": material_path,
                "primary_shader_path": shaders[0] if shaders else None,
                "shader_paths": shaders,
                "texture_bindings": [
                    _texture_descriptor(path, unity_project, tags_by_asset_id, tags_by_source_path)
                    for path in texture_paths
                ],
                "source_missing_dependency_count": len(unresolved),
                "editor_texture_slot_count": audit.get("texture_slot_count"),
                "editor_bound_texture_slot_count": audit.get("bound_texture_slot_count"),
            }
        )
    return {
        "material_count": len(materials),
        "materials": materials,
        "selection_basis": [
            "material paths are direct Prefab dependency edges",
            "shader and texture paths are direct material dependency edges",
            "texture tags are joined by content hash when the local index contains the copied texture",
        ],
    }


def _load_material_audit(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    payload = _load_json(path)
    return {
        str(record["material_path"]): record
        for record in payload.get("materials", [])
        if isinstance(record, dict) and isinstance(record.get("material_path"), str)
    }


def _build_local_texture_tags(
    manifest: dict[str, Any],
    unity_project: Path,
    output_path: Path,
) -> Path:
    from workspace.tools.vfx_source_ingest import build_local_texture_tag_index

    texture_paths = sorted(
        {
            str(dependency["to_path"])
            for dependency in manifest.get("dependencies", [])
            if dependency.get("dependency_type") == "texture"
            and dependency.get("status") in RESOLVED_STATUSES
            and isinstance(dependency.get("to_path"), str)
            and str(dependency["to_path"]).startswith("Assets/")
        }
    )
    records = [{"path": path, "license_status": "local_reference_only"} for path in texture_paths]
    build_local_texture_tag_index(records, unity_project.resolve(), unity_project / "Assets", output_path)
    return output_path


def build_prefab_training_dataset(
    source_dir: Path,
    output_dir: Path,
    *,
    unity_project: Path | None = None,
    texture_tag_index_path: Path | None = None,
    material_audit_path: Path | None = None,
    playability_audit_path: Path | None = None,
    generate_local_texture_tags: bool = False,
) -> dict[str, Path]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    manifest = _load_json(source_dir / "source_manifest.json")
    sample = _load_json(source_dir / "source_sample.json")
    graph = _dependency_graph(manifest.get("dependencies", []))
    texture_index_path = texture_tag_index_path or Path(str(manifest.get("extraction", {}).get("texture_tag_index_path") or ""))
    if generate_local_texture_tags:
        if unity_project is None:
            raise ValueError("--generate-local-texture-tags requires --unity-project")
        texture_index_path = _build_local_texture_tags(manifest, unity_project, output_dir / "texture_tags.jsonl")
    tags_by_asset_id, tags_by_source_path = _load_texture_tags(texture_index_path if str(texture_index_path) else None)
    material_audit = _load_material_audit(material_audit_path)
    playability_audit = _load_json(playability_audit_path) if playability_audit_path is not None and playability_audit_path.is_file() else {}
    playability_by_path = {
        str(record["prefab_path"]): record
        for record in playability_audit.get("prefabs", [])
        if isinstance(record, dict) and isinstance(record.get("prefab_path"), str)
    }
    prefab_paths = sorted(
        {
            str(row.get("path"))
            for row in manifest.get("files", [])
            if isinstance(row, dict) and str(row.get("path", "")).lower().endswith(".prefab")
        },
        key=str.casefold,
    )
    source_id = str(sample.get("source_id") or manifest.get("source_id") or source_dir.name)
    cases: list[dict[str, Any]] = []
    style_queue: list[dict[str, Any]] = []
    render_queue: list[dict[str, Any]] = []
    blocked_queue: list[dict[str, Any]] = []
    supervision_counts: Counter[str] = Counter()
    playability_counts: Counter[str] = Counter()

    for index, prefab_path in enumerate(prefab_paths, start=1):
        category = _source_category(prefab_path)
        target_style = blank_style_profile(source="prompt", scene_context=category)
        observed_style = blank_style_profile(source="unlabeled_source_import", scene_context=category)
        health = _reachable_health(prefab_path, graph)
        material_selection = _material_selection(
            prefab_path,
            graph,
            unity_project=unity_project,
            tags_by_asset_id=tags_by_asset_id,
            tags_by_source_path=tags_by_source_path,
            material_audit=material_audit,
        )
        runtime = playability_by_path.get(
            prefab_path,
            {"status": "not_audited", "reasons": ["playability audit pending"], "report_path": None},
        )
        runtime_status = str(runtime.get("status") or "not_audited")
        playability_counts[runtime_status] += 1
        blocking_reasons = []
        if health["missing_dependency_count"]:
            blocking_reasons.append("source_missing_dependency")
        if health["ignored_dependency_count"]:
            blocking_reasons.append("runtime_context_required")
        if runtime.get("status") in {"particle_context_required", "empty_or_invalid", "audit_error"}:
            blocking_reasons.append(str(runtime["status"]))
        if health["missing_dependency_count"]:
            supervision_status = "blocked_source_missing"
        elif runtime_status == "particle_playable":
            supervision_status = "needs_render_and_style_annotation"
        elif runtime_status == "particle_context_required":
            supervision_status = "runtime_context_required"
        elif runtime_status == "static_or_contextual":
            supervision_status = "static_or_contextual"
        elif runtime_status in {"empty_or_invalid", "audit_error"}:
            supervision_status = runtime_status
        else:
            supervision_status = "not_audited"
        supervision_counts[supervision_status] += 1
        eligible_for = ["source_retrieval", "material_candidate_selection", "style_annotation"]
        if runtime_status != "not_audited":
            eligible_for.append("prefab_structure_supervision")
        if int(runtime.get("particle_system_count") or 0) > 0:
            eligible_for.append("particle_parameter_supervision")
        if supervision_status == "needs_render_and_style_annotation":
            eligible_for.append("play_mode_render_candidate")
        case = {
            "schema_version": "vfx_prefab_training_case.v1",
            "case_id": _case_id(index, prefab_path),
            "source": {
                "source_id": source_id,
                "prefab_path": prefab_path,
                "source_category": category,
                "effect_family_hint": _effect_family_hint(prefab_path),
            },
            "inputs": {
                "prompt": f"Imported Unity VFX Prefab: {Path(prefab_path).stem}",
                "negative_prompt": "Do not treat source existence as visual success. Do not use a style label until it is provided by a prompt or human annotation.",
                "target_style_profile": target_style,
                "material_selection": material_selection,
            },
            "observations": {
                "observed_style_profile": observed_style,
                "dependency_health": health,
                "runtime_observation": runtime,
            },
            "training": {
                "supervision_status": supervision_status,
                "eligible_for": eligible_for,
                "excluded_from": ["positive_generation_supervision", "style_conditioned_supervision", "preference_training"],
                "blocking_reasons": sorted(set(blocking_reasons + ["needs_render_evidence", "needs_human_style_annotation"])),
            },
        }
        cases.append(case)
        style_queue.append(
            {
                "schema_version": "vfx_style_annotation_request.v1",
                "case_id": case["case_id"],
                "prefab_path": prefab_path,
                "target_style_profile": target_style,
                "observed_style_profile": observed_style,
                "annotation_status": "pending",
            }
        )
        queue_record = {
            "case_id": case["case_id"],
            "prefab_path": prefab_path,
            "source_category": category,
            "effect_family_hint": case["source"]["effect_family_hint"],
            "supervision_status": supervision_status,
            "playability_status": runtime_status,
            "blocking_reasons": case["training"]["blocking_reasons"],
            "particle_system_count": int(runtime.get("particle_system_count") or 0),
            "estimated_duration_seconds": float(runtime.get("estimated_duration_seconds") or 0.0),
        }
        if supervision_status == "needs_render_and_style_annotation":
            render_queue.append(queue_record)
        else:
            blocked_queue.append(queue_record)

    cases_path = _write_jsonl(output_dir / "prefab_cases.jsonl", cases)
    style_queue_path = _write_jsonl(output_dir / "style_annotation_queue.jsonl", style_queue)
    render_queue_path = _write_jsonl(output_dir / "play_mode_render_queue.jsonl", render_queue)
    blocked_queue_path = _write_jsonl(output_dir / "prefab_blocked_queue.jsonl", blocked_queue)
    manifest_path = _write_json(
        output_dir / "dataset_manifest.json",
        {
            "schema_version": "vfx_prefab_dataset.v1",
            "dataset_id": f"{source_id.lower()}_prefab_cases",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_id": source_id,
            "source_manifest_path": str((source_dir / "source_manifest.json").resolve()),
            "source_sample_path": str((source_dir / "source_sample.json").resolve()),
            "case_count": len(cases),
            "supervision_status_counts": dict(supervision_counts),
            "playability_status_counts": dict(playability_counts),
            "prefab_structure_example_count": sum(status != "not_audited" for status in playability_counts.elements()),
            "particle_parameter_example_count": sum(int(case["observations"]["runtime_observation"].get("particle_system_count") or 0) > 0 for case in cases),
            "play_mode_render_candidate_count": len(render_queue),
            "blocked_or_context_count": len(blocked_queue),
            "prefab_cases_path": cases_path.name,
            "style_annotation_queue_path": style_queue_path.name,
            "play_mode_render_queue_path": render_queue_path.name,
            "prefab_blocked_queue_path": blocked_queue_path.name,
            "material_audit_path": str(material_audit_path.resolve()) if material_audit_path is not None and material_audit_path.is_file() else None,
            "playability_audit_path": str(playability_audit_path.resolve()) if playability_audit_path is not None and playability_audit_path.is_file() else None,
            "texture_tag_index_path": str(texture_index_path.resolve()) if texture_index_path is not None and texture_index_path.is_file() else None,
            "texture_tag_index_record_count": len(tags_by_asset_id),
            "notes": [
                "Cases are source priors and material-selection contexts, not positive visual training labels.",
                "A later prompt supplies target_style_profile; render review supplies observed_style_profile and style match feedback.",
            ],
        },
    )
    return {
        "dataset_manifest": manifest_path,
        "prefab_cases": cases_path,
        "style_annotation_queue": style_queue_path,
        "play_mode_render_queue": render_queue_path,
        "prefab_blocked_queue": blocked_queue_path,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Prefab-level VFX dataset cases from a source-ingest sample.")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--unity-project", type=Path)
    parser.add_argument("--texture-tag-index", type=Path)
    parser.add_argument("--material-audit", type=Path)
    parser.add_argument("--playability-audit", type=Path)
    parser.add_argument("--generate-local-texture-tags", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    paths = build_prefab_training_dataset(
        args.source_dir,
        args.output_dir,
        unity_project=args.unity_project,
        texture_tag_index_path=args.texture_tag_index,
        material_audit_path=args.material_audit,
        playability_audit_path=args.playability_audit,
        generate_local_texture_tags=args.generate_local_texture_tags,
    )
    print(json.dumps({name: path.as_posix() for name, path in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
