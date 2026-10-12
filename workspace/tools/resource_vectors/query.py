"""Query normalization for the local VFX vector prototype."""

from __future__ import annotations

import re
from pathlib import Path

_VFX_TERMS = {
    "蓝色": "blue",
    "蓝白": "blue white",
    "紫色": "purple",
    "红色": "red",
    "橙色": "orange",
    "金色": "gold",
    "白色": "white",
    "黑色": "black",
    "闪电": "lightning",
    "雷电": "lightning",
    "刀光": "slash",
    "剑气": "slash",
    "拖尾": "trail",
    "火焰": "fire flame",
    "烟雾": "smoke",
    "冰": "ice",
    "冰晶": "ice crystal",
    "水": "water",
    "法阵": "magic circle",
    "光环": "aura ring",
    "圆环": "ring",
    "爆点": "burst spark",
    "爆炸": "explosion burst",
    "粒子": "particle",
    "噪声": "noise",
    "扰动": "distortion",
    "溶解": "dissolve mask",
    "遮罩": "mask",
    "贴图": "texture",
    "横向": "horizontal",
    "纵向": "vertical",
    "柔和": "soft",
    "尖锐": "sharp",
    "发光": "glowing",
    "亮纹": "bright streak",
}


def normalize_text_query(text: str) -> str:
    """Append deterministic English VFX terms for an English CLIP tokenizer."""
    original = text.strip()
    if not original:
        raise ValueError("text query must not be empty")
    translated: list[str] = []
    for term in sorted(_VFX_TERMS, key=len, reverse=True):
        if term in original:
            translated.extend(_VFX_TERMS[term].split())
    ascii_terms = re.findall(r"[A-Za-z0-9_-]+", original)
    tokens = list(dict.fromkeys([*ascii_terms, *translated]))
    if not tokens:
        return original
    return "VFX texture, " + " ".join(tokens)


def is_within_root(candidate: Path, root: Path) -> bool:
    resolved, resolved_root = Path(candidate).resolve(), Path(root).resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


def resolve_query_image(image: Path, resource_root: Path) -> Path:
    """Resolve an image from cwd first, then safely from the resource root."""
    image = Path(image)
    root = Path(resource_root).resolve()
    if image.is_absolute():
        candidate = image.resolve()
        if candidate.is_file():
            return candidate
        raise ValueError(f"query image not found; checked: {candidate}")

    candidate = (root / image).resolve()
    if not is_within_root(candidate, root):
        raise ValueError(f"resource-relative query image is outside resource root: {image}")
    if candidate.is_file():
        return candidate
    raise ValueError(f"query image not found; checked: {candidate}")


__all__ = ["is_within_root", "normalize_text_query", "resolve_query_image"]
