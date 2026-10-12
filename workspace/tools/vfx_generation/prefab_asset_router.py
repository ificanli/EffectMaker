"""Create auditable Material/Texture/Mesh routes for generated PrefabGraphs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .prefab_graph import _read_json, _schema_root, _write_json


ROUTE_SCHEMA = "vfx_prefab_asset_route_plan.v1"
ROUTE_KINDS = ("billboard", "mesh_particle", "impact_decal")
LEGACY_ALLOWED_SHADERS = {"Common/ColorDefault", "Common/CustomSpriteDefault", "Common/FrameAnimation", "VFX/YOYO Shader URP"}
RUNTIME_VERIFIED_MATERIALS = {"Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_S_fozu/mat/Mat_fozu_03.mat"}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _project_root() -> Path:
    return _repo_root() / "UnityDemo/EffectDemo"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _guid(asset_path: str) -> str | None:
    meta = _project_root() / Path(asset_path + ".meta")
    if not meta.is_file():
        return None
    match = re.search(r"^guid:\s*([0-9a-f]{32})\s*$", meta.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def _asset_path_exists(asset_path: str) -> bool:
    return (_project_root() / Path(asset_path)).is_file()


def _validate(plan: dict[str, Any]) -> None:
    schema = _read_json(_schema_root() / "prefab_asset_route_plan.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(plan), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"asset route plan schema error at {location}: {errors[0].message}")


def _tag_index(texture_tag_path: Path) -> dict[str, dict[str, Any]]:
    records = _read_jsonl(texture_tag_path.resolve())
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        path = str(record.get("relative_path") or "").replace("\\", "/")
        if path:
            index[path] = record
    return index


def _material_catalog(material_audit_path: Path, texture_tags: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    audit = _read_json(material_audit_path.resolve())
    records: list[dict[str, Any]] = []
    for material in audit.get("materials") or []:
        material_path = str(material.get("material_path") or "").replace("\\", "/")
        shader_name = str(material.get("shader_name") or "")
        if not material_path or not shader_name or not _asset_path_exists(material_path):
            continue
        bound = []
        for binding in material.get("bindings") or []:
            if not binding.get("is_bound") or not binding.get("texture_path"):
                continue
            texture_path = str(binding["texture_path"]).replace("\\", "/")
            tag = texture_tags.get(texture_path, {})
            bound.append({
                "property_name": str(binding.get("property_name") or ""),
                "path": texture_path,
                "asset_id": tag.get("asset_id") or _guid(texture_path),
                "tags": list(tag.get("tags") or []),
                "slot_roles": [value for value in tag.get("tags") or [] if str(value).startswith("slot.")],
                "authorization_status": str(tag.get("license_status") or "unknown"),
            })
        main_texture = next((value for value in bound if value["property_name"] == "_MainTex"), None)
        if main_texture is None:
            continue
        records.append({
            "asset_id": _guid(material_path),
            "path": material_path,
            "asset_type": "material",
            "authorization_status": "local_source_unconfirmed",
            "sha256": _sha256(_project_root() / Path(material_path)),
            "shader_name": shader_name,
            "shader_properties": [str(row.get("property_name") or "") for row in material.get("properties") or []],
            "bound_textures": bound,
            "main_texture": main_texture,
        })
    return records


def _texture_asset(texture: dict[str, Any], basis: list[str]) -> dict[str, Any]:
    path = str(texture.get("path") or "").replace("\\", "/")
    return {
        "asset_id": texture.get("asset_id"),
        "path": path or None,
        "asset_type": "texture",
        "authorization_status": str(texture.get("authorization_status") or "unknown"),
        "sha256": _sha256(_project_root() / Path(path)) if path and _asset_path_exists(path) else None,
        "tags": list(texture.get("tags") or []),
        "slot_roles": list(texture.get("slot_roles") or []),
        "shader_name": None,
        "selection_basis": basis,
        "verification": "texture_tag_index_and_asset_exists",
    }


def _material_asset(material: dict[str, Any], basis: list[str]) -> dict[str, Any]:
    return {
        "asset_id": material.get("asset_id"),
        "path": material.get("path"),
        "asset_type": "material",
        "authorization_status": material.get("authorization_status", "unknown"),
        "sha256": material.get("sha256"),
        "shader_name": material.get("shader_name"),
        "tags": [],
        "slot_roles": [],
        "selection_basis": basis,
        "verification": "material_binding_audit_and_shader_property_check",
    }


def _mesh_catalog(mesh_root: Path, mesh_audit_path: Path | None) -> list[dict[str, Any]]:
    audit_by_path: dict[str, dict[str, Any]] = {}
    if mesh_audit_path is not None:
        payload = _read_json(mesh_audit_path.resolve())
        audit_by_path = {str(row.get("asset_path") or "").replace("\\", "/"): row for row in payload.get("meshes") or []}
    values: list[dict[str, Any]] = []
    for path in sorted(mesh_root.resolve().rglob("*.fbx")):
        relative = path.relative_to(_project_root()).as_posix()
        audit = audit_by_path.get(relative)
        values.append({
            "asset_id": _guid(relative),
            "path": relative,
            "asset_type": "mesh",
            "authorization_status": "local_source_unconfirmed",
            "sha256": _sha256(path),
            "audit": audit,
        })
    return values


def _select_material(materials: list[dict[str, Any]], route_kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    def score(material: dict[str, Any]) -> tuple[int, str]:
        tags = set(material["main_texture"].get("tags") or [])
        if route_kind == "impact_decal":
            weight = int("role.impact_ring" in tags) * 100 + int("semantic.ring" in tags) * 50 + int("slot.alpha_mask" in tags) * 20
        elif route_kind == "billboard":
            weight = int("slot.emission_map" in tags) * 40 + int("slot.alpha_mask" in tags) * 30 + int("semantic.spark" in tags) * 10
        else:
            weight = int("slot.emission_map" in tags) * 40 + int("slot.alpha_mask" in tags) * 20
        weight += int(material["shader_name"] in LEGACY_ALLOWED_SHADERS) * 10
        if route_kind != "impact_decal" and material["path"] in RUNTIME_VERIFIED_MATERIALS:
            weight += 500
        return (-weight, str(material["path"]))

    compatible = [value for value in materials if value["shader_name"] in LEGACY_ALLOWED_SHADERS and "_MainTex" in value["shader_properties"]]
    if not compatible:
        raise ValueError(f"no Shader/property-compatible material for route {route_kind}")
    material = sorted(compatible, key=score)[0]
    basis = [
        f"shader is in the audited compatible set: {material['shader_name']}",
        "material exposes _MainTex in the Unity API binding audit",
        "material path is provenance; selection does not rely on filename",
    ]
    if route_kind == "impact_decal":
        basis.append("texture tags prefer role.impact_ring or semantic.ring")
    else:
        basis.append("texture tags prefer an emission or alpha slot role")
    if material["path"] in RUNTIME_VERIFIED_MATERIALS:
        basis.append("material template has prior Unity runtime-visible capture evidence")
    return material, {**material["main_texture"], "selection_basis": basis}


def _route_component(graph: dict[str, Any], route_kind: str) -> str | None:
    renderers = graph.get("components", {}).get("renderers") or []
    if route_kind == "mesh_particle":
        for renderer in renderers:
            if str((renderer.get("parameters") or {}).get("particle_render_mode") or "") == "Mesh":
                return str(renderer.get("component_id"))
        return None
    for renderer in renderers:
        if str(renderer.get("renderer_type") or "") == "ParticleSystemRenderer":
            return str(renderer.get("component_id"))
    return None


def _mesh_asset(meshes: list[dict[str, Any]], route_kind: str, basis: list[str]) -> dict[str, Any] | None:
    if route_kind != "mesh_particle":
        return None
    if not meshes:
        raise ValueError("mesh_particle route requires an imported FBX mesh candidate")
    ranked = sorted(meshes, key=lambda value: (0 if any(key in Path(value["path"]).stem.lower() for key in ("daoguang", "arrow", "yuan", "shuibo")) else 1, value["path"]))
    selected = ranked[0]
    audit = selected.get("audit")
    if audit is None:
        verification = "needs_unity_api_validation"
    elif audit.get("status") != "pass" or not audit.get("uv_valid"):
        raise ValueError(f"mesh failed Unity API geometry validation: {selected['path']}")
    else:
        verification = "unity_api_geometry_audit_pass"
    return {
        "asset_id": selected.get("asset_id"),
        "path": selected.get("path"),
        "asset_type": "mesh",
        "authorization_status": selected.get("authorization_status", "unknown"),
        "sha256": selected.get("sha256"),
        "shader_name": None,
        "tags": [],
        "slot_roles": [],
        "selection_basis": basis + ["mesh path is selected from imported local FBX inventory, not guessed from a Prefab YAML field"],
        "verification": verification,
    }


def build_asset_route_plan(
    graph: dict[str, Any],
    material_audit_path: Path,
    texture_tag_path: Path,
    mesh_root: Path,
    mesh_audit_path: Path | None = None,
    routes: Iterable[str] = ROUTE_KINDS,
    prompt: str | None = None,
    effect_family: str | None = None,
    style_family: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    route_names = list(dict.fromkeys(routes))
    if sorted(route_names) != sorted(ROUTE_KINDS):
        raise ValueError(f"asset route plan must cover exactly {ROUTE_KINDS}")
    materials = _material_catalog(material_audit_path, _tag_index(texture_tag_path))
    meshes = _mesh_catalog(mesh_root, mesh_audit_path)
    output_routes: list[dict[str, Any]] = []
    for route_kind in route_names:
        material, texture = _select_material(materials, route_kind)
        material_basis = [f"route kind is {route_kind}", "material and texture are joined through audited Unity property bindings"]
        mesh_basis = ["mesh route requires vertex data, UV cardinality and bounds from Unity AssetDatabase"]
        mesh = _mesh_asset(meshes, route_kind, mesh_basis)
        target = _route_component(graph, route_kind)
        if route_kind == "mesh_particle" and mesh and mesh.get("verification") != "unity_api_geometry_audit_pass":
            status = "needs_unity_validation"
        elif route_kind == "mesh_particle" and mesh is None:
            status = "blocked"
        else:
            status = "pass"
        compatibility = {
            "shader_name": material["shader_name"],
            "shader_allowed": material["shader_name"] in LEGACY_ALLOWED_SHADERS,
            "required_texture_slots": ["_MainTex"],
            "texture_slot_satisfied": texture["path"] is not None,
            "renderer_route": route_kind,
        }
        if route_kind == "mesh_particle":
            compatibility.update({"axis_space": "unity_local", "pivot_mode": "source_import_pivot", "uv_required": True, "mesh_audit": mesh.get("verification") if mesh else None, "requires_component_creation": target is None})
        elif route_kind == "impact_decal":
            compatibility.update({"geometry": "quad", "surface_alignment": "normal", "alpha_mask_required": True})
        else:
            compatibility.update({"geometry": "particle_billboard", "alpha_or_emission_texture_required": True})
        output_routes.append({
            "route_id": f"{graph['graph_id']}_{route_kind}",
            "route_kind": route_kind,
            "target_component_id": target,
            "material": _material_asset(material, material_basis),
            "texture": _texture_asset(texture, material_basis + ["texture content tags are used for slot role selection"]),
            "mesh": mesh,
            "compatibility": compatibility,
            "selection_basis": material_basis + (mesh_basis + (["no Mesh Renderer exists in this Graph; downstream compiler must create an explicit mesh-particle binding"] if target is None else []) if route_kind == "mesh_particle" else ["route geometry is explicit and does not imply a source Prefab dependency"]),
            "status": status,
        })
    status = "pass" if all(route["status"] == "pass" for route in output_routes) else "needs_unity_validation" if all(route["status"] != "blocked" for route in output_routes) else "blocked"
    plan = {
        "schema_version": ROUTE_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": f"asset_route_{graph['graph_id']}",
        "graph_id": graph["graph_id"],
        "condition": {"prompt": prompt, "effect_family": effect_family, "style_family": style_family, "seed": seed},
        "routes": output_routes,
        "selection_policy": {
            "material_selection": "shader_property_and_texture_slot_compatibility",
            "texture_selection": "content_tag_and_slot_role",
            "mesh_selection": "unity_api_geometry_audit",
            "no_silent_fallback": True,
        },
        "status": status,
    }
    _validate(plan)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a verified Prefab asset route plan.")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--material-audit", type=Path, required=True)
    parser.add_argument("--texture-tags", type=Path, required=True)
    parser.add_argument("--mesh-root", type=Path, required=True)
    parser.add_argument("--mesh-audit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt")
    parser.add_argument("--effect-family")
    parser.add_argument("--style-family")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args(argv)
    try:
        graph = _read_json(args.graph.resolve())
        plan = build_asset_route_plan(graph, args.material_audit, args.texture_tags, args.mesh_root, args.mesh_audit, prompt=args.prompt, effect_family=args.effect_family, style_family=args.style_family, seed=args.seed)
        path = _write_json(args.output.resolve(), plan)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": plan["status"] == "pass", "output": path.as_posix(), "status": plan["status"]}, ensure_ascii=False, indent=2))
    return 0 if plan["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
