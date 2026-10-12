"""Route original Material/Shader/Texture tuples under ProposalPlan contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .material_plan import COLOR_TERMS, FAMILY_TAGS, ROLE_PROPERTIES, STYLE_TERMS
from .shader_material_contract import canonical_layer_role, renderer_mode_compatible, shader_contract_pass, shader_features


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _texture_groups_pass(tags: set[str], contract: dict[str, Any]) -> bool:
    return all(set(group).intersection(tags) for group in contract["required_any"]) and not set(contract["forbidden_tags"]).intersection(tags)


def _candidate_score(
    material: dict[str, Any],
    shader: dict[str, Any],
    texture: dict[str, Any],
    role: str,
    intent: dict[str, Any],
    features: set[str],
    pairing_preserved: bool,
) -> dict[str, float]:
    tags = set(texture.get("tags") or [])
    searchable = f"{material.get('material_path')} {shader.get('shader_name')} {texture.get('project_asset_path')}".lower()
    family = str(intent["effect_family"])
    style = str(intent["style_family"])
    family_score = sum(10.0 for tag in FAMILY_TAGS.get(family, ()) if tag in tags)
    role_score = sum(8.0 for tag in tags if tag.startswith("role."))
    slot_score = sum(6.0 for tag in tags if tag.startswith("slot."))
    style_score = sum(4.0 for term in STYLE_TERMS.get(style, ()) if term in searchable)
    color_score = sum(3.0 for color in intent.get("color_keywords") or [] for term in COLOR_TERMS.get(color, (color,)) if term in searchable)
    pipeline_score = 8.0 if "urp" in shader.get("pipeline_tags", []) else 3.0 if "builtin" in shader.get("pipeline_tags", []) else 0.0
    max_size = max(int(texture.get("width") or 0), int(texture.get("height") or 0))
    performance_score = 4.0 if max_size <= 1024 else -2.0
    pairing_score = 32.0 if pairing_preserved else 0.0
    diversity = int(hashlib.sha256(f"{role}|{material['material_id']}|{texture['asset_id']}".encode("utf-8")).hexdigest()[:6], 16) / float(16**6 - 1)
    capability_score = float(len(features.intersection({"emission_control", "dissolve_control", "cutout_control", "uv_motion", "distortion"})) * 5)
    total = family_score + role_score + slot_score + style_score + color_score + pipeline_score + performance_score + pairing_score + diversity + capability_score
    return {
        "family": family_score,
        "role": role_score,
        "slot": slot_score,
        "style": style_score,
        "color": color_score,
        "pipeline": pipeline_score,
        "performance": performance_score,
        "pairing": pairing_score + capability_score,
        "diversity": round(diversity, 6),
        "total": round(total, 6),
    }


def _material_candidates(
    registry: dict[str, Any],
    role: str,
    contract: dict[str, Any],
    intent: dict[str, Any],
    renderer_mode: str,
) -> list[dict[str, Any]]:
    shaders = {row["asset_id"]: row for row in registry["shaders"] if row.get("binding_status") == "project_bindable" and (row.get("compiler") or {}).get("is_supported")}
    textures = {row["asset_id"]: row for row in registry["textures"] if row.get("binding_status") == "project_bindable" and row.get("project_asset_path")}
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append_candidate(material: dict[str, Any], shader: dict[str, Any], texture: dict[str, Any], property_name: str, features: set[str], pairing_preserved: bool) -> None:
        identity = f"{role}|{material['material_id']}|{texture['asset_id']}|{property_name}|{pairing_preserved}"
        candidate_id = "proposal_asset_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        if candidate_id in seen:
            return
        seen.add(candidate_id)
        candidates.append({
            "candidate_id": candidate_id,
            "material": {"material_id": material["material_id"], "path": material["material_path"], "binding_status": "usable"},
            "shader": {"asset_id": shader["asset_id"], "name": shader.get("shader_name"), "path": shader["path"], "binding_status": "project_bindable", "pipeline_tags": list(shader.get("pipeline_tags") or [])},
            "texture": {"asset_id": texture["asset_id"], "path": texture["project_asset_path"], "binding_status": "project_bindable", "tags": sorted(set(texture.get("tags") or []))},
            "texture_property_name": property_name,
            "scores": _candidate_score(material, shader, texture, role, intent, features, pairing_preserved),
            "selection_basis": [
                "original Unity Material-Shader-Texture binding is preserved" if pairing_preserved else "controlled texture rebind passed Shader property and semantic contracts",
                f"layer_role={role}",
                "shader capability contract passed",
                "texture semantic contract passed",
                "Unity compile, readback and runtime validation remain required",
            ],
            "status": "pass",
        })

    compatible_materials = []
    for material in registry["materials"]:
        if material.get("binding_status") != "usable" or material.get("source_group") == "VFXGenerated":
            continue
        shader = shaders.get(material.get("shader_asset_id"))
        if shader is None:
            continue
        features = shader_features(shader, material)
        shader_ok, _, _ = shader_contract_pass(features, contract["shader_contract"])
        if not shader_ok or not renderer_mode_compatible(features, renderer_mode):
            continue
        compatible_materials.append((material, shader, features))
        shader_properties = set(shader.get("property_names") or [])
        preferred_properties = ROLE_PROPERTIES[role]
        for binding in material.get("texture_bindings") or []:
            if not binding.get("is_bound") or not binding.get("texture_asset_id"):
                continue
            property_name = str(binding.get("property_name") or "")
            if property_name not in shader_properties or property_name not in preferred_properties:
                continue
            texture = textures.get(binding["texture_asset_id"])
            if texture is None:
                continue
            tags = set(texture.get("tags") or [])
            if not _texture_groups_pass(tags, contract["texture_contract"]):
                continue
            append_candidate(material, shader, texture, property_name, features, True)

    texture_pool = [texture for texture in textures.values() if _texture_groups_pass(set(texture.get("tags") or []), contract["texture_contract"])]
    family_tags = set(FAMILY_TAGS.get(str(intent["effect_family"]), ()))
    texture_pool.sort(key=lambda row: (-len(family_tags.intersection(set(row.get("tags") or []))), str(row["asset_id"])))
    for material, shader, features in compatible_materials:
        shader_properties = set(shader.get("property_names") or [])
        property_name = next((value for value in ROLE_PROPERTIES[role] if value in shader_properties), None)
        if property_name is None:
            continue
        original_pairs = {(str(row.get("property_name")), str(row.get("texture_asset_id"))) for row in material.get("texture_bindings") or [] if row.get("is_bound")}
        for texture in texture_pool[:64]:
            if (property_name, str(texture["asset_id"])) in original_pairs:
                continue
            append_candidate(material, shader, texture, property_name, features, False)
    candidates.sort(key=lambda row: (-float(row["scores"]["total"]), row["candidate_id"]))
    return candidates


def build_proposal_asset_plan(
    graph: dict[str, Any],
    registry: dict[str, Any],
    proposal_plan: dict[str, Any],
    *,
    alternatives_per_layer: int = 4,
) -> dict[str, Any]:
    if alternatives_per_layer < 1:
        raise ValueError("alternatives_per_layer must be positive")
    intent = proposal_plan["intent"]
    contract_by_role = {row["layer_role"]: row for row in proposal_plan["layers"]}
    layers = []
    selected_materials: set[str] = set()
    all_candidate_ids = []
    for index, particle in enumerate(graph.get("components", {}).get("particle_systems") or []):
        role = canonical_layer_role(particle, index)
        renderer_mode = str((particle.get("parameters") or {}).get("renderer_mode") or "")
        candidates = _material_candidates(registry, role, contract_by_role[role], intent, renderer_mode)
        component_id = str(particle["component_id"])
        for candidate in candidates:
            source_candidate_id = candidate["candidate_id"]
            candidate["candidate_id"] = "proposal_asset_" + hashlib.sha256(f"{component_id}|{source_candidate_id}".encode("utf-8")).hexdigest()[:16]
            candidate["selection_basis"].append(f"component_id={component_id}")
        if candidates:
            preferred = next((row for row in candidates if row["material"]["material_id"] not in selected_materials), candidates[0])
            ordered = [preferred] + [row for row in candidates if row["candidate_id"] != preferred["candidate_id"]]
            selected = ordered[:alternatives_per_layer]
            selected_materials.add(preferred["material"]["material_id"])
        else:
            selected = []
        all_candidate_ids.extend(row["candidate_id"] for row in selected)
        layers.append({
            "component_id": component_id,
            "node_id": particle["node_id"],
            "layer_role": role,
            "selected_candidate_id": selected[0]["candidate_id"] if selected else None,
            "candidates": selected,
            "status": "pass" if selected else "blocked",
            "blocking_reasons": [] if selected else ["no_original_asset_tuple_satisfies_procedure_and_role_contract"],
        })
    selected = [layer["candidates"][0] for layer in layers if layer["candidates"]]
    gates = {
        "duplicate_candidate_ids": len(all_candidate_ids) - len(set(all_candidate_ids)),
        "reference_shaders_selected": sum(row["shader"]["binding_status"] != "project_bindable" for row in selected),
        "nonproject_textures_selected": sum(row["texture"]["binding_status"] != "project_bindable" for row in selected),
        "blocked_materials_selected": sum(row["material"]["binding_status"] != "usable" for row in selected),
        "selected_layer_count": len(selected),
        "layer_count": len(layers),
    }
    plan = {
        "schema_version": "vfx_material_plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": f"material_plan_{graph['graph_id']}",
        "graph_id": graph["graph_id"],
        "registry_id": registry["manifest"]["registry_id"],
        "condition": {
            "prompt": proposal_plan["prompt"],
            "effect_family": intent["effect_family"],
            "style_family": intent["style_family"],
            "color_keywords": intent["color_keywords"],
            "performance_tier": "standard",
            "seed": proposal_plan["seed"],
        },
        "layers": layers,
        "selection_policy": {
            "shader_texture_joint_ranking": True,
            "prompt_conditioned": True,
            "project_bindable_only": True,
            "no_silent_fallback": True,
            "alternatives_per_layer": alternatives_per_layer,
            "neural_asset_pair_ranking": False,
        },
        "quality_gates": gates,
        "status": "pass" if layers and all(row["status"] == "pass" for row in layers) and not any(value for key, value in gates.items() if key not in {"selected_layer_count", "layer_count"}) else "blocked",
    }
    schema = json.loads((_repo_root() / "workspace/data/vfx_generation/schemas/material_plan.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(plan), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"proposal asset plan schema error at {location}: {errors[0].message}")
    return plan
