"""Describe VFX family operators without confusing executors with generators."""

from __future__ import annotations

from typing import Any


GENERATOR_FAMILIES: dict[str, dict[str, Any]] = {
    "slash": {
        "implementation_status": "legacy_fixed_adapter",
        "generator_module": "workspace.tools.vfx_generation.slash_family_generator",
        "generator_family": "mesh_blade_multilayer",
        "technical_executor_ready": True,
        "proposal_planner_ready": False,
        "production_generation_eligible": False,
        "migration_blockers": ["fixed_topology", "fixed_asset_bundle", "prompt_metadata_only", "shader_material_texture_contract_not_enforced", "absolute_quality_gate_missing"],
        "inputs": ["attack_direction", "outer_inner_hierarchy", "contact_point", "residual_flow", "timing_profile"],
        "outputs": ["outer_blade", "inner_support", "contact_hit", "direction_trail", "prefab_graph"],
        "applies_to": ["melee_slash", "sword_trail", "arc_hit"],
        "failure_modes": ["equal_layer_weight", "misaligned_trail", "misplaced_hit", "premature_residual", "unclear_attack_direction"],
    },
    "fire": {
        "implementation_status": "planned_adapter",
        "generator_module": None,
        "generator_family": "volume_flow_particles",
        "technical_executor_ready": False,
        "proposal_planner_ready": False,
        "production_generation_eligible": False,
        "migration_blockers": ["family_operator_missing", "shader_material_texture_contract_not_enforced", "absolute_quality_gate_missing"],
        "inputs": ["emission_shape", "buoyancy", "noise_flow", "temperature_gradient", "smoke_ratio"],
        "outputs": ["core_flame", "ember_particles", "smoke_residual", "material_trajectory"],
        "applies_to": ["flame_burst", "burning_ground", "torch", "explosion_fire"],
        "failure_modes": ["flat_billboard", "no_heat_gradient", "looping_without_breath", "smoke_overpowers_core"],
    },
    "lightning": {
        "implementation_status": "legacy_fixed_adapter",
        "generator_module": "workspace.tools.vfx_generation.lightning_family_generator",
        "generator_family": "layered_bolt_billboards",
        "technical_executor_ready": True,
        "proposal_planner_ready": False,
        "production_generation_eligible": False,
        "migration_blockers": ["fixed_topology", "fixed_asset_bundle", "prompt_metadata_only", "shader_material_texture_contract_not_enforced", "absolute_quality_gate_missing"],
        "inputs": ["main_bolt_scale", "branch_rotation", "impact_position", "residual_speed", "pulse_timing"],
        "outputs": ["main_bolt", "branch_support", "impact_flash", "residual_spark", "prefab_graph"],
        "applies_to": ["bolt", "chain_lightning", "electric_hit"],
        "failure_modes": ["uniform_zigzag", "missing_target_anchor", "slow_pulse", "branch_noise_hides_main_bolt"],
    },
    "shield": {
        "implementation_status": "planned_adapter",
        "generator_module": None,
        "generator_family": "surface_ring_impact",
        "technical_executor_ready": False,
        "proposal_planner_ready": False,
        "production_generation_eligible": False,
        "migration_blockers": ["family_operator_missing", "shader_material_texture_contract_not_enforced", "absolute_quality_gate_missing"],
        "inputs": ["surface_shape", "coverage", "rim_width", "impact_point", "ripple_speed", "thickness"],
        "outputs": ["shield_surface", "rim", "impact_ripple", "contact_sparks"],
        "applies_to": ["barrier", "defense_hit", "area_protection"],
        "failure_modes": ["open_silhouette", "no_surface_depth", "impact_not_localized", "rim_dominates_surface"],
    },
    "smoke": {
        "implementation_status": "planned_adapter",
        "generator_module": None,
        "generator_family": "soft_volume_particles",
        "technical_executor_ready": False,
        "proposal_planner_ready": False,
        "production_generation_eligible": False,
        "migration_blockers": ["family_operator_missing", "shader_material_texture_contract_not_enforced", "absolute_quality_gate_missing"],
        "inputs": ["source_volume", "drift", "dissipation", "density", "turbulence"],
        "outputs": ["smoke_volume", "wisps", "dissolve_trajectory"],
        "applies_to": ["trail_smoke", "impact_dust", "fog_residual"],
        "failure_modes": ["hard_edges", "uniform_noise", "no_dissipation", "opaque_screen_fill"],
    },
    "explosion": {
        "implementation_status": "legacy_fixed_adapter",
        "generator_module": "workspace.tools.vfx_generation.explosion_family_generator",
        "generator_family": "radial_impact_fragments",
        "technical_executor_ready": True,
        "proposal_planner_ready": False,
        "production_generation_eligible": False,
        "migration_blockers": ["fixed_topology", "fixed_asset_bundle", "prompt_metadata_only", "shader_material_texture_contract_not_enforced", "absolute_quality_gate_missing"],
        "inputs": ["origin", "peak_time", "shockwave_radius", "fragment_count", "flash_intensity", "residual"],
        "outputs": ["core_flash", "shockwave", "fragments", "fire_or_smoke_residual"],
        "applies_to": ["impact", "detonation", "area_hit"],
        "failure_modes": ["no_peak", "shockwave_without_origin", "fragment_uniformity", "residual_precedes_impact"],
    },
}


def get_generator_family(name: str) -> dict[str, Any]:
    try:
        return GENERATOR_FAMILIES[name]
    except KeyError as error:
        raise ValueError(f"unknown generator family: {name}") from error


def require_production_ready(name: str) -> dict[str, Any]:
    entry = get_generator_family(name)
    if not entry["production_generation_eligible"]:
        blockers = ", ".join(entry["migration_blockers"])
        raise ValueError(f"generator family is not production-ready: {name}; blockers: {blockers}")
    return entry


def generator_catalog() -> dict[str, Any]:
    return {
        "schema_version": "vfx_generator_registry.v2",
        "family_count": len(GENERATOR_FAMILIES),
        "proposal_plan_module": "workspace.tools.vfx_generation.proposal_plan",
        "shader_material_contract_module": "workspace.tools.vfx_generation.shader_material_contract",
        "technical_adapter_families": sorted(
            name for name, value in GENERATOR_FAMILIES.items() if value["technical_executor_ready"]
        ),
        "production_ready_families": sorted(
            name for name, value in GENERATOR_FAMILIES.items() if value["production_generation_eligible"]
        ),
        "planned_families": sorted(
            name for name, value in GENERATOR_FAMILIES.items() if value["implementation_status"] == "planned_adapter"
        ),
        "migration_required_families": sorted(
            name for name, value in GENERATOR_FAMILIES.items() if value["technical_executor_ready"] and not value["production_generation_eligible"]
        ),
        "families": GENERATOR_FAMILIES,
    }
