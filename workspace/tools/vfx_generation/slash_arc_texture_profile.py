from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PROFILE_VERSION = "slash_arc_texture_profile.v1"
DEFAULT_SHADER = "Universal Render Pipeline/Particles/Unlit"

SLASH_TEXTURE_SLOT_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "base_map": {
        "required_tags": ("semantic.slash", "slot.base_map"),
        "preferred_tags": ("role.core_shape", "alpha.sparse", "alpha.mixed", "luma.bright_core", "luma.high_contrast", "shape.horizontal_strip"),
        "avoided_tags": ("alpha.opaque", "luma.low_contrast"),
    },
    "alpha_mask": {
        "required_tags": ("slot.alpha_mask",),
        "preferred_tags": ("alpha.structured", "alpha.gradient", "alpha.cutout", "semantic.mask", "semantic.slash"),
        "avoided_tags": ("alpha.opaque",),
    },
    "dissolve_map": {
        "required_tags": ("semantic.noise", "slot.dissolve_map"),
        "preferred_tags": ("slot.distortion_map", "role.noise_control", "motion.dissolve_reveal", "shape.square", "luma.high_contrast"),
        "avoided_tags": (),
    },
    "ramp_map": {
        "required_tags": ("slot.ramp_map",),
        "preferred_tags": ("semantic.gradient", "role.color_control", "shape.horizontal_strip", "shape.vertical_strip"),
        "avoided_tags": (),
    },
}


@dataclass(frozen=True)
class TextureSelectionConfig:
    tag_files: tuple[Path, ...]
    output: Path
    limit_per_slot: int = 8


def load_tagged_textures(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        with Path(path).open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                asset_id = record["asset_id"]
                if asset_id not in seen:
                    seen.add(asset_id)
                    records.append(record)
    return records


def _has(record: dict[str, Any], *tags: str) -> bool:
    values = set(record.get("tags") or [])
    return all(tag in values for tag in tags)


def _score(record: dict[str, Any], preferred: Iterable[str], avoided: Iterable[str] = ()) -> float:
    tags = set(record.get("tags") or [])
    metrics = record.get("metrics") or {}
    score = 0.0
    for tag in preferred:
        if tag in tags:
            score += 10.0
    for tag in avoided:
        if tag in tags:
            score -= 10.0
    score += min(float(record.get("width") or 0), 1024.0) / 1024.0
    score += min(float(record.get("height") or 0), 1024.0) / 1024.0
    score += float(metrics.get("bright_ratio") or 0.0) * 2.0
    score += float(metrics.get("luminance_std") or 0.0) * 2.0
    score += float(metrics.get("alpha_std") or 0.0) * 2.0
    return score


def _pick(records: list[dict[str, Any]], required: tuple[str, ...], preferred: tuple[str, ...], avoided: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    candidates = [record for record in records if _has(record, *required)]
    ranked = sorted(
        candidates,
        key=lambda record: (-_score(record, preferred, avoided), record["relative_path"]),
    )
    return ranked[:limit]


def build_shader_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [
        {
            "name": DEFAULT_SHADER,
            "role": "baseline_default",
            "source": "Unity built-in URP particle shader; use as the first material baseline before custom shader work.",
            "tags": ["shader.baseline", "shader.urp", "shader.unlit", "material.simple"],
        }
    ]

    nb_shader_path = Path("UnityDemo/EffectDemo/Packages/com.xuanxuan.nb.fx/NBShaders2/Shader/NBShader.shader")
    if nb_shader_path.exists():
        candidates.append(
            {
                "name": "Effects/NBShader",
                "role": "local_reference",
                "source": "Local NB FX package shader in UnityDemo/EffectDemo; compare it against the URP baseline when a custom shader baseline is needed.",
                "path": nb_shader_path.as_posix(),
                "tags": ["shader.local_reference", "shader.nbfx", "material.custom"],
            }
        )
    return candidates


def build_slash_arc_texture_profile(config: TextureSelectionConfig) -> dict[str, Any]:
    records = load_tagged_textures(config.tag_files)
    shader_candidates = build_shader_candidates()
    slot_rules = {
        slot: {
            "required_tags": list(rule["required_tags"]),
            "preferred_tags": list(rule["preferred_tags"]),
            "avoided_tags": list(rule["avoided_tags"]),
        }
        for slot, rule in SLASH_TEXTURE_SLOT_RULES.items()
    }
    slots = {
        slot_name: _pick(
            records,
            rule["required_tags"],
            rule["preferred_tags"],
            rule["avoided_tags"],
            config.limit_per_slot,
        )
        for slot_name, rule in SLASH_TEXTURE_SLOT_RULES.items()
    }
    profile = {
        "schema_version": PROFILE_VERSION,
        "shader": {
            **shader_candidates[0],
        },
        "shader_candidates": shader_candidates,
        "material_selection": {
            "shader_name": DEFAULT_SHADER,
            "shader_candidates": shader_candidates,
            "slot_rules": slot_rules,
            "tag_sources": [path.as_posix() for path in config.tag_files],
            "selection_basis": [
                "shader choice comes first and is recorded separately from texture slots",
                "texture tags determine slot compatibility before material training",
                "slot rules use explicit required, preferred, and avoided tag families",
            ],
        },
        "slots": {
            slot: [
                {
                    "asset_id": record["asset_id"],
                    "relative_path": record["relative_path"],
                    "width": record.get("width"),
                    "height": record.get("height"),
                    "tags": record.get("tags", []),
                    "license_status": record.get("license_status", "unknown"),
                    "thumbnail_status": record.get("thumbnail_status"),
                }
                for record in picks
            ]
            for slot, picks in slots.items()
        },
    }
    config.output.parent.mkdir(parents=True, exist_ok=True)
    config.output.write_text(json.dumps(profile, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select tagged textures for SlashArc material slots.")
    parser.add_argument("--tags", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=Path("workspace/data/vfx_generation/reports/slash_arc_texture_profile.json"))
    parser.add_argument("--limit-per-slot", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = build_slash_arc_texture_profile(
        TextureSelectionConfig(
            tag_files=tuple(args.tags),
            output=args.output,
            limit_per_slot=args.limit_per_slot,
        )
    )
    counts = {slot: len(records) for slot, records in profile["slots"].items()}
    print(json.dumps({"output": args.output.as_posix(), "counts": counts}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
