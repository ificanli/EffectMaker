"""Jointly rank bindable Shader, Material and Texture assets for generated VFX layers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .prefab_graph import assign_graph_id
from .material_asset_pair_model import score_pair


ROLE_ORDER = ("core", "support", "hit", "residual")
FAMILY_TAGS = {
    "fire": ("semantic.fire", "semantic.spark", "semantic.smoke"),
    "lightning": ("semantic.lightning", "semantic.spark", "semantic.trail"),
    "slash": ("semantic.slash", "semantic.trail", "semantic.spark"),
    "explosion": ("semantic.fire", "semantic.smoke", "semantic.ring", "semantic.spark"),
    "impact": ("semantic.fire", "semantic.ring", "semantic.spark", "semantic.trail"),
    "laser": ("semantic.energy", "semantic.trail", "semantic.spark"),
    "smoke": ("semantic.smoke", "semantic.noise"),
    "magic_circle": ("semantic.magic_circle", "semantic.ring", "semantic.gradient"),
    "shield": ("semantic.ring", "semantic.magic_circle", "semantic.noise"),
    "water": ("semantic.water", "semantic.trail", "semantic.noise"),
    "ice": ("semantic.ice", "semantic.spark", "semantic.noise"),
}
ROLE_TAGS = {
    "core": ("role.core_shape", "slot.base_map", "luma.bright_core"),
    "support": ("role.noise_control", "slot.dissolve_map", "slot.distortion_map"),
    "hit": ("role.hit_accent", "role.impact_ring", "slot.emission_map"),
    "residual": ("role.residual_trail", "semantic.smoke", "semantic.trail"),
}
ROLE_PROPERTIES = {
    "core": ("_MainTex", "_BaseMap", "_MainTexture", "_BaseTex"),
    "support": ("_NoiseTex", "_DissolveTex", "_MaskTex", "_MainTex", "_BaseMap"),
    "hit": ("_EmissionMap", "_MainTex", "_BaseMap", "_MaskTex"),
    "residual": ("_MainTex", "_BaseMap", "_NoiseTex", "_MaskTex"),
}
SLOT_TAGS = {
    "core": ("slot.base_map", "slot.alpha_mask"),
    "support": ("slot.dissolve_map", "slot.distortion_map", "slot.alpha_mask"),
    "hit": ("slot.emission_map", "slot.alpha_mask"),
    "residual": ("slot.base_map", "slot.alpha_mask", "slot.dissolve_map"),
}
STYLE_TERMS = {
    "cartoon": ("toon", "cartoon"),
    "stylized": ("stylized", "toon", "hovl", "qfx", "erb"),
    "realistic": ("real", "realistic", "standard"),
    "anime": ("anime", "manga"),
}
COLOR_TERMS = {
    "blue": ("blue", "cyan", "lan"), "cyan": ("cyan", "blue"), "red": ("red",),
    "orange": ("orange", "fire"), "purple": ("purple", "violet"), "green": ("green",), "white": ("white",),
}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_registry(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / "registry_manifest.json")
    if manifest.get("schema_version") != "vfx_asset_capability_registry.v1" or manifest.get("status") != "pass":
        raise ValueError(f"verified asset capability registry required: {root}")
    return {
        "manifest": manifest,
        "textures": _read_jsonl(root / "textures.jsonl"),
        "shaders": _read_jsonl(root / "shaders.jsonl"),
        "materials": _read_jsonl(root / "materials.jsonl"),
    }


def _hash_float(value: str) -> float:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16) / float(16**8 - 1)


def _property(material: dict[str, Any], shader: dict[str, Any], role: str) -> str | None:
    texture_properties = [str(row["property_name"]) for row in material.get("texture_bindings") or []]
    shader_properties = {str(value) for value in shader.get("property_names") or [] if str(value)}
    if shader_properties:
        texture_properties = [value for value in texture_properties if value in shader_properties]
    for preferred in ROLE_PROPERTIES[role]:
        if preferred in texture_properties:
            return preferred
    return sorted(texture_properties)[0] if texture_properties else None


def _score_texture(texture: dict[str, Any], family: str, role: str, colors: list[str]) -> tuple[float, float, float, float]:
    tags = set(texture.get("tags") or [])
    path = str(texture.get("project_asset_path") or "").lower()
    family_score = max((24.0 if tag in tags else 0.0 for tag in FAMILY_TAGS.get(family, ())), default=0.0)
    role_score = sum(10.0 for tag in ROLE_TAGS[role] if tag in tags)
    slot_score = sum(8.0 for tag in SLOT_TAGS[role] if tag in tags)
    color_score = sum(5.0 for color in colors for term in COLOR_TERMS.get(color, (color,)) if term in path)
    if "alpha.opaque" in tags:
        slot_score -= 12.0
    if "analysis.error" in tags:
        slot_score -= 4.0
    return family_score, role_score, slot_score, color_score


def _pair_candidate(material: dict[str, Any], shader: dict[str, Any], texture: dict[str, Any], role: str, condition: dict[str, Any], seed: int, asset_pair_model: Any = None) -> dict[str, Any] | None:
    property_name = _property(material, shader, role)
    if property_name is None:
        return None
    family = str(condition["effect_family"])
    style = str(condition["style_family"])
    colors = list(condition.get("color_keywords") or [])
    family_score, role_score, slot_score, color_score = _score_texture(texture, family, role, colors)
    searchable = f"{material['material_path']} {shader.get('shader_name')} {texture.get('project_asset_path')}".lower()
    style_score = sum(6.0 for term in STYLE_TERMS.get(style, ()) if term in searchable)
    pipeline_score = 14.0 if "urp" in shader.get("pipeline_tags", []) else 4.0 if "builtin" in shader.get("pipeline_tags", []) else 0.0
    max_size = max(int(texture.get("width") or 0), int(texture.get("height") or 0))
    property_count = len(material.get("property_names") or [])
    if condition.get("performance_tier") == "mobile":
        performance_score = (8.0 if max_size <= 512 else -8.0) + (6.0 if property_count <= 40 else -4.0)
    else:
        performance_score = 3.0 if max_size <= 1024 else -2.0
    original_binding = any(
        row.get("property_name") == property_name and row.get("texture_asset_id") == texture["asset_id"]
        for row in material.get("texture_bindings") or []
    )
    texture_source_group = str((texture.get("importer") or {}).get("source_group") or "")
    pairing_score = 32.0 if original_binding else 8.0 if texture_source_group and texture_source_group == material.get("source_group") else 0.0
    diversity = round(_hash_float(f"{seed}|{role}|{material['material_id']}|{texture['asset_id']}") * 2.0, 6)
    total = family_score + role_score + slot_score + style_score + color_score + pipeline_score + performance_score + pairing_score + diversity
    candidate_id = "material_candidate_" + hashlib.sha256(f"{material['material_id']}|{texture['asset_id']}|{property_name}|{role}".encode("utf-8")).hexdigest()[:16]
    scores: dict[str, float] = {"family": family_score, "role": role_score, "slot": slot_score, "style": style_score, "color": color_score, "pipeline": pipeline_score, "performance": performance_score, "pairing": pairing_score, "diversity": diversity, "total": round(total, 6)}
    if asset_pair_model is not None:
        neural_probability = score_pair(asset_pair_model, material, shader, texture, role, condition)
        scores["neural_probability"] = round(neural_probability, 6)
        scores["rank_total"] = round(total + (neural_probability - 0.5) * 40.0, 6)
    return {
        "candidate_id": candidate_id,
        "material": {"material_id": material["material_id"], "path": material["material_path"], "binding_status": material["binding_status"]},
        "shader": {"asset_id": shader["asset_id"], "name": shader.get("shader_name"), "path": shader["path"], "binding_status": shader["binding_status"], "pipeline_tags": list(shader.get("pipeline_tags") or [])},
        "texture": {"asset_id": texture["asset_id"], "path": texture["project_asset_path"], "binding_status": texture["binding_status"], "tags": list(texture.get("tags") or [])},
        "texture_property_name": property_name,
        "scores": scores,
        "selection_basis": ["material, Shader and Texture are jointly ranked", f"effect_family={family}", f"style_family={style}", f"layer_role={role}", f"texture_property={property_name}", "all selected assets are project_bindable", "prior Unity Material property binding is preferred when available"],
        "status": "pass",
    }


def _diverse_top(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected = []
    texture_ids = set()
    for candidate in candidates:
        texture_id = candidate["texture"]["asset_id"]
        if texture_id in texture_ids:
            continue
        selected.append(candidate)
        texture_ids.add(texture_id)
        if len(selected) >= limit:
            return selected
    for candidate in candidates:
        if candidate["candidate_id"] in {row["candidate_id"] for row in selected}:
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def build_material_plan(graph: dict[str, Any], registry: dict[str, Any], condition: dict[str, Any], *, seed: int, alternatives_per_layer: int = 4, asset_pair_model: Any = None) -> dict[str, Any]:
    if alternatives_per_layer < 1:
        raise ValueError("alternatives_per_layer must be positive")
    textures = [row for row in registry["textures"] if row.get("binding_status") == "project_bindable" and row.get("project_asset_path")]
    shaders = {row["asset_id"]: row for row in registry["shaders"] if row.get("binding_status") == "project_bindable" and str(row.get("path") or "").startswith("Assets/")}
    materials = [row for row in registry["materials"] if row.get("binding_status") == "usable" and row.get("shader_asset_id") in shaders and row.get("source_group") != "VFXGenerated"]
    layers = []
    all_candidate_ids = []
    for index, particle in enumerate(graph.get("components", {}).get("particle_systems") or []):
        role = ROLE_ORDER[min(index, len(ROLE_ORDER) - 1)]
        texture_rank = sorted(textures, key=lambda row: (-sum(_score_texture(row, str(condition["effect_family"]), role, list(condition.get("color_keywords") or []))), row["asset_id"]))[:64]
        candidates = []
        for material in materials:
            shader = shaders[material["shader_asset_id"]]
            for texture in texture_rank:
                candidate = _pair_candidate(material, shader, texture, role, condition, seed)
                if candidate is not None:
                    candidates.append(candidate)
        candidates.sort(key=lambda row: (-float(row["scores"]["total"]), row["candidate_id"]))
        if asset_pair_model is not None:
            material_by_id = {str(row["material_id"]): row for row in materials}
            texture_by_id = {str(row["asset_id"]): row for row in textures}
            shader_by_id = {str(row["asset_id"]): row for row in shaders.values()}
            neural_pool = candidates[:min(len(candidates), max(64, alternatives_per_layer * 16))]
            for candidate in neural_pool:
                material = material_by_id[candidate["material"]["material_id"]]
                shader = shader_by_id[candidate["shader"]["asset_id"]]
                texture = texture_by_id[candidate["texture"]["asset_id"]]
                neural_probability = score_pair(asset_pair_model, material, shader, texture, role, condition)
                candidate["scores"]["neural_probability"] = round(neural_probability, 6)
                candidate["scores"]["rank_total"] = round(float(candidate["scores"]["total"]) + (neural_probability - 0.5) * 40.0, 6)
            candidates.sort(key=lambda row: (-float(row["scores"].get("rank_total", row["scores"]["total"])), row["candidate_id"]))
        selected = _diverse_top(candidates, alternatives_per_layer)
        all_candidate_ids.extend(row["candidate_id"] for row in selected)
        layers.append({
            "component_id": particle["component_id"],
            "node_id": particle["node_id"],
            "layer_role": role,
            "selected_candidate_id": selected[0]["candidate_id"] if selected else None,
            "candidates": selected,
            "status": "pass" if selected else "blocked",
            "blocking_reasons": [] if selected else ["no_project_bindable_shader_material_texture_pair"],
        })
    selected_candidates = [layer["candidates"][0] for layer in layers if layer["candidates"]]
    gates = {
        "duplicate_candidate_ids": len(all_candidate_ids) - len(set(all_candidate_ids)),
        "reference_shaders_selected": sum(row["shader"]["binding_status"] != "project_bindable" for row in selected_candidates),
        "nonproject_textures_selected": sum(row["texture"]["binding_status"] != "project_bindable" for row in selected_candidates),
        "blocked_materials_selected": sum(row["material"]["binding_status"] != "usable" for row in selected_candidates),
        "selected_layer_count": len(selected_candidates),
        "layer_count": len(layers),
    }
    plan = {
        "schema_version": "vfx_material_plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": f"material_plan_{graph['graph_id']}",
        "graph_id": graph["graph_id"],
        "registry_id": registry["manifest"]["registry_id"],
        "condition": {"prompt": str(condition.get("text") or condition.get("prompt") or ""), "effect_family": str(condition["effect_family"]), "style_family": str(condition["style_family"]), "color_keywords": sorted(set(condition.get("color_keywords") or [])), "performance_tier": str(condition.get("performance_tier") or "standard"), "seed": seed},
        "layers": layers,
        "selection_policy": {"shader_texture_joint_ranking": True, "prompt_conditioned": True, "project_bindable_only": True, "no_silent_fallback": True, "alternatives_per_layer": alternatives_per_layer, "neural_asset_pair_ranking": asset_pair_model is not None},
        "quality_gates": gates,
        "status": "pass" if layers and all(layer["status"] == "pass" for layer in layers) and not any(value for key, value in gates.items() if key not in {"selected_layer_count", "layer_count"}) else "blocked",
    }
    validator = Draft202012Validator(_read_json(_repo_root() / "workspace/data/vfx_generation/schemas/material_plan.schema.json"))
    errors = list(validator.iter_errors(plan))
    if errors:
        raise ValueError(f"MaterialPlan schema error: {errors[0].message}")
    return plan


def apply_material_plan(graph: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("status") != "pass":
        raise ValueError("cannot apply a blocked MaterialPlan")
    value = json.loads(json.dumps(graph, ensure_ascii=False))
    particles = {row["component_id"]: row for row in value["components"]["particle_systems"]}
    material_paths = []
    for layer in plan["layers"]:
        selected = next(row for row in layer["candidates"] if row["candidate_id"] == layer["selected_candidate_id"])
        particle = particles[layer["component_id"]]
        particle["material_paths"] = []
        particle["parameters"]["material_template_path"] = selected["material"]["path"]
        particle["parameters"]["texture_asset_path"] = selected["texture"]["path"]
        particle["parameters"]["texture_property_name"] = selected["texture_property_name"]
        particle["parameters"]["texture_profile"] = None
        particle["parameters"]["shader_profile"] = None
        material_paths.append(selected["material"]["path"])
    for renderer in value["components"].get("renderers") or []:
        renderer["material_paths"] = []
    value["asset_bindings"]["materials"] = sorted(set(material_paths))
    return assign_graph_id(value)
