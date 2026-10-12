"""Build a shared Prompt-conditioned proposal contract before family generation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .procedure_spec import build_procedure_context, retrieve_procedures, steps_for_role


FAMILIES = {"slash", "lightning", "explosion", "fire", "shield"}
STYLE_TERMS = {
    "stylized": ("风格化", "stylized"),
    "cartoon": ("卡通", "cartoon", "toon"),
    "realistic": ("写实", "realistic"),
    "anime": ("二次元", "anime"),
}
COLOR_TERMS = {
    "blue": ("蓝", "blue"),
    "purple": ("紫", "purple", "violet"),
    "cyan": ("青", "cyan"),
    "red": ("红", "red"),
    "orange": ("橙", "orange"),
    "yellow": ("黄", "yellow"),
    "green": ("绿", "green"),
    "white": ("白", "white"),
    "black": ("黑", "black"),
}
DIRECTION_TERMS = {
    "horizontal": ("横向", "horizontal"),
    "vertical": ("纵向", "vertical"),
    "radial": ("径向", "环形", "radial"),
    "forward": ("向前", "前向", "forward"),
}
SHAPE_TERMS = {
    "sharp_outer_edge": ("外刃锐利", "锐利", "sharp"),
    "restrained_inner_layer": ("内层克制", "克制", "restrained"),
    "irregular_silhouette": ("不规则", "irregular"),
    "hard_edge": ("硬朗", "hard edge"),
    "soft_edge": ("柔和", "soft edge"),
}
TIMING_TERMS = {
    "fast_collapse_after_peak": ("峰值后快速收束", "快速收束", "fast collapse"),
    "instant_pulse": ("瞬时", "短促", "instant"),
    "persistent_residual": ("残留", "余韵", "persistent residual"),
    "staged_onset": ("分层出现", "依次出现", "staged"),
}

LAYER_PURPOSES = {
    "slash": {
        "core": "Carry the readable blade silhouette and outer cutting edge.",
        "support": "Reinforce the inner energy without competing with the blade edge.",
        "hit": "Mark contact at the leading edge instead of the composition center.",
        "residual": "Continue attack direction briefly and collapse after the peak.",
    },
    "lightning": {
        "core": "Carry the main bolt and instantaneous pulse.",
        "support": "Add thinner branches without obscuring the main bolt.",
        "hit": "Concentrate the electrical contact point.",
        "residual": "Leave short-lived residual sparks after the main pulse.",
    },
    "explosion": {
        "core": "Carry the ignition and peak energy mass.",
        "support": "Expand the shockwave and secondary volume.",
        "hit": "Provide the peak flash and high-frequency debris accent.",
        "residual": "Leave smoke, embers or dust after the peak.",
    },
    "fire": {
        "core": "Carry the hot core and primary flame silhouette.",
        "support": "Add turbulent tongues and darker separation.",
        "hit": "Accentuate ignition or contact.",
        "residual": "Leave smoke, embers or heat distortion.",
    },
    "shield": {
        "core": "Carry the readable shield boundary.",
        "support": "Add surface flow and internal structure.",
        "hit": "Localize impact response on the shield surface.",
        "residual": "Fade ripples and fragments without hiding the boundary.",
    },
}

TOPOLOGIES = {
    "slash": {
        "core": ["mesh_arc", "procedural_ribbon", "multi_segment_arc"],
        "support": ["inner_mesh_arc", "masked_ribbon", "thin_particle_band"],
        "hit": ["leading_edge_flash", "spark_cluster", "short_impact_ring"],
        "residual": ["directional_streaks", "tapered_trail", "sparse_afterimage"],
    },
    "lightning": {
        "core": ["single_bolt_strip", "segmented_bolt", "procedural_line"],
        "support": ["branch_strip", "fork_cluster", "secondary_line"],
        "hit": ["contact_flash", "electric_ring", "spark_cluster"],
        "residual": ["residual_sparks", "fading_branches", "surface_arcs"],
    },
    "explosion": {
        "core": ["billboard_volume", "flipbook_core", "mesh_burst"],
        "support": ["shockwave_ring", "secondary_fireball", "radial_streaks"],
        "hit": ["peak_flash", "debris_burst", "spark_shell"],
        "residual": ["smoke_volume", "ember_field", "dust_ring"],
    },
    "fire": {
        "core": ["flipbook_flame", "mesh_flame", "stacked_billboards"],
        "support": ["turbulence_layer", "dark_flame_layer", "heat_distortion"],
        "hit": ["ignition_flash", "ember_burst", "contact_flame"],
        "residual": ["smoke_column", "embers", "heat_haze"],
    },
    "shield": {
        "core": ["sphere_shell", "disc_shell", "segmented_barrier"],
        "support": ["flowing_surface", "hex_pattern", "inner_fresnel"],
        "hit": ["surface_ripple", "localized_crack", "impact_flash"],
        "residual": ["fading_ripple", "surface_sparks", "dissolve_fragments"],
    },
}

RENDERER_MODES = {
    "slash": {"core": ["Mesh", "Trail"], "support": ["Mesh", "Trail"], "hit": ["Billboard"], "residual": ["Stretch", "Trail"]},
    "lightning": {"core": ["Mesh", "Trail"], "support": ["Mesh", "Trail"], "hit": ["Billboard"], "residual": ["Stretch", "Trail"]},
    "explosion": {"core": ["Billboard", "Mesh"], "support": ["Billboard", "Mesh"], "hit": ["Billboard"], "residual": ["Billboard"]},
    "fire": {"core": ["Billboard", "Mesh"], "support": ["Billboard", "Mesh"], "hit": ["Billboard"], "residual": ["Billboard"]},
    "shield": {"core": ["Mesh"], "support": ["Mesh"], "hit": ["Billboard", "Mesh"], "residual": ["Billboard", "Mesh"]},
}

SHADER_CONTRACTS = {
    "core": {"required_all": ["opacity_control", "color_control"], "required_any": [["emission_control", "additive_blend"], ["dissolve_control", "cutout_control", "uv_motion"]]},
    "support": {"required_all": ["opacity_control", "color_control"], "required_any": [["dissolve_control", "cutout_control", "uv_motion", "distortion"]]},
    "hit": {"required_all": ["opacity_control", "color_control"], "required_any": [["emission_control", "additive_blend"]]},
    "residual": {"required_all": ["opacity_control", "color_control"], "required_any": [["uv_motion", "dissolve_control", "cutout_control"]]},
}

TEXTURE_TAGS = {
    "core": ["role.core_shape", "slot.base_map", "slot.alpha_mask"],
    "support": ["role.noise_control", "slot.dissolve_map", "slot.distortion_map"],
    "hit": ["role.hit_accent", "role.impact_ring", "semantic.spark"],
    "residual": ["role.residual_trail", "semantic.trail", "semantic.smoke"],
}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _matches(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def parse_prompt_intent(prompt: str, effect_family: str) -> dict[str, Any]:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    if effect_family not in FAMILIES:
        raise ValueError(f"unsupported effect family: {effect_family}")
    style = next((name for name, terms in STYLE_TERMS.items() if _matches(prompt, terms)), "unspecified")
    colors = sorted(name for name, terms in COLOR_TERMS.items() if _matches(prompt, terms))
    direction = next((name for name, terms in DIRECTION_TERMS.items() if _matches(prompt, terms)), "unspecified")
    shapes = sorted(name for name, terms in SHAPE_TERMS.items() if _matches(prompt, terms))
    timing = sorted(name for name, terms in TIMING_TERMS.items() if _matches(prompt, terms))
    if _matches(prompt, ("前端命中", "前端闪点", "leading edge")):
        hit_placement = "leading_edge"
    elif _matches(prompt, ("中心命中", "center hit")):
        hit_placement = "center"
    elif _matches(prompt, ("表面命中", "surface hit")):
        hit_placement = "surface"
    else:
        hit_placement = "unspecified"
    return {
        "effect_family": effect_family,
        "style_family": style,
        "color_keywords": colors,
        "direction": direction,
        "shape_keywords": shapes,
        "timing_keywords": timing,
        "hit_placement": hit_placement,
    }


def _prompt_controls(intent: dict[str, Any], role: str) -> list[str]:
    controls = ["style_family", "color_keywords"]
    if role in {"core", "support", "residual"} and intent["direction"] != "unspecified":
        controls.append("direction")
    if role in {"core", "support"} and intent["shape_keywords"]:
        controls.append("shape_keywords")
    if role == "hit" and intent["hit_placement"] != "unspecified":
        controls.append("hit_placement")
    if role == "residual" and intent["timing_keywords"]:
        controls.append("timing_keywords")
    return controls


def build_proposal_plan(
    prompt: str,
    effect_family: str,
    seed: int,
    *,
    procedure_specs: Iterable[dict[str, Any]] = (),
    target_unity_version: str = "2022.3.16f1c1",
    target_render_pipeline: str = "URP 14.0.9",
) -> dict[str, Any]:
    if seed < 0:
        raise ValueError("seed must be non-negative")
    intent = parse_prompt_intent(prompt, effect_family)
    matched_procedures = retrieve_procedures(procedure_specs, effect_family=effect_family, style_family=intent["style_family"])
    procedure_context = build_procedure_context(
        matched_procedures,
        effect_family=effect_family,
        style_family=intent["style_family"],
        target_unity_version=target_unity_version,
        target_render_pipeline=target_render_pipeline,
    )
    layers = []
    for role in ("core", "support", "hit", "residual"):
        contract = SHADER_CONTRACTS[role]
        renderer_modes = RENDERER_MODES[effect_family][role]
        procedure_steps = steps_for_role(matched_procedures, role)
        required_all = set(contract["required_all"])
        required_tag_groups = [list(TEXTURE_TAGS[role])]
        procedure_step_ids = []
        for procedure, step in procedure_steps:
            required_all.update(step["required_shader_features"])
            if step["required_texture_tags"]:
                required_tag_groups.append(list(step["required_texture_tags"]))
            procedure_step_ids.append(f"{procedure['procedure_id']}:{step['step_id']}")
        layers.append({
            "layer_role": role,
            "purpose": LAYER_PURPOSES[effect_family][role],
            "renderer_modes": renderer_modes,
            "topology_candidates": TOPOLOGIES[effect_family][role],
        "shader_contract": {
                "required_all": sorted(required_all),
                "required_any": [list(group) for group in contract["required_any"]],
                "forbidden": ["radial_mask", "spherical_distortion"] if effect_family in {"slash", "lightning"} and role in {"core", "support"} else [],
                "requires_vertex_stream_contract": "Mesh" in renderer_modes or "Trail" in renderer_modes,
                "forbid_unverified_fallback": True,
            },
            "texture_contract": {
                "required_any": required_tag_groups,
                "forbidden_tags": ["analysis.error", "alpha.opaque"] if role != "support" else ["analysis.error"],
            },
            "prompt_controls": _prompt_controls(intent, role),
            "procedure_step_ids": procedure_step_ids,
        })
    identity = json.dumps({"prompt": prompt, "effect_family": effect_family, "seed": seed, "intent": intent, "procedure_context": procedure_context, "layers": layers}, ensure_ascii=False, sort_keys=True)
    plan = {
        "schema_version": "vfx_proposal_plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": "proposal_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20],
        "prompt": prompt,
        "seed": seed,
        "intent": intent,
        "procedure_context": procedure_context,
        "layers": layers,
        "selection_policy": {
            "prompt_controls_proposal": True,
            "role_specific_shader_plan": True,
            "joint_shader_material_texture_ranking": True,
            "verified_assets_only": True,
            "no_single_template_for_all_roles": True,
            "whole_batch_absolute_quality_gate": True,
        },
        "training_eligibility": {
            "controller_sft": False,
            "positive_generation_supervision": False,
            "proposal_failure_supervision": False,
            "reason": "Plan only; requires a target-verified tutorial procedure, asset contract audit, Unity execution and absolute quality acceptance.",
        },
        "status": "planned" if procedure_context["status"] == "verified" else "blocked",
    }
    schema = json.loads((_repo_root() / "workspace/data/vfx_generation/schemas/vfx_proposal_plan.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(plan), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"proposal plan schema error at {location}: {errors[0].message}")
    return plan
