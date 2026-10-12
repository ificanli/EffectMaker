from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workspace.tools.vfx_generation.slash_arc_texture_profile import (
    DEFAULT_SHADER,
    SLASH_TEXTURE_SLOT_RULES,
    build_shader_candidates,
)
from workspace.tools.vfx_generation.style_profile import parse_style_profile

GENERATOR_NAME = "slash_arc_generator"
GENERATOR_VERSION = "0.1.0"
PROMPT_FILE = "workspace/data/vfx_generation/prompts/slash_arc_001.md"
CURRENT_UNITY_PROJECT = "E:/Unity特效人工智能学习/UnityDemo/EffectDemo"
DEFAULT_TIME_POINTS = [0.30, 0.50, 0.60, 0.75, 0.90]
TOPOLOGIES = ["single_sweep", "hooked_slash", "crescent", "broken_sweep"]
WIDTH_PROFILES = ["root_heavy", "center_heavy", "tip_heavy", "tapered", "broken"]
TIP_SHAPES = ["sharp", "needle", "torn", "forked"]
DIRECTIONS = ["left_to_right", "right_to_left", "diagonal"]
RESIDUAL_FLOWS = ["none", "along_attack", "opposite_attack", "outward", "fragmented"]


def _material_profile() -> dict[str, Any]:
    shader_candidates = build_shader_candidates()
    return {
        "shader": shader_candidates[0],
        "shader_candidates": shader_candidates,
        "slot_rules": SLASH_TEXTURE_SLOT_RULES,
        "selection_basis": [
            "Shader is the first material decision and stays explicit in the spec.",
            "Texture slots use tagged texture families, not raw filename guesses.",
            "These material features are training inputs, not final visual validation.",
        ],
    }


@dataclass(frozen=True)
class GeneratorConfig:
    run_id: str
    count: int
    seed: int
    output_dir: Path
    prompt: str
    negative_prompt: str
    prompt_file: str = PROMPT_FILE


def _round(value: float) -> float:
    return round(value, 4)


def _candidate_id(run_id: str, index: int) -> str:
    return f"{run_id}_c{index + 1:04d}"


def _sample_width(profile: str, progress: float, rng: random.Random) -> float:
    base = math.sin(math.pi * progress)
    if profile == "root_heavy":
        value = (1.0 - progress) ** 0.55 * 0.78 + base * 0.22
    elif profile == "center_heavy":
        value = base ** 0.62
    elif profile == "tip_heavy":
        value = progress ** 0.55 * 0.70 + base * 0.30
    elif profile == "tapered":
        value = (1.0 - progress) * 0.92 + base * 0.08
    else:
        notch = 0.30 if 0.42 < progress < 0.62 else 1.0
        value = (base ** 0.7) * notch
    jitter = rng.uniform(-0.025, 0.025)
    return _round(max(0.015, min(1.0, value + jitter)))


def _width_samples(profile: str, rng: random.Random) -> list[list[float]]:
    positions = [0.0, 0.18, 0.38, 0.58, 0.78, 1.0]
    return [[p, _sample_width(profile, p, rng)] for p in positions]


def _control_points(topology: str, length: float, curvature: float, asymmetry: float, direction: str, rng: random.Random) -> list[list[float]]:
    count = rng.randint(4, 7)
    points: list[list[float]] = []
    for index in range(count):
        t = index / (count - 1)
        x = (t - 0.5) * length
        if topology == "single_sweep":
            z = curvature * math.sin(math.pi * t) * length * 0.22
        elif topology == "hooked_slash":
            z = curvature * math.sin(math.pi * t) * length * 0.18
            z += (t**2) * asymmetry * length * 0.16
        elif topology == "crescent":
            z = (curvature * 0.55 + 0.38) * math.sin(math.pi * t) * length * 0.34
        else:
            z = curvature * math.sin(math.pi * t) * length * 0.18
            if 0.40 < t < 0.68:
                z += rng.choice([-1.0, 1.0]) * asymmetry * length * 0.10
        x += rng.uniform(-0.10, 0.10) * length * (0.35 + asymmetry * 0.25)
        z += rng.uniform(-0.08, 0.08) * length
        if direction == "right_to_left":
            x *= -1.0
        elif direction == "diagonal":
            x2 = x * 0.86 - z * 0.35
            z2 = x * 0.35 + z * 0.86
            x, z = x2, z2
        points.append([_round(x), 0.0, _round(z)])
    return points


def _make_candidate(config: GeneratorConfig, index: int) -> dict[str, Any]:
    candidate_seed = config.seed + index * 9973
    rng = random.Random(candidate_seed)
    topology = TOPOLOGIES[index % len(TOPOLOGIES)]
    width_profile = WIDTH_PROFILES[(index // len(TOPOLOGIES) + index) % len(WIDTH_PROFILES)]
    direction = DIRECTIONS[(index + rng.randrange(len(DIRECTIONS))) % len(DIRECTIONS)]
    tip_shape = rng.choice(TIP_SHAPES)
    residual_flow = rng.choice(RESIDUAL_FLOWS)
    arc_length = rng.uniform(3.5, 6.5)
    arc_width = rng.uniform(0.25, 1.10)
    curvature = rng.uniform(-0.75, 0.85)
    asymmetry = rng.uniform(0.20, 0.90)
    edge_breakup = rng.uniform(0.0, 0.45)
    control_points = _control_points(topology, arc_length, curvature, asymmetry, direction, rng)
    width_samples = _width_samples(width_profile, rng)
    candidate_id = _candidate_id(config.run_id, index)
    shape = {
        "arc_length": _round(arc_length),
        "arc_width": _round(arc_width),
        "width_profile": width_profile,
        "tip_shape": tip_shape,
        "curvature": _round(curvature),
        "edge_breakup": _round(edge_breakup),
        "residual_flow": residual_flow,
        "control_points": control_points,
        "width_samples": width_samples,
    }
    adapter = {
        "name": "slash.adapter",
        "version": "0.1.0",
        "schema_ref": "schemas/adapters/slash_adapter.schema.json",
        "generator_family": "curve_mesh",
        "topology": {
            "arc_topology": topology,
            "attack_direction": direction,
            "control_point_count": len(control_points),
            "asymmetry": _round(asymmetry),
        },
        "shape": shape,
        "evaluation_metrics": ["sharpness", "attack_direction", "width_profile", "tip_quality", "silhouette_readability"],
    }
    return {
        "schema_version": "vfxspec.v1",
        "effect_family": "slash",
        "effect_type": "slash_arc",
        "prompt": config.prompt,
        "negative_prompt": config.negative_prompt,
        "target_style_profile": parse_style_profile(config.prompt, scene_context=["battle"]),
        "generation": {
            "run_id": config.run_id,
            "candidate_id": candidate_id,
            "seed": candidate_seed,
            "generator": GENERATOR_NAME,
            "generator_version": GENERATOR_VERSION,
            "parent_candidate_id": None,
        },
        "adapter": adapter,
        "material_profile": _material_profile(),
        "layers": [
            {
                "role": "core_blade",
                "status": "active",
                "topology": "curve_mesh",
                "shape_parameters": shape,
                "material_parameters": {
                    "base_color": rng.choice(["cyan_blue", "cold_white", "blue_violet", "gold_white"]),
                    "alpha_power": _round(rng.uniform(0.80, 2.20)),
                    "edge_emission": _round(rng.uniform(0.60, 2.80)),
                    "dissolve_bias": _round(rng.uniform(0.10, 0.55)),
                },
                "timing_parameters": {
                    "appear_time": _round(rng.uniform(0.22, 0.36)),
                    "peak_time": _round(rng.uniform(0.50, 0.64)),
                    "fade_time": _round(rng.uniform(0.78, 0.98)),
                },
                "constraints": ["core_blade_only", "no_support_arc", "no_hit_accent", "no_scene_anchor"],
            }
        ],
        "render_plan": {
            "unity_project": CURRENT_UNITY_PROJECT,
            "scene": "Assets/Scenes/SampleScene.unity",
            "camera": "VFXCaptureCamera",
            "resolution": "1280x720",
            "time_points_seconds": DEFAULT_TIME_POINTS,
        },
    }


def generate_candidates(config: GeneratorConfig) -> list[dict[str, Any]]:
    if config.count < 1:
        raise ValueError("count must be positive")
    return [_make_candidate(config, index) for index in range(config.count)]


def write_run(config: GeneratorConfig) -> dict[str, Path]:
    candidates = generate_candidates(config)
    candidates_dir = config.output_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    for spec in candidates:
        candidate_id = spec["generation"]["candidate_id"]
        candidate_dir = candidates_dir / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        (candidate_dir / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    topology_counts: dict[str, int] = {}
    for spec in candidates:
        topology = spec["adapter"]["topology"]["arc_topology"]
        topology_counts[topology] = topology_counts.get(topology, 0) + 1
    manifest = {
        "schema_version": "run_manifest.v1",
        "run_id": config.run_id,
        "beads_id": "vfx-2df.2",
        "prompt_file": config.prompt_file,
        "generator": GENERATOR_NAME,
        "generator_version": GENERATOR_VERSION,
        "seed": config.seed,
        "target_style_profile": parse_style_profile(config.prompt, scene_context=["battle"]),
        "candidate_count": len(candidates),
        "candidate_ids": [spec["generation"]["candidate_id"] for spec in candidates],
        "topology_counts": topology_counts,
        "render_time_points_seconds": DEFAULT_TIME_POINTS,
        "unity_project": CURRENT_UNITY_PROJECT,
        "outputs": {
            "candidates_dir": "candidates",
            "auto_eval_jsonl": "auto_eval.jsonl",
            "feedback_jsonl": "feedback.jsonl",
        },
        "status": "generated_specs_only",
    }
    config.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config.output_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"run_manifest": manifest_path, "candidates_dir": candidates_dir}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SlashArc VFXSpec candidates.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--count", type=int, default=48)
    parser.add_argument("--seed", type=int, default=20260827)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prompt", default="stylized top-down slash core arc with clear attack direction")
    parser.add_argument("--negative-prompt", default="closed ring, symmetric UI icon, rectangular billboard, reused V9 arc")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = write_run(
        GeneratorConfig(
            run_id=args.run_id,
            count=args.count,
            seed=args.seed,
            output_dir=args.out,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
        )
    )
    print(f"generated {args.count} SlashArc candidates")
    print(paths["run_manifest"].as_posix())


if __name__ == "__main__":
    main()
