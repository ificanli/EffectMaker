"""Family-aware candidate scoring with explicit evidence provenance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable


SCORE_SCHEMA_VERSION = "candidate_score.v1"

FAMILY_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "slash": (
        "sharpness",
        "attack_direction",
        "width_profile",
        "tip_quality",
        "residual_flow",
        "silhouette_readability",
    ),
    "fire": (
        "turbulence",
        "root_brightness",
        "edge_breakup",
        "heat_layering",
        "afterburn_quality",
    ),
    "lightning": (
        "branch_readability",
        "instant_peak",
        "path_energy",
        "randomness_control",
        "contact_clarity",
    ),
    "shield": (
        "wrap_volume",
        "impact_response",
        "surface_readability",
        "transparent_sorting",
        "ground_attachment",
    ),
    "magic_circle": (
        "symbol_density",
        "ground_attachment",
        "reveal_timing",
        "layer_clarity",
        "radial_readability",
    ),
    "smoke": (
        "volume_softness",
        "rise_spread",
        "dissipation",
        "depth_layering",
    ),
    "explosion": (
        "impact_peak",
        "shockwave_readability",
        "fragment_spread",
        "residual_smoke",
        "layer_separation",
    ),
    "water": (
        "flow_direction",
        "foam_edge",
        "gravity_return",
        "transparency_layering",
    ),
}

COMMON_RENDER_DIMENSIONS = (
    "readability",
    "timing",
    "material",
    "camera_readability",
    "performance",
    "layer_separation",
    "spatial_anchor",
)

FamilyScorer = Callable[[Mapping[str, Any], list[str]], dict[str, float | None]]

_TIP_SCORES = {
    "sharp": 100.0,
    "needle": 96.0,
    "forked": 78.0,
    "torn": 72.0,
    "rounded": 38.0,
}
_DIRECTION_SCORES = {
    "left_to_right": 92.0,
    "right_to_left": 92.0,
    "diagonal": 96.0,
    "front_to_back": 72.0,
    "back_to_front": 72.0,
    "radial": 55.0,
}
_TOPOLOGY_SCORES = {
    "single_sweep": 96.0,
    "hooked_slash": 90.0,
    "broken_sweep": 76.0,
    "double_echo": 70.0,
    "crescent": 52.0,
}
_WIDTH_SCORES = {
    "tapered": 96.0,
    "center_heavy": 90.0,
    "root_heavy": 82.0,
    "tip_heavy": 74.0,
    "broken": 66.0,
}
_FLOW_SCORES = {
    "along_attack": 96.0,
    "fragmented": 86.0,
    "outward": 78.0,
    "opposite_attack": 62.0,
    "none": 48.0,
}
_FLAME_EDGE_SCORES = {
    "none": 25.0,
    "soft_residue": 78.0,
    "thin_wisp": 72.0,
    "dark_plume": 66.0,
}
_EMBER_SCORES = {
    "none": 30.0,
    "short_sparks": 70.0,
    "rising_sparks": 92.0,
    "burst_sparks": 84.0,
    "residual_sparks": 78.0,
}
_REVEAL_SCORES = {
    "instant": 55.0,
    "center_out": 94.0,
    "outside_in": 84.0,
    "clockwise": 88.0,
    "layered": 92.0,
    "pulse": 76.0,
}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _average(values: list[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    if not available:
        return None
    return round(sum(available) / len(available), 2)


def _band_score(value: float | None, low: float, ideal_low: float, ideal_high: float, high: float) -> float | None:
    if value is None:
        return None
    if value <= low or value >= high:
        return 0.0
    if ideal_low <= value <= ideal_high:
        return 100.0
    if value < ideal_low:
        return _clamp((value - low) / (ideal_low - low) * 100.0)
    return _clamp((high - value) / (high - ideal_high) * 100.0)


def _enum_score(value: Any, scores: Mapping[str, float]) -> float | None:
    if value is None:
        return None
    score = scores.get(str(value))
    return None if score is None else float(score)


def _adapter_metrics(spec: Mapping[str, Any]) -> list[str]:
    adapter = spec.get("adapter")
    if not isinstance(adapter, Mapping):
        return list(FAMILY_DIMENSIONS.get(str(spec.get("effect_family", "")), ()))
    metrics = adapter.get("evaluation_metrics")
    if not isinstance(metrics, list):
        metrics = adapter.get("specialized_metrics")
    if isinstance(metrics, list):
        return [str(metric) for metric in metrics]
    return list(FAMILY_DIMENSIONS.get(str(spec.get("effect_family", "")), ()))


def _slash_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    topology = adapter.get("topology")
    shape = adapter.get("shape")
    topology = topology if isinstance(topology, Mapping) else {}
    shape = shape if isinstance(shape, Mapping) else {}
    tip_score = _enum_score(shape.get("tip_shape"), _TIP_SCORES)
    topology_score = _enum_score(topology.get("arc_topology"), _TOPOLOGY_SCORES)
    direction_score = _enum_score(topology.get("attack_direction"), _DIRECTION_SCORES)
    width_score = _enum_score(shape.get("width_profile"), _WIDTH_SCORES)
    flow_score = _enum_score(shape.get("residual_flow"), _FLOW_SCORES)
    asymmetry = _number(topology.get("asymmetry"))
    edge_breakup = _number(shape.get("edge_breakup"))
    control_points = _number(topology.get("control_point_count"))
    silhouette = _average(
        [
            topology_score,
            _band_score(asymmetry, 0.0, 0.25, 0.85, 1.0),
            _band_score(edge_breakup, 0.0, 0.04, 0.42, 1.0),
            _band_score(control_points, 2.0, 4.0, 8.0, 13.0),
        ]
    )
    values = {
        "sharpness": _average([tip_score, edge_breakup * 100.0 if edge_breakup is not None else None]),
        "attack_direction": direction_score,
        "width_profile": width_score,
        "tip_quality": tip_score,
        "residual_flow": flow_score,
        "silhouette_readability": silhouette,
    }
    return {dimension: values.get(dimension) for dimension in dimensions}


def _fire_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    topology = adapter.get("topology")
    behavior = adapter.get("behavior")
    topology = topology if isinstance(topology, Mapping) else {}
    behavior = behavior if isinstance(behavior, Mapping) else {}
    turbulence = _number(behavior.get("turbulence"))
    root_brightness = _number(behavior.get("root_brightness"))
    edge_breakup = _number(topology.get("edge_breakup"))
    values = {
        "turbulence": turbulence * 100.0 if turbulence is not None else None,
        "root_brightness": root_brightness * 100.0 if root_brightness is not None else None,
        "edge_breakup": edge_breakup * 100.0 if edge_breakup is not None else None,
        "heat_layering": _average(
            [
                _enum_score(behavior.get("ember_behavior"), _EMBER_SCORES),
                _enum_score(behavior.get("smoke_afterburn"), _FLAME_EDGE_SCORES),
            ]
        ),
        "afterburn_quality": _enum_score(behavior.get("smoke_afterburn"), _FLAME_EDGE_SCORES),
    }
    return {dimension: values.get(dimension) for dimension in dimensions}


def _lightning_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    path = adapter.get("path")
    flash = adapter.get("flash")
    path = path if isinstance(path, Mapping) else {}
    flash = flash if isinstance(flash, Mapping) else {}
    branch_count = _number(path.get("branch_count"))
    main_path_bias = _number(path.get("main_path_bias"))
    jitter = _number(path.get("jitter_strength"))
    contact_points = _number(path.get("contact_points"))
    contact_strength = _number(flash.get("contact_arc_strength"))
    values = {
        "branch_readability": _average(
            [
                main_path_bias * 100.0 if main_path_bias is not None else None,
                _band_score(branch_count, 0.0, 1.0, 12.0, 65.0),
            ]
        ),
        "instant_peak": (_number(flash.get("instant_peak")) or 0.0) * 100.0 if flash.get("instant_peak") is not None else None,
        "path_energy": _average(
            [
                jitter * 100.0 if jitter is not None else None,
                main_path_bias * 100.0 if main_path_bias is not None else None,
            ]
        ),
        "randomness_control": _band_score(jitter, 0.0, 0.25, 0.82, 1.0),
        "contact_clarity": _average(
            [
                _band_score(contact_points, 0.0, 1.0, 4.0, 17.0),
                contact_strength * 100.0 if contact_strength is not None else None,
            ]
        ),
    }
    return {dimension: values.get(dimension) for dimension in dimensions}


def _shield_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    volume = adapter.get("volume")
    surface = adapter.get("surface")
    impact = adapter.get("impact_response")
    volume = volume if isinstance(volume, Mapping) else {}
    surface = surface if isinstance(surface, Mapping) else {}
    impact = impact if isinstance(impact, Mapping) else {}
    wrap_ratio = _number(volume.get("wrap_ratio"))
    thickness = _number(volume.get("surface_thickness"))
    pattern_density = _number(surface.get("pattern_density"))
    rim_strength = _number(surface.get("rim_strength"))
    ripple_count = _number(impact.get("ripple_count"))
    impact_decay = _number(impact.get("impact_decay"))
    values = {
        "wrap_volume": wrap_ratio * 100.0 if wrap_ratio is not None else None,
        "impact_response": _average(
            [
                _band_score(ripple_count, 0.0, 1.0, 5.0, 17.0),
                _band_score(impact_decay, 0.0, 0.12, 0.72, 2.0),
            ]
        ),
        "surface_readability": _average(
            [
                pattern_density * 100.0 if pattern_density is not None else None,
                _band_score(thickness, 0.0, 0.02, 0.18, 1.0),
            ]
        ),
        "transparent_sorting": _enum_score(surface.get("transparency_mode"), {
            "rim_only": 94.0,
            "soft_additive": 84.0,
            "transparent_shell": 72.0,
            "opaque_energy": 42.0,
        }),
        "ground_attachment": _enum_score(volume.get("ground_intersection"), {
            "ground_ring": 94.0,
            "soft_clip": 84.0,
            "hard_clip": 70.0,
            "none": 42.0,
        }),
    }
    if rim_strength is not None and values["surface_readability"] is not None:
        values["surface_readability"] = _average([values["surface_readability"], _band_score(rim_strength, 0.0, 0.2, 2.2, 5.0)])
    return {dimension: values.get(dimension) for dimension in dimensions}


def _magic_circle_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    layout = adapter.get("layout")
    reveal = adapter.get("reveal")
    layout = layout if isinstance(layout, Mapping) else {}
    reveal = reveal if isinstance(reveal, Mapping) else {}
    ring_count = _number(layout.get("ring_count"))
    rune_density = _number(layout.get("rune_density"))
    radial_segments = _number(layout.get("radial_segments"))
    rotation_layers = _number(reveal.get("rotation_layers"))
    values = {
        "symbol_density": _average([rune_density * 100.0 if rune_density is not None else None, _band_score(radial_segments, 0.0, 8.0, 40.0, 65.0)]),
        "ground_attachment": _enum_score(layout.get("ground_attachment"), {
            "flat_ground": 96.0,
            "projected": 92.0,
            "slight_float": 66.0,
            "vertical_portal": 48.0,
        }),
        "reveal_timing": _enum_score(reveal.get("reveal_timing"), _REVEAL_SCORES),
        "layer_clarity": _average([_band_score(ring_count, 0.0, 1.0, 6.0, 13.0), _band_score(rotation_layers, 0.0, 1.0, 4.0, 9.0)]),
        "radial_readability": _enum_score(layout.get("symmetry"), {
            "broken_radial": 94.0,
            "asymmetric": 90.0,
            "quadrant": 78.0,
            "radial": 68.0,
        }),
    }
    return {dimension: values.get(dimension) for dimension in dimensions}


def _smoke_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    volume = adapter.get("volume")
    behavior = adapter.get("behavior")
    volume = volume if isinstance(volume, Mapping) else {}
    behavior = behavior if isinstance(behavior, Mapping) else {}
    softness = _number(volume.get("softness", behavior.get("softness")))
    rise_speed = _number(behavior.get("rise_speed", behavior.get("upward_flow_speed")))
    dissipation = _number(behavior.get("dissipation", behavior.get("fade_rate")))
    layer_count = _number(volume.get("layer_count", behavior.get("depth_layers")))
    values = {
        "volume_softness": softness * 100.0 if softness is not None else None,
        "rise_spread": _band_score(rise_speed, 0.0, 0.1, 3.0, 12.0),
        "dissipation": _band_score(dissipation, 0.0, 0.05, 0.8, 3.0),
        "depth_layering": _band_score(layer_count, 0.0, 2.0, 6.0, 17.0),
    }
    return {dimension: values.get(dimension) for dimension in dimensions}


def _explosion_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    impact = adapter.get("impact")
    shockwave = adapter.get("shockwave")
    fragments = adapter.get("fragments")
    residual = adapter.get("residual")
    impact = impact if isinstance(impact, Mapping) else {}
    shockwave = shockwave if isinstance(shockwave, Mapping) else {}
    fragments = fragments if isinstance(fragments, Mapping) else {}
    residual = residual if isinstance(residual, Mapping) else {}
    impact_peak = _number(impact.get("peak"))
    if impact_peak is None:
        impact_brightness = _number(impact.get("brightness"))
        impact_peak = impact_brightness * 100.0 if impact_brightness is not None else None
    elif 0.0 <= impact_peak <= 1.0:
        impact_peak *= 100.0
    values = {
        "impact_peak": impact_peak,
        "shockwave_readability": _average(
            [
                _band_score(_number(shockwave.get("radius")), 0.0, 0.2, 4.0, 20.0),
                _band_score(_number(shockwave.get("thickness")), 0.0, 0.02, 0.25, 1.0),
            ]
        ),
        "fragment_spread": _average(
            [
                _band_score(_number(fragments.get("count")), 0.0, 2.0, 24.0, 129.0),
                _band_score(_number(fragments.get("spread")), 0.0, 0.1, 0.8, 3.0),
            ]
        ),
        "residual_smoke": _enum_score(residual.get("smoke"), {
            "none": 30.0,
            "thin": 72.0,
            "soft": 90.0,
            "heavy": 64.0,
        }),
        "layer_separation": _band_score(_number(adapter.get("layer_count")), 0.0, 2.0, 5.0, 13.0),
    }
    return {dimension: values.get(dimension) for dimension in dimensions}


def _water_scores(adapter: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    flow = adapter.get("flow")
    surface = adapter.get("surface")
    foam = adapter.get("foam")
    flow = flow if isinstance(flow, Mapping) else {}
    surface = surface if isinstance(surface, Mapping) else {}
    foam = foam if isinstance(foam, Mapping) else {}
    direction = _number(flow.get("directionality", flow.get("direction_strength")))
    return_values = _number(flow.get("gravity_return", flow.get("return_strength")))
    transparency = _number(surface.get("transparency_layering", surface.get("layer_count")))
    values = {
        "flow_direction": direction * 100.0 if direction is not None else None,
        "foam_edge": _number(foam.get("edge_strength")) * 100.0 if _number(foam.get("edge_strength")) is not None else None,
        "gravity_return": return_values * 100.0 if return_values is not None else None,
        "transparency_layering": _band_score(transparency, 0.0, 1.0, 4.0, 13.0),
    }
    return {dimension: values.get(dimension) for dimension in dimensions}


FAMILY_SCORERS: dict[str, FamilyScorer] = {
    "slash": _slash_scores,
    "fire": _fire_scores,
    "lightning": _lightning_scores,
    "shield": _shield_scores,
    "magic_circle": _magic_circle_scores,
    "smoke": _smoke_scores,
    "explosion": _explosion_scores,
    "water": _water_scores,
}


def register_family_scorer(family: str, scorer: FamilyScorer, dimensions: tuple[str, ...] = ()) -> None:
    """Register a family scorer without changing the generic evaluation contract."""

    family_name = str(family).strip()
    if not family_name:
        raise ValueError("family must be non-empty")
    FAMILY_SCORERS[family_name] = scorer
    if dimensions:
        FAMILY_DIMENSIONS[family_name] = tuple(dimensions)


def _specialized_scores(spec: Mapping[str, Any], dimensions: list[str]) -> dict[str, float | None]:
    adapter = spec.get("adapter")
    adapter = adapter if isinstance(adapter, Mapping) else {}
    family = str(spec.get("effect_family", ""))
    scorer = FAMILY_SCORERS.get(family)
    if scorer is None:
        return {dimension: None for dimension in dimensions}
    return scorer(adapter, dimensions)


def score_render_metrics(
    metrics: Mapping[str, Any] | None,
    *,
    rendered: bool,
    render_context: Mapping[str, Any] | None = None,
) -> dict[str, float | None]:
    """Score measurable render properties without claiming aesthetic acceptance."""

    if not rendered or not isinstance(metrics, Mapping):
        return {dimension: None for dimension in COMMON_RENDER_DIMENSIONS}

    context = render_context if isinstance(render_context, Mapping) else {}
    visible = _number(metrics.get("visible_area_ratio_peak"))
    luminance = _number(metrics.get("mean_luminance_peak"))
    overexposed = _number(metrics.get("overexposed_ratio_peak"))
    frame_delta = _number(metrics.get("frame_delta_mean"))
    readability = _band_score(visible, 0.0, 0.025, 0.35, 0.85)
    timing = _band_score(frame_delta, 0.0, 0.004, 0.012, 0.08)
    material = _average(
        [
            _band_score(luminance, 0.0, 0.08, 0.72, 1.0),
            _band_score(overexposed, -0.01, 0.0, 0.08, 0.98),
        ]
    )

    context_matches = [context.get(key) for key in ("scene_match", "camera_match", "resolution_match")]
    camera_readability = None
    if any(value is not None for value in context_matches):
        camera_readability = 100.0 if all(value is True for value in context_matches if value is not None) else 0.0

    performance = None
    particle_peak = _number(metrics.get("particle_count_peak"))
    draw_calls = _number(metrics.get("draw_call_count"))
    particle_budget = _number(context.get("particle_budget"))
    draw_call_budget = _number(context.get("draw_call_budget"))
    performance_values: list[float | None] = []
    if particle_budget is not None and particle_peak is not None:
        performance_values.append(_clamp((1.0 - particle_peak / particle_budget) * 100.0))
    if draw_call_budget is not None and draw_calls is not None:
        performance_values.append(_clamp((1.0 - draw_calls / draw_call_budget) * 100.0))
    if performance_values:
        performance = _average(performance_values)

    spatial_anchor = None
    if context.get("spatial_anchor_match") is not None:
        spatial_anchor = 100.0 if context.get("spatial_anchor_match") is True else 0.0

    return {
        "readability": readability,
        "timing": timing,
        "material": material,
        "camera_readability": camera_readability,
        "performance": performance,
        "layer_separation": None,
        "spatial_anchor": spatial_anchor,
    }


def score_candidate(
    spec: Mapping[str, Any],
    *,
    render_metrics: Mapping[str, Any] | None = None,
    rendered: bool = False,
    render_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return render evidence scores and spec-only family priors separately."""

    family = str(spec.get("effect_family", "unknown"))
    dimensions = _adapter_metrics(spec)
    specialized = _specialized_scores(spec, dimensions)
    common = score_render_metrics(render_metrics, rendered=rendered, render_context=render_context)
    spec_prior = _average(list(specialized.values()))
    render_score = _average(list(common.values()))
    overall_score = None
    if render_score is not None and spec_prior is not None:
        overall_score = round(render_score * 0.65 + spec_prior * 0.35, 2)
    elif render_score is not None:
        overall_score = render_score

    return {
        "schema_version": SCORE_SCHEMA_VERSION,
        "effect_family": family,
        "provenance": {
            "render_scores": "render_metrics" if rendered else "not_rendered",
            "specialized_scores": "spec_parameters",
            "final_visual_acceptance": False,
        },
        "common_scores": common,
        "specialized_scores": {key: None if value is None else round(value, 2) for key, value in specialized.items()},
        "spec_prior_score": spec_prior,
        "render_score": render_score,
        "overall_score": overall_score,
        "unscored_dimensions": [
            *[key for key, value in common.items() if value is None],
            *[key for key, value in specialized.items() if value is None],
        ],
        "notes": [
            "Specialized scores are parameter priors, not image understanding.",
            "Composite screenshots cannot establish layer separation without isolated renders.",
        ],
    }
