"""Build a unified texture, Shader and material capability registry for VFX generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from workspace.tools.resource_index.texture_tagger import tag_texture_record


SHADER_EXTENSIONS = {".shader", ".shadergraph", ".hlsl", ".cginc"}
TEXTURE_SCHEMA = "vfx_texture_candidate.v1"
SHADER_SCHEMA = "vfx_shader_capability.v1"
MATERIAL_SCHEMA = "vfx_material_binding_candidate.v1"


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _schema_root() -> Path:
    return _repo_root() / "workspace/data/vfx_generation/schemas"


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_id(prefix: str, value: str) -> str:
    return f"{prefix}_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _validate(name: str, rows: Iterable[dict[str, Any]]) -> list[str]:
    validator = Draft202012Validator(_read_json(_schema_root() / name))
    errors = []
    for row in rows:
        for error in validator.iter_errors(row):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{row.get('asset_id') or row.get('material_id')}:{location}:{error.message}")
    return errors


def _pipeline_tags(text: str, path: str) -> list[str]:
    lowered = f"{path}\n{text}".lower()
    tags = []
    if "universalpipeline" in lowered or "render-pipelines.universal" in lowered or "/urp" in lowered or " urp" in lowered:
        tags.append("urp")
    if "hdrenderpipeline" in lowered or "render-pipelines.high-definition" in lowered or "/hdrp" in lowered:
        tags.append("hdrp")
    if "unitycg.cginc" in lowered or ("cgprogram" in lowered and not tags):
        tags.append("builtin")
    return sorted(set(tags or ["unknown"]))


def _shader_source(path: Path) -> tuple[str, list[str], list[str], list[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "", ["unknown"], [], [], []
    match = re.search(r'\bShader\s+"([^"]+)"', text)
    shader_name = match.group(1) if match else ""
    properties = sorted(set(re.findall(r"(?m)^\s*(_[A-Za-z0-9_]+)\s*\(", text)))
    includes = sorted(set(re.findall(r'#include\s+["<]([^">]+)[">]', text)))
    keywords = sorted(set(re.findall(r"(?m)^\s*#pragma\s+(?:shader_feature(?:_local)?|multi_compile(?:_local)?)\s+([^\r\n]+)", text)))
    keyword_values = sorted({value for group in keywords for value in group.split() if value not in {"_", "__"}})
    return shader_name, _pipeline_tags(text, path.as_posix()), properties, keyword_values, includes


def _license_status(root: Path) -> str:
    candidates = [path for path in root.iterdir() if path.is_file() and path.name.lower().startswith(("license", "copying"))]
    if not candidates:
        return "unknown"
    text = candidates[0].read_text(encoding="utf-8", errors="ignore").lower()
    if "mit license" in text:
        return "declared_mit"
    if "apache license" in text:
        return "declared_apache"
    if "gnu general public license" in text:
        return "declared_gpl"
    return "declared_other"


def _unity_version(root: Path) -> str | None:
    path = root / "ProjectSettings/ProjectVersion.txt"
    if not path.is_file():
        return None
    match = re.search(r"m_EditorVersion:\s*(.+)", path.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1).strip() if match else None


def _texture_registry(global_tags_path: Path, project_tags_path: Path | None, shader_audit: dict[str, Any], project_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    project_tags = {}
    if project_tags_path is not None and project_tags_path.is_file():
        project_tags = {str(row.get("relative_path") or "").replace("\\", "/"): row for row in _read_jsonl(project_tags_path)}
    records_by_sha: dict[str, dict[str, Any]] = {}
    for source in _read_jsonl(global_tags_path):
        content_sha = str(source.get("asset_id") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", content_sha):
            continue
        path = _repo_root() / "resource" / str(source["relative_path"])
        exists = path.is_file()
        records_by_sha[content_sha] = {
            "schema_version": TEXTURE_SCHEMA,
            "asset_id": f"tex_{content_sha[:20]}",
            "content_sha256": content_sha,
            "binding_status": "requires_import" if exists else "missing_source",
            "license_status": str(source.get("license_status") or "unknown"),
            "tags": sorted(set(source.get("tags") or [])),
            "metrics": source.get("metrics") or {},
            "width": int(source.get("width") or 0),
            "height": int(source.get("height") or 0),
            "source_paths": [{"path": _portable(path), "source_kind": "local_reference", "exists": exists}],
            "project_asset_path": None,
            "importer": None,
            "provenance": {"global_texture_index": _portable(global_tags_path), "thumbnail_status": source.get("thumbnail_status")},
        }
    project_ids: dict[str, str] = {}
    for source in shader_audit.get("textures") or []:
        asset_path = str(source["texture_path"]).replace("\\", "/")
        path = project_root / Path(asset_path)
        if not path.is_file():
            continue
        content_sha = _sha256(path)
        local_tags = project_tags.get(asset_path, {})
        existing = records_by_sha.get(content_sha)
        generated = tag_texture_record({
            "asset_id": content_sha,
            "relative_path": asset_path,
            "extension": str(source.get("source_extension") or path.suffix.lower()),
            "width": int(source.get("width") or 0),
            "height": int(source.get("height") or 0),
            "license_status": str(local_tags.get("license_status") or "unknown"),
            "tags": [],
            "thumbnail_status": None,
        }, project_root, inspect_pixels=True)
        tags = sorted(set([*(existing or {}).get("tags", []), *(local_tags.get("tags") or []), *(generated.get("tags") or [])]))
        source_paths = list((existing or {}).get("source_paths", []))
        source_paths.append({"path": asset_path, "source_kind": "project_asset", "exists": True})
        record = {
            "schema_version": TEXTURE_SCHEMA,
            "asset_id": f"tex_{content_sha[:20]}",
            "content_sha256": content_sha,
            "binding_status": "project_bindable",
            "license_status": str(local_tags.get("license_status") or "local_source_unconfirmed"),
            "tags": tags,
            "metrics": generated.get("metrics") or (existing or {}).get("metrics") or {},
            "width": int(source.get("width") or (existing or {}).get("width") or 0),
            "height": int(source.get("height") or (existing or {}).get("height") or 0),
            "source_paths": sorted(source_paths, key=lambda row: (row["source_kind"], row["path"])),
            "project_asset_path": asset_path,
            "importer": {
                key: source.get(key)
                for key in ("texture_type", "alpha_source", "srgb", "wrap_mode", "filter_mode", "max_texture_size", "compression", "mipmap_enabled", "is_readable", "texture_format", "source_extension", "source_group")
            },
            "provenance": {"unity_shader_audit": True, "project_texture_tags": _portable(project_tags_path) if project_tags_path else None, "global_tag_match": existing is not None},
        }
        records_by_sha[content_sha] = record
        project_ids[asset_path] = record["asset_id"]
    return sorted(records_by_sha.values(), key=lambda row: row["asset_id"]), project_ids


def _unity_shaders(shader_audit: dict[str, Any], project_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    records = []
    path_ids = {}
    for source in shader_audit.get("shaders") or []:
        asset_path = str(source["shader_path"]).replace("\\", "/")
        path = project_root / Path(asset_path)
        exists = path.is_file()
        content_sha = _sha256(path) if exists else None
        parsed_name, pipelines, parsed_properties, parsed_keywords, includes = _shader_source(path)
        error_count = int(source.get("error_count") or 0)
        supported = bool(source.get("is_supported"))
        binding_status = "project_bindable" if exists and supported and error_count == 0 else "blocked_missing_file" if not exists else "blocked_compile_error" if error_count else "blocked_unsupported"
        record = {
            "schema_version": SHADER_SCHEMA,
            "asset_id": _asset_id("shader", f"unity|{asset_path}|{source.get('shader_guid')}"),
            "content_sha256": content_sha,
            "shader_name": str(source.get("shader_name") or parsed_name) or None,
            "path": asset_path,
            "source_kind": "project_bindable",
            "binding_status": binding_status,
            "license_status": "local_source_unconfirmed",
            "source_repository": None,
            "target_unity_version": str(shader_audit.get("unity_version") or "") or None,
            "pipeline_tags": pipelines,
            "property_names": sorted(set([*(row.get("property_name") for row in source.get("properties") or [] if row.get("property_name")), *parsed_properties])),
            "keywords": sorted(set([*(source.get("keywords") or []), *parsed_keywords])),
            "includes": includes,
            "dependencies": sorted(set(source.get("dependency_paths") or [])),
            "compiler": {"unity_api_audited": True, "unity_version": shader_audit.get("unity_version"), "is_supported": supported, "error_count": error_count, "warning_count": int(source.get("warning_count") or 0), "messages": list(source.get("messages") or [])},
            "provenance": {"shader_audit_schema": shader_audit.get("schema_version"), "audit_render_pipeline": shader_audit.get("render_pipeline")},
        }
        records.append(record)
        path_ids[asset_path] = record["asset_id"]
    return records, path_ids


def _reference_shaders(root: Path, source_kind: str) -> list[dict[str, Any]]:
    records = []
    repositories = [root] if source_kind == "package_reference" else sorted(path for path in root.iterdir() if path.is_dir())
    for repository in repositories:
        license_status = _license_status(repository)
        version = _unity_version(repository)
        for path in sorted(candidate for candidate in repository.rglob("*") if candidate.is_file() and candidate.suffix.lower() in SHADER_EXTENSIONS):
            content_sha = _sha256(path)
            shader_name, pipelines, properties, keywords, includes = _shader_source(path)
            records.append({
                "schema_version": SHADER_SCHEMA,
                "asset_id": _asset_id("shader", f"{source_kind}|{_portable(path)}|{content_sha}"),
                "content_sha256": content_sha,
                "shader_name": shader_name or None,
                "path": _portable(path),
                "source_kind": source_kind,
                "binding_status": "reference_only",
                "license_status": license_status,
                "source_repository": repository.name,
                "target_unity_version": version,
                "pipeline_tags": pipelines,
                "property_names": properties,
                "keywords": keywords,
                "includes": includes,
                "dependencies": [],
                "compiler": {"unity_api_audited": False, "unity_version": None, "is_supported": None, "error_count": 0, "warning_count": 0, "messages": []},
                "provenance": {"reference_root": _portable(repository), "must_import_and_compile_before_binding": True},
            })
    return records


def _materials(material_audit: dict[str, Any], shader_ids: dict[str, str], shader_statuses: dict[str, str], texture_ids: dict[str, str]) -> list[dict[str, Any]]:
    records = []
    for source in material_audit.get("materials") or []:
        shader_name = str(source.get("shader_name") or "")
        shader_path = str(source.get("shader_path") or "").replace("\\", "/") or None
        shader_id = shader_ids.get(shader_path or "")
        bindings = []
        unresolved = False
        for binding in source.get("bindings") or []:
            texture_path = str(binding.get("texture_path") or "").replace("\\", "/") or None
            texture_id = texture_ids.get(texture_path or "")
            if binding.get("is_bound") and texture_path and texture_id is None:
                unresolved = True
            bindings.append({"property_name": str(binding.get("property_name") or "unknown"), "is_bound": bool(binding.get("is_bound")), "texture_asset_id": texture_id, "texture_path": texture_path})
        reasons = []
        if shader_name == "Hidden/InternalErrorShader" or not source.get("shader_supported") or shader_id is None or shader_statuses.get(shader_path or "") != "project_bindable":
            reasons.append("shader_not_bindable")
        if unresolved:
            reasons.append("bound_texture_not_in_registry")
        status = "blocked_shader" if "shader_not_bindable" in reasons else "blocked_texture_reference" if unresolved else "usable"
        records.append({
            "schema_version": MATERIAL_SCHEMA,
            "material_id": _asset_id("material", f"{source.get('material_path')}|{source.get('material_guid')}"),
            "material_path": str(source["material_path"]).replace("\\", "/"),
            "material_guid": source.get("material_guid"),
            "source_group": str(source.get("source_group") or "unknown"),
            "binding_status": status,
            "exclusion_reasons": sorted(set(reasons)),
            "shader_asset_id": shader_id,
            "shader_name": shader_name or None,
            "shader_path": shader_path,
            "render_queue": int(source.get("render_queue") or 0),
            "keywords": sorted(set(source.get("shader_keywords") or [])),
            "property_names": sorted({str(row.get("property_name")) for row in source.get("properties") or [] if row.get("property_name")}),
            "texture_bindings": bindings,
            "provenance": {"unity_material_audit_schema": material_audit.get("schema_version"), "unity_version": material_audit.get("unity_version")},
        })
    return sorted(records, key=lambda row: row["material_id"])


def build_registry(
    shader_audit_path: Path,
    material_audit_path: Path,
    global_texture_tags_path: Path,
    project_root: Path,
    github_root: Path,
    nb_root: Path,
    output_root: Path,
    registry_id: str,
    project_texture_tags_path: Path | None = None,
) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"asset registry output already exists and is not empty: {output_root}")
    shader_audit = _read_json(shader_audit_path.resolve())
    material_audit = _read_json(material_audit_path.resolve())
    project_root, github_root, nb_root = project_root.resolve(), github_root.resolve(), nb_root.resolve()
    textures, texture_ids = _texture_registry(global_texture_tags_path.resolve(), project_texture_tags_path.resolve() if project_texture_tags_path else None, shader_audit, project_root)
    unity_shaders, shader_ids = _unity_shaders(shader_audit, project_root)
    shaders = [*unity_shaders, *_reference_shaders(nb_root, "package_reference"), *_reference_shaders(github_root, "github_reference")]
    shaders.sort(key=lambda row: row["asset_id"])
    shader_statuses = {row["path"]: row["binding_status"] for row in unity_shaders}
    materials = _materials(material_audit, shader_ids, shader_statuses, texture_ids)
    errors = [
        *_validate("texture_candidate.schema.json", textures),
        *_validate("shader_capability.schema.json", shaders),
        *_validate("material_binding_candidate.schema.json", materials),
    ]
    texture_ids_all = [row["asset_id"] for row in textures]
    shader_ids_all = [row["asset_id"] for row in shaders]
    material_ids = [row["material_id"] for row in materials]
    gates = {
        "schema_errors": len(errors),
        "duplicate_texture_ids": len(texture_ids_all) - len(set(texture_ids_all)),
        "duplicate_shader_ids": len(shader_ids_all) - len(set(shader_ids_all)),
        "duplicate_material_ids": len(material_ids) - len(set(material_ids)),
        "project_texture_missing_files": sum(row["binding_status"] == "project_bindable" and not (project_root / Path(str(row["project_asset_path"]))).is_file() for row in textures),
        "project_shader_missing_files": sum(row["source_kind"] == "project_bindable" and row["binding_status"] != "blocked_missing_file" and not (project_root / Path(row["path"])).is_file() for row in shaders),
        "reference_assets_marked_bindable": sum(row["source_kind"] != "project_bindable" and row["binding_status"] == "project_bindable" for row in shaders),
        "compiler_error_assets_marked_bindable": sum(row["compiler"]["error_count"] > 0 and row["binding_status"] == "project_bindable" for row in shaders),
        "invalid_materials_marked_usable": sum(row["binding_status"] == "usable" and (row["shader_asset_id"] is None or any(binding["is_bound"] and binding["texture_path"] and binding["texture_asset_id"] is None for binding in row["texture_bindings"])) for row in materials),
    }
    if errors or any(gates.values()):
        raise ValueError(f"asset capability registry quality gate failed: {gates}; first schema error: {errors[:1]}")
    texture_path = _write_jsonl(output_root / "textures.jsonl", textures)
    shader_path = _write_jsonl(output_root / "shaders.jsonl", shaders)
    material_path = _write_jsonl(output_root / "materials.jsonl", materials)
    manifest = {
        "schema_version": "vfx_asset_capability_registry.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "registry_id": registry_id,
        "target_unity_version": "2022.3.16f1c1",
        "target_render_pipeline": "urp14",
        "counts": {
            "texture_count": len(textures),
            "project_bindable_texture_count": sum(row["binding_status"] == "project_bindable" for row in textures),
            "local_reference_texture_count": sum(row["binding_status"] != "project_bindable" for row in textures),
            "shader_count": len(shaders),
            "project_bindable_shader_count": sum(row["binding_status"] == "project_bindable" for row in shaders),
            "package_reference_shader_count": sum(row["source_kind"] == "package_reference" for row in shaders),
            "github_reference_shader_count": sum(row["source_kind"] == "github_reference" for row in shaders),
            "material_count": len(materials),
            "usable_material_count": sum(row["binding_status"] == "usable" for row in materials),
            "blocked_material_count": sum(row["binding_status"] != "usable" for row in materials),
        },
        "files": {"textures": _portable(texture_path), "shaders": _portable(shader_path), "materials": _portable(material_path)},
        "quality_gates": gates,
        "status": "pass",
    }
    manifest_errors = _validate("asset_capability_registry.schema.json", [manifest])
    if manifest_errors:
        raise ValueError(f"asset registry manifest schema error: {manifest_errors[0]}")
    manifest_path = _write_json(output_root / "registry_manifest.json", manifest)
    return {"manifest": manifest_path, "textures": texture_path, "shaders": shader_path, "materials": material_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a unified VFX asset capability registry.")
    parser.add_argument("--shader-audit", type=Path, required=True)
    parser.add_argument("--material-audit", type=Path, required=True)
    parser.add_argument("--global-texture-tags", type=Path, required=True)
    parser.add_argument("--project-texture-tags", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--github-root", type=Path, required=True)
    parser.add_argument("--nb-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--registry-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_registry(args.shader_audit, args.material_audit, args.global_texture_tags, args.project_root, args.github_root, args.nb_root, args.output_root, args.registry_id, args.project_texture_tags)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
