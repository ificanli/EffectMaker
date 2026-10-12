"""Reject renderable-but-semantic-mismatched Shader, Material and Texture plans."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .material_plan import load_registry
from .proposal_plan import build_proposal_plan


ROLE_ALIASES = {
    "core": "core",
    "main_bolt": "core",
    "outer_blade": "core",
    "core_flash": "core",
    "support": "support",
    "branch_support": "support",
    "inner_support": "support",
    "shockwave_ring": "support",
    "hit": "hit",
    "contact_hit": "hit",
    "impact_flash": "hit",
    "debris_burst": "hit",
    "residual": "residual",
    "direction_trail": "residual",
    "residual_spark": "residual",
    "residual_smoke": "residual",
}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def canonical_layer_role(particle: dict[str, Any], index: int) -> str:
    parameters = particle.get("parameters") or {}
    serialized = parameters.get("serialized_modules") or {}
    source = str(serialized.get("layer_role") or parameters.get("layer_role") or "").strip().lower()
    if source in ROLE_ALIASES:
        return ROLE_ALIASES[source]
    return ("core", "support", "hit", "residual")[min(index, 3)]


def shader_features(shader: dict[str, Any], material: dict[str, Any]) -> set[str]:
    properties = {str(value).lower() for value in shader.get("property_names") or []}
    shader_keywords = {str(value).lower() for value in shader.get("keywords") or []}
    material_keywords = {str(value).lower() for value in material.get("keywords") or []}
    searchable = " ".join(
        [
            str(shader.get("shader_name") or ""),
            str(shader.get("path") or ""),
            *properties,
            *shader_keywords,
        ]
    ).lower()
    features = {"base_texture"} if any("tex" in value or "map" in value for value in properties) else set()
    if any(term in searchable for term in ("opacity", "alpha", "cutout", "tintcolor", "basecolor", "_color")):
        features.add("opacity_control")
    if any(term in searchable for term in ("tintcolor", "basecolor", "emissioncolor", "dissolvecolor", "addcolor", "_color")):
        features.add("color_control")
    if any(term in searchable for term in ("emission", "emissive", "glow")):
        features.add("emission_control")
    if any(term in searchable for term in ("blend_add", "additive", "particles/add")) or any("blend_add" in value for value in material_keywords):
        features.add("additive_blend")
    if "dissolve" in searchable:
        features.add("dissolve_control")
    if any(term in searchable for term in ("cutout", "alphacutout", "maskclip")):
        features.add("cutout_control")
    if any(term in searchable for term in ("speed", "flow", "panner", "tilingoffset", "uvgradient")):
        features.add("uv_motion")
    if any(term in searchable for term in ("distortion", "distort", "refract")):
        features.add("distortion")
    if "radial" in searchable:
        features.add("radial_mask")
    if "spherical" in searchable:
        features.add("spherical_distortion")
    if any(term in searchable for term in ("softparticles", "invfade")):
        features.add("soft_particles")
    if "trail" in str(shader.get("shader_name") or "").lower() or "/trail/" in str(shader.get("path") or "").lower():
        features.add("trail_shader")
    if str(shader.get("shader_name") or "") == "Hovl/Particles/SwordSlash":
        features.add("mesh_effect_shader")
    if str(shader.get("shader_name") or "") == "Hovl/Particles/SwordSlash" or "speedmaintexuvnoisezw" in searchable:
        features.add("custom_vertex_stream_required")
    return features


def renderer_mode_compatible(features: set[str], renderer_mode: str) -> bool:
    normalized = renderer_mode.lower()
    if "trail_shader" in features and normalized not in {"trail", "stretch", "stretchedbillboard"}:
        return False
    if "mesh_effect_shader" in features and normalized != "mesh":
        return False
    return True


def _vertex_stream_contract_present(graph: dict[str, Any], node_id: str) -> bool:
    for renderer in graph.get("components", {}).get("renderers") or []:
        if renderer.get("node_id") != node_id:
            continue
        parameters = renderer.get("parameters") or {}
        streams = parameters.get("active_vertex_streams") or []
        return bool(streams)
    return False


def shader_contract_pass(features: set[str], contract: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    missing = [value for value in contract["required_all"] if value not in features]
    missing_groups = []
    for group in contract["required_any"]:
        if not any(value in features for value in group):
            missing_groups.append("|".join(group))
    required = [f"all:{value}" for value in contract["required_all"]]
    required.extend(f"any:{'|'.join(group)}" for group in contract["required_any"])
    reasons = [f"missing_shader_feature:{value}" for value in missing]
    reasons.extend(f"missing_shader_feature_group:{value}" for value in missing_groups)
    reasons.extend(f"forbidden_shader_feature:{value}" for value in contract.get("forbidden") or [] if value in features)
    return not reasons, required, reasons


def audit_graph_contract(
    graph: dict[str, Any],
    registry: dict[str, Any],
    proposal_plan: dict[str, Any],
) -> dict[str, Any]:
    family = str(proposal_plan["intent"]["effect_family"])
    material_by_path = {str(row.get("material_path")): row for row in registry["materials"]}
    shader_by_id = {str(row.get("asset_id")): row for row in registry["shaders"]}
    texture_by_path = {str(row.get("project_asset_path")): row for row in registry["textures"]}
    contract_by_role = {row["layer_role"]: row for row in proposal_plan["layers"]}
    layers = []
    missing_asset_count = 0
    shader_mismatch_count = 0
    texture_mismatch_count = 0
    vertex_stream_missing_count = 0
    template_paths = []
    roles = []

    for index, particle in enumerate(graph.get("components", {}).get("particle_systems") or []):
        parameters = particle.get("parameters") or {}
        role = canonical_layer_role(particle, index)
        roles.append(role)
        contract = contract_by_role[role]
        material_path = parameters.get("material_template_path")
        texture_path = parameters.get("texture_asset_path")
        template_paths.append(str(material_path or ""))
        material = material_by_path.get(str(material_path))
        shader = shader_by_id.get(str((material or {}).get("shader_asset_id")))
        texture = texture_by_path.get(str(texture_path))
        reasons = []
        if material is None:
            reasons.append("material_not_in_verified_registry")
            missing_asset_count += 1
        if shader is None or shader.get("binding_status") != "project_bindable" or not (shader.get("compiler") or {}).get("is_supported"):
            reasons.append("shader_not_verified_project_bindable")
            missing_asset_count += 1
        if texture is None or texture.get("binding_status") != "project_bindable":
            reasons.append("texture_not_verified_project_bindable")
            missing_asset_count += 1
        features = shader_features(shader or {}, material or {})
        shader_ok, required_features, shader_reasons = shader_contract_pass(features, contract["shader_contract"])
        if not shader_ok:
            reasons.extend(shader_reasons)
            shader_mismatch_count += 1
        if not renderer_mode_compatible(features, str(parameters.get("renderer_mode") or "")):
            reasons.append("shader_renderer_mode_mismatch")
            shader_mismatch_count += 1
        texture_tags = sorted(set((texture or {}).get("tags") or []))
        required_tag_groups = [set(group) for group in contract["texture_contract"]["required_any"]]
        forbidden_tags = set(contract["texture_contract"]["forbidden_tags"])
        if texture is not None:
            for group in required_tag_groups:
                if not group.intersection(texture_tags):
                    reasons.append("texture_missing_role_tag:" + "|".join(sorted(group)))
                    texture_mismatch_count += 1
        if forbidden_tags.intersection(texture_tags):
            reasons.append("texture_has_forbidden_tag")
            texture_mismatch_count += 1
        if "custom_vertex_stream_required" in features and not _vertex_stream_contract_present(graph, str(particle.get("node_id"))):
            reasons.append("required_particle_vertex_stream_contract_missing")
            vertex_stream_missing_count += 1
        layers.append({
            "component_id": str(particle.get("component_id") or ""),
            "layer_role": role,
            "renderer_mode": str(parameters.get("renderer_mode") or ""),
            "material_path": material_path,
            "shader_name": (shader or {}).get("shader_name"),
            "texture_path": texture_path,
            "shader_features": sorted(features),
            "required_features": required_features,
            "texture_tags": texture_tags,
            "blocking_reasons": sorted(set(reasons)),
            "status": "blocked" if reasons else "pass",
        })

    meaningful_roles = set(roles)
    nonempty_templates = {value for value in template_paths if value}
    single_template_all_roles = len(meaningful_roles) >= 3 and len(nonempty_templates) == 1

    blocked = sum(row["status"] == "blocked" for row in layers)
    gates = {
        "layer_count": len(layers),
        "blocked_layer_count": blocked,
        "missing_asset_count": missing_asset_count,
        "shader_role_mismatch_count": shader_mismatch_count,
        "texture_role_mismatch_count": texture_mismatch_count,
        "single_template_all_roles": single_template_all_roles,
        "vertex_stream_contract_missing_count": vertex_stream_missing_count,
    }
    status = "pass" if layers and blocked == 0 else "blocked"
    audit = {
        "schema_version": "shader_material_contract_audit.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "graph_id": graph["graph_id"],
        "effect_family": family,
        "registry_id": registry["manifest"]["registry_id"],
        "evidence_scope": "static_heuristic_only",
        "layers": layers,
        "quality_gates": gates,
        "training_eligibility": {
            "positive_generation_supervision": False,
            "proposal_failure_supervision": status == "blocked",
            "reason": "Static matching is a candidate-screening hint; runtime compatibility and overall quality require separate evidence.",
        },
        "status": status,
    }
    schema = _read(_repo_root() / "workspace/data/vfx_generation/schemas/shader_material_contract_audit.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(audit), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"shader contract audit schema error at {location}: {errors[0].message}")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a generated PrefabGraph against role-specific render contracts.")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--effect-family", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--proposal-output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        graph = _read(args.graph.resolve())
        registry = load_registry(args.registry.resolve())
        proposal = build_proposal_plan(args.prompt, args.effect_family, args.seed)
        audit = audit_graph_contract(graph, registry, proposal)
        proposal_path = _write(args.proposal_output.resolve(), proposal)
        audit_path = _write(args.audit_output.resolve(), audit)
    except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "proposal": proposal_path.as_posix(), "audit": audit_path.as_posix(), "status": audit["status"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
