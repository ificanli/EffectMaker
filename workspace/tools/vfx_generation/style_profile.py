"""Parse VFX prompt style words into a trainable target style profile."""

from __future__ import annotations

import argparse
import json
from typing import Any, Iterable


STYLE_AXES = (
    "realism",
    "graphic_stylization",
    "texture_detail",
    "color_saturation",
    "edge_definition",
    "glow_exaggeration",
    "motion_exaggeration",
)

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "realistic": ("realistic", "photoreal", "photorealistic", "写实", "拟真"),
    "stylized": ("stylized", "stylised", "风格化", "游戏化", "low poly"),
    "cartoon": ("cartoon", "卡通", "q版"),
    "anime": ("anime", "anime-style", "二次元", "日系"),
    "fantasy_painterly": ("painterly", "painted", "水彩", "绘画", "手绘"),
    "ui_graphic": ("ui graphic", "ui-style", "界面风", "图标风", "图形化"),
}

FAMILY_AXES: dict[str, dict[str, float]] = {
    "realistic": {"realism": 0.9, "graphic_stylization": 0.15, "texture_detail": 0.85, "color_saturation": 0.5, "edge_definition": 0.35, "glow_exaggeration": 0.35, "motion_exaggeration": 0.4},
    "stylized": {"realism": 0.35, "graphic_stylization": 0.8, "texture_detail": 0.45, "color_saturation": 0.75, "edge_definition": 0.7, "glow_exaggeration": 0.75, "motion_exaggeration": 0.7},
    "cartoon": {"realism": 0.1, "graphic_stylization": 0.95, "texture_detail": 0.25, "color_saturation": 0.85, "edge_definition": 0.85, "glow_exaggeration": 0.7, "motion_exaggeration": 0.85},
    "anime": {"realism": 0.2, "graphic_stylization": 0.9, "texture_detail": 0.5, "color_saturation": 0.8, "edge_definition": 0.8, "glow_exaggeration": 0.85, "motion_exaggeration": 0.8},
    "fantasy_painterly": {"realism": 0.35, "graphic_stylization": 0.8, "texture_detail": 0.7, "color_saturation": 0.65, "edge_definition": 0.45, "glow_exaggeration": 0.65, "motion_exaggeration": 0.6},
    "ui_graphic": {"realism": 0.05, "graphic_stylization": 0.95, "texture_detail": 0.2, "color_saturation": 0.8, "edge_definition": 0.9, "glow_exaggeration": 0.6, "motion_exaggeration": 0.45},
}


def _average_axes(families: Iterable[str]) -> dict[str, float | None]:
    selected = [FAMILY_AXES[family] for family in families if family in FAMILY_AXES]
    if not selected:
        return {axis: None for axis in STYLE_AXES}
    return {axis: round(sum(values[axis] for values in selected) / len(selected), 3) for axis in STYLE_AXES}


def parse_style_profile(prompt: str, *, scene_context: Iterable[str] = ()) -> dict[str, Any]:
    normalized = prompt.casefold()
    matched: list[tuple[str, str]] = []
    for family, keywords in FAMILY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.casefold() in normalized:
                matched.append((family, keyword))
                break
    families = [family for family, _keyword in matched]
    if not families:
        family = "unknown"
        confidence = 0.0
    elif len(families) == 1:
        family = families[0]
        confidence = 0.9
    else:
        family = "mixed"
        confidence = 0.65
    return {
        "schema_version": "vfx_style_profile.v1",
        "family": family,
        "keywords": [keyword for _family, keyword in matched],
        "axes": _average_axes(families),
        "scene_context": sorted(set(str(value) for value in scene_context)),
        "source": "prompt",
        "confidence": confidence,
        "notes": None if families else "No recognized style keyword; require explicit style annotation.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse VFX prompt style keywords into a style profile.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--scene-context", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    profile = parse_style_profile(args.prompt, scene_context=args.scene_context)
    payload = json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
