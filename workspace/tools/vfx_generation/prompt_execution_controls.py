"""Apply bounded, inspectable Prompt controls to existing particle proposals."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any

from .proposal_plan import COLOR_TERMS, parse_prompt_intent


PALETTE = {
    "blue": [0.18, 0.5, 1.0], "purple": [0.65, 0.2, 1.0],
    "cyan": [0.1, 0.9, 1.0], "red": [1.0, 0.16, 0.12],
    "orange": [1.0, 0.42, 0.08], "yellow": [1.0, 0.88, 0.12],
    "green": [0.12, 1.0, 0.28], "white": [1.0, 1.0, 1.0],
    "black": [0.02, 0.02, 0.02],
}
DURATION = re.compile(r"(?:持续|时长|duration\s*[:=]?|lasts?)\s*(\d+(?:\.\d+)?)\s*(毫秒|秒|ms|s(?:ec(?:onds?)?)?)(?![A-Za-z])", re.IGNORECASE)


def has_gradient_data(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get('mode') or value.get('color_keys') or value.get('alpha_keys'))


def execution_fingerprint(graph: dict[str, Any]) -> str:
    value = copy.deepcopy({key: graph[key] for key in ("nodes", "components", "asset_bindings")})
    for particle in value["components"].get("particle_systems") or []:
        particle.get("parameters", {}).pop("serialized_modules", None)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ordered_colors(prompt: str, colors: list[str]) -> list[str]:
    positions = []
    for color in colors:
        for term in COLOR_TERMS[color]:
            pattern = re.escape(term) if not term.isascii() else rf"\b{re.escape(term)}\b"
            for match in re.finditer(pattern, prompt, re.IGNORECASE):
                prefix = prompt[max(0, match.start() - 5):match.start()]
                if re.search(r"(?:不要|避免|去掉|非|no |not )\s*$", prefix, re.IGNORECASE):
                    continue
                positions.append((match.start(), color))
    result = []
    for _, color in sorted(positions):
        if color not in result:
            result.append(color)
    return result


def apply_prompt_controls(graph: dict[str, Any], prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    value = copy.deepcopy(graph)
    family = str(value.get("condition", {}).get("effect_family") or "")
    intent = parse_prompt_intent(prompt, family)
    particles = value["components"].get("particle_systems") or []
    roles = {node["node_id"]: node.get("role", "unclassified") for node in value["nodes"]}
    changes: list[dict[str, Any]] = []
    applied = []
    unresolved = []

    def set_parameter(particle: dict[str, Any], field: str, updated: Any, control: str) -> None:
        parameters = particle["parameters"]
        previous = parameters.get(field)
        parameters[field] = updated
        if previous != updated:
            changes.append({"component_id": particle["component_id"], "field": field, "before": previous, "after": updated, "control": control})

    colors = _ordered_colors(prompt, intent["color_keywords"])
    if colors:
        chromatic = [color for color in colors if color not in {"white", "black"}]
        for particle in particles:
            role = roles.get(particle["node_id"])
            chosen = chromatic[-1 if role in {"support", "residual"} else 0] if chromatic else colors[0]
            rgb = list(PALETTE[chosen])
            if "white" in colors and role in {"core", "hit"} and chromatic:
                rgb = [0.65 + 0.35 * channel for channel in rgb]
            color_fields = ("start_color_rgba",) if has_gradient_data(particle["parameters"].get("color_over_lifetime_gradient")) else ("start_color_rgba", "end_color_rgba")
            for field in color_fields:
                old = particle["parameters"].get(field) or [1.0, 1.0, 1.0, 1.0]
                brightness = max(old[:3])
                updated = [round(channel * brightness, 6) for channel in rgb] + [old[3]]
                set_parameter(particle, field, updated, "color")
        applied.append("color")

    direction = intent["direction"]
    if direction in {"horizontal", "vertical"}:
        planar = particles and all(p["parameters"].get("renderer_mode") == "Billboard" and not p["parameters"].get("shape_enabled") and p["parameters"].get("start_speed_max", 0) == 0 for p in particles)
        if planar:
            core = next((p for p in particles if roles.get(p["node_id"]) == "core"), particles[0])
            params = core["parameters"]
            if params.get("start_size_3d") and params.get("start_size_x_max") != params.get("start_size_y_max"):
                axis = 0.0 if params["start_size_x_max"] >= params["start_size_y_max"] else math.pi / 2.0
                baseline = params.get("start_rotation_max", 0.0) + axis
                target = 0.0 if direction == "horizontal" else math.pi / 2.0
                delta = target - baseline
                for particle in particles:
                    rotation = round(particle["parameters"].get("start_rotation_max", 0.0) + delta, 8)
                    set_parameter(particle, "start_rotation_max", rotation, "direction")
                for node in value["nodes"]:
                    if node.get("parent_node_id") != value["root_node_id"]:
                        continue
                    x, y, z = node["transform"]["local_position"]
                    node["transform"]["local_position"] = [round(x * math.cos(delta) - y * math.sin(delta), 8), round(x * math.sin(delta) + y * math.cos(delta), 8), z]
                applied.append("direction")
            else:
                unresolved.append("direction_requires_explicit_planar_major_axis")
        else:
            unresolved.append("direction_requires_spatial_or_motion_operator")
    elif direction != "unspecified":
        unresolved.append("direction:" + direction)

    duration_matches = list(DURATION.finditer(prompt))
    target_duration = None
    if duration_matches:
        values = [float(match.group(1)) / (1000.0 if match.group(2).lower() in {"ms", "毫秒"} else 1.0) for match in duration_matches]
        if len(set(values)) != 1:
            unresolved.append("ambiguous_duration")
        elif not 0.01 <= values[0] <= 8.0:
            unresolved.append("duration_outside_supported_0.01_to_8_seconds")
        elif particles and all(not p["parameters"].get("looping") and p["parameters"].get("emission_rate_over_time_max", 0) == 0 for p in particles):
            target_duration = values[0]
            baseline_end = max(p["parameters"].get("start_delay_max", 0.0) + p["parameters"].get("start_lifetime_max", 0.0) for p in particles)
            scale = target_duration / baseline_end if baseline_end > 0 else 1.0
            for particle in particles:
                for field in ("start_delay_max", "start_lifetime_max", "duration_seconds"):
                    set_parameter(particle, field, round(particle["parameters"][field] * scale, 8), "duration")
            applied.append("duration")
        else:
            unresolved.append("duration_requires_continuous_emission_operator")
    elif intent["timing_keywords"] or "持续" in prompt:
        unresolved.append("timing_uses_existing_procedure_without_explicit_duration")

    unresolved.extend("shape:" + item for item in intent["shape_keywords"])
    if intent["hit_placement"] != "unspecified":
        unresolved.append("hit_placement:" + intent["hit_placement"])
    if intent["style_family"] != "unspecified":
        unresolved.append("style_requires_visual_validation:" + intent["style_family"])

    report = {
        "schema_version": "vfx_prompt_execution_controls.v1",
        "implementation": "bounded_rule_based_executor_not_trained_planner",
        "prompt": prompt,
        "applied_controls": applied,
        "unresolved_intents": sorted(set(unresolved)),
        "target_visual_duration_seconds": target_duration,
        "field_changes": changes,
        "before_execution_sha256": execution_fingerprint(graph),
        "after_execution_sha256": execution_fingerprint(value),
        "full_prompt_understanding": False,
        "training_eligibility": {"controller_sft": False, "positive_generation_supervision": False},
    }
    return value, report
