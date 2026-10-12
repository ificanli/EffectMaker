from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover - exercised only when Pillow is unavailable
    Image = None
    ImageStat = None

TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".dds", ".tif", ".tiff", ".bmp", ".exr"}

KEYWORD_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("semantic.slash", ("slash", "blade", "knife", "knifelight", "刀光", "daoguang")),
    ("semantic.trail", ("trail", "streak", "拖尾", "轨迹")),
    ("semantic.mask", ("mask", "alpha", "遮罩")),
    ("semantic.noise", ("noise", "perlin", "voronoi", "distortion", "dissolve", "噪声", "扰动", "扭曲", "niuqu")),
    ("semantic.gradient", ("gradient", "ramp", "colorbar", "渐变")),
    ("semantic.ring", ("ring", "circle", "环", "圆")),
    ("semantic.magic_circle", ("magiccircle", "magic_circle", "magic-circle", "rune", "symbol", "法阵")),
    ("semantic.spark", ("spark", "star", "flare", "glow", "flash", "火星", "光点")),
    ("semantic.fire", ("fire", "flame", "huo", "火焰")),
    ("semantic.smoke", ("smoke", "cloud", "dust", "烟", "雾")),
    ("semantic.lightning", ("lightning", "thunder", "electric", "闪电", "雷")),
)


@dataclass(frozen=True)
class TextureTagConfig:
    resource_root: Path
    assets_jsonl: Path
    output_jsonl: Path
    query: str = ""
    limit: int | None = None
    inspect_pixels: bool = True


def _matches_query(relative_path: str, query: str) -> bool:
    if not query:
        return True
    terms = [term.casefold() for term in re.split(r"\s+", query.strip()) if term]
    path = relative_path.casefold()
    return all(term in path for term in terms)


def _path_keyword_tags(relative_path: str) -> list[str]:
    value = relative_path.casefold()
    tags: list[str] = []
    for tag, keywords in KEYWORD_TAGS:
        if any(keyword.casefold() in value for keyword in keywords):
            tags.append(tag)
    return tags


def _geometry_tags(width: int | None, height: int | None) -> list[str]:
    if not width or not height:
        return []
    tags = [f"size.{width}x{height}"]
    ratio = width / height
    if ratio >= 3.0:
        tags.append("shape.horizontal_strip")
    elif ratio <= 1 / 3:
        tags.append("shape.vertical_strip")
    elif 0.85 <= ratio <= 1.18:
        tags.append("shape.square")
    else:
        tags.append("shape.rectangle")
    if max(width, height) <= 128:
        tags.append("resolution.small")
    elif max(width, height) >= 1024:
        tags.append("resolution.large")
    else:
        tags.append("resolution.medium")
    return tags


def _pixel_tags(path: Path) -> tuple[list[str], dict[str, float | int | str]]:
    if Image is None or ImageStat is None:
        return ["analysis.pillow_missing"], {"analysis_error": "Pillow is not available"}
    try:
        with Image.open(path) as image:
            image = image.convert("RGBA")
            width, height = image.size
            alpha = image.getchannel("A")
            luminance = image.convert("L")
            alpha_stat = ImageStat.Stat(alpha)
            lum_stat = ImageStat.Stat(luminance)
            alpha_mean = alpha_stat.mean[0] / 255.0
            alpha_std = alpha_stat.stddev[0] / 255.0
            lum_mean = lum_stat.mean[0] / 255.0
            lum_std = lum_stat.stddev[0] / 255.0
            alpha_hist = alpha.histogram()
            transparent_ratio = sum(alpha_hist[:16]) / (width * height)
            opaque_ratio = sum(alpha_hist[240:]) / (width * height)
            bright_hist = luminance.histogram()
            bright_ratio = sum(bright_hist[220:]) / (width * height)
            dark_ratio = sum(bright_hist[:32]) / (width * height)
            metrics: dict[str, float | int | str] = {
                "width": width,
                "height": height,
                "alpha_mean": round(alpha_mean, 4),
                "alpha_std": round(alpha_std, 4),
                "transparent_ratio": round(transparent_ratio, 4),
                "opaque_ratio": round(opaque_ratio, 4),
                "luminance_mean": round(lum_mean, 4),
                "luminance_std": round(lum_std, 4),
                "bright_ratio": round(bright_ratio, 4),
                "dark_ratio": round(dark_ratio, 4),
            }
            tags: list[str] = []
            if transparent_ratio > 0.35:
                tags.append("alpha.sparse")
            elif opaque_ratio > 0.85:
                tags.append("alpha.opaque")
            else:
                tags.append("alpha.mixed")
            if alpha_std > 0.20:
                tags.append("alpha.structured")
            if transparent_ratio > 0.20 and alpha_std > 0.12:
                tags.append("alpha.gradient")
            if alpha_std > 0.25 and transparent_ratio > 0.20:
                tags.append("alpha.cutout")
            if lum_std > 0.22:
                tags.append("luma.high_contrast")
            elif lum_std < 0.08:
                tags.append("luma.low_contrast")
            if lum_std < 0.045:
                tags.append("luma.flat")
            if bright_ratio > 0.08:
                tags.append("luma.bright_core")
            if bright_ratio > 0.18:
                tags.append("luma.overbright_risk")
            if dark_ratio > 0.55:
                tags.append("luma.dark_background")
            return tags, metrics
    except Exception as error:  # pragma: no cover - depends on local image codecs
        return ["analysis.error"], {"analysis_error": f"{type(error).__name__}: {error}"}


def _slot_and_role_tags(tags: Iterable[str]) -> list[str]:
    tag_set = set(tags)
    derived: list[str] = []
    if "semantic.slash" in tag_set or "semantic.trail" in tag_set:
        derived.extend(["slot.base_map", "role.core_shape"])
    if "semantic.trail" in tag_set:
        derived.extend(["role.residual_trail", "motion.uv_scroll_u"])
    if "semantic.mask" in tag_set or "alpha.structured" in tag_set:
        derived.extend(["slot.alpha_mask", "role.noise_control"])
    if "semantic.noise" in tag_set:
        derived.extend(["slot.dissolve_map", "slot.distortion_map", "role.noise_control", "motion.dissolve_reveal"])
    if "semantic.gradient" in tag_set or "shape.horizontal_strip" in tag_set or "shape.vertical_strip" in tag_set:
        derived.extend(["slot.ramp_map", "role.color_control"])
    if "semantic.spark" in tag_set or "semantic.flare" in tag_set:
        derived.extend(["slot.emission_map", "role.hit_accent", "role.edge_accent"])
    if "semantic.ring" in tag_set:
        derived.extend(["role.impact_ring", "motion.radial_expand"])
    if "semantic.magic_circle" in tag_set:
        derived.extend(["role.warning_area", "motion.radial_rotate"])
    if "license_unknown" in tag_set or "quality.license_unknown" in tag_set:
        derived.append("quality.license_unknown")
    return derived


def tag_texture_record(record: dict[str, Any], resource_root: Path, inspect_pixels: bool = True) -> dict[str, Any]:
    relative_path = record["relative_path"]
    tags = list(record.get("tags") or [])
    tags.extend(_path_keyword_tags(relative_path))
    tags.extend(_geometry_tags(record.get("width"), record.get("height")))
    metrics: dict[str, Any] = {}
    if inspect_pixels:
        pixel_tags, metrics = _pixel_tags(resource_root / relative_path)
        tags.extend(pixel_tags)
    if record.get("license_status", "unknown") == "unknown":
        tags.append("quality.license_unknown")
    tags.extend(_slot_and_role_tags(tags))
    return {
        "schema_version": "texture_tags.v1",
        "asset_id": record["asset_id"],
        "relative_path": relative_path,
        "extension": record.get("extension"),
        "width": record.get("width"),
        "height": record.get("height"),
        "license_status": record.get("license_status", "unknown"),
        "thumbnail_status": record.get("thumbnail_status"),
        "tags": sorted(set(tag for tag in tags if tag)),
        "metrics": metrics,
    }


def iter_asset_records(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def build_texture_tags(config: TextureTagConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in iter_asset_records(config.assets_jsonl):
        if record.get("asset_type") != "texture":
            continue
        if record.get("extension", "").casefold() not in TEXTURE_EXTENSIONS:
            continue
        if not _matches_query(record["relative_path"], config.query):
            continue
        records.append(tag_texture_record(record, config.resource_root, config.inspect_pixels))
        if config.limit is not None and len(records) >= config.limit:
            break
    config.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with config.output_jsonl.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fine-grained tags for indexed VFX textures.")
    parser.add_argument("--resource-root", type=Path, default=Path("resource"))
    parser.add_argument("--assets-jsonl", type=Path, default=Path("workspace/data/resource_index/assets.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("workspace/data/resource_index/texture_tags.jsonl"))
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-pixels", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = build_texture_tags(
        TextureTagConfig(
            resource_root=args.resource_root,
            assets_jsonl=args.assets_jsonl,
            output_jsonl=args.output,
            query=args.query,
            limit=args.limit,
            inspect_pixels=not args.no_pixels,
        )
    )
    print(f"tagged {len(records)} textures -> {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
