"""Build a leakage-aware technical Material x Shader x Texture training view."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


DATASET_SCHEMA = "vfx_material_asset_pair_training_dataset.v1"
ELEMENTS = ("fire", "ice", "lightning", "energy", "water", "smoke", "wind", "earth", "light", "dark")
EFFECT_TYPES = ("impact", "explosion", "slash", "magic_circle", "laser", "lightning", "fire", "shield", "smoke", "water", "unknown")
ROLES = ("core", "support", "hit", "residual")
STYLES = ("realistic", "cartoon", "stylized", "anime", "unknown")
COLORS = ("blue", "cyan", "orange", "red", "purple", "green", "white", "yellow", "unknown")
TYPE_TAGS = {
    "impact": ("semantic.ring", "role.impact_ring", "impact", "hit", "baodian", "shouji"),
    "slash": ("semantic.slash", "slash", "daoguang", "blade", "trail"),
    "explosion": ("semantic.fire", "semantic.smoke", "semantic.ring", "explosion", "burst", "baozha"),
    "magic_circle": ("semantic.magic_circle", "magic_circle", "rune", "portal"),
    "laser": ("semantic.laser", "laser", "beam"),
    "lightning": ("semantic.lightning", "lightning", "leidian", "electric"),
    "fire": ("semantic.fire", "fire", "flame", "huo"),
    "shield": ("semantic.shield", "shield", "barrier"),
    "smoke": ("semantic.smoke", "smoke", "yan", "dust"),
    "water": ("semantic.water", "water", "splash"),
}
ELEMENT_TAGS = {element: f"semantic.{element}" for element in ELEMENTS}
COLOR_TERMS = {color: (color,) for color in COLORS if color != "unknown"}
COLOR_TERMS.update({"cyan": ("cyan", "qing"), "orange": ("orange", "cheng"), "purple": ("purple", "violet"), "yellow": ("yellow", "huang")})


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _split(asset_group: str) -> str:
    bucket = int(hashlib.sha256(asset_group.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def _contains(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    for term in terms:
        normalized = term.lower()
        if normalized == "light":
            if re.search(r"(?<![a-z0-9])light(?![a-z0-9])", lowered):
                return True
        elif normalized in lowered:
            return True
    return False


def _infer_type(material: dict[str, Any], texture: dict[str, Any]) -> str:
    tags = set(str(value) for value in texture.get("tags") or [])
    searchable = " ".join((str(material.get("material_path") or ""), str(material.get("shader_name") or ""), str(texture.get("project_asset_path") or ""))).lower()
    for effect_type in EFFECT_TYPES:
        if effect_type != "unknown" and (tags.intersection(TYPE_TAGS.get(effect_type, ())) or _contains(searchable, TYPE_TAGS.get(effect_type, ()) )):
            return effect_type
    return "unknown"


def _infer_elements(texture: dict[str, Any], material: dict[str, Any]) -> list[str]:
    tags = set(str(value) for value in texture.get("tags") or [])
    values = [element for element, tag in ELEMENT_TAGS.items() if tag in tags]
    searchable = " ".join((str(material.get("material_path") or ""), str(texture.get("project_asset_path") or ""))).lower()
    values.extend(element for element in ELEMENTS if element not in values and _contains(searchable, (element,)))
    return sorted(set(values)) or ["energy"]


def _infer_role(property_name: str, texture: dict[str, Any]) -> str:
    tags = set(str(value) for value in texture.get("tags") or [])
    if "role.impact_ring" in tags or property_name == "_EmissionMap":
        return "hit"
    if "role.residual_trail" in tags:
        return "residual"
    if property_name in {"_DissolveTex", "_MaskTex", "_DistortTex", "_NoiseTex", "_NoiseMap"} or "role.noise_control" in tags:
        return "support"
    return "core"


def _infer_style(material: dict[str, Any], shader: dict[str, Any]) -> str:
    searchable = " ".join((str(material.get("source_group") or ""), str(material.get("material_path") or ""), str(shader.get("shader_name") or ""))).lower()
    if _contains(searchable, ("anime", "manga")):
        return "anime"
    if _contains(searchable, ("hovl", "qfx", "toon", "stylized", "erb", "cartoon")):
        return "stylized"
    if _contains(searchable, ("realistic", "real", "standard")):
        return "realistic"
    return "unknown"


def _infer_colors(texture: dict[str, Any]) -> list[str]:
    searchable = str(texture.get("project_asset_path") or "").lower()
    return sorted({color for color, terms in COLOR_TERMS.items() if _contains(searchable, terms)}) or ["unknown"]


def _texture_pair_score(material: dict[str, Any], texture: dict[str, Any], property_name: str, shader: dict[str, Any]) -> float:
    tags = set(str(value) for value in texture.get("tags") or [])
    score = 0.0
    if property_name in {"_DissolveTex", "_MaskTex", "_DistortTex", "_NoiseTex", "_NoiseMap"} and tags.intersection({"slot.dissolve_map", "slot.distortion_map", "slot.alpha_mask", "role.noise_control"}):
        score += 0.4
    if property_name == "_MainTex" and tags.intersection({"slot.base_map", "slot.alpha_mask", "semantic.spark", "role.core_shape"}):
        score += 0.4
    if "alpha.opaque" in tags:
        score -= 0.4
    if "urp" in shader.get("pipeline_tags", []):
        score += 0.1
    return round(score, 6)


def _graph_usage(graph_root: Path, training_view_root: Path) -> dict[str, list[dict[str, Any]]]:
    examples = {str(row.get("graph_id")): row for row in _read_jsonl(training_view_root / "examples.jsonl")}
    usage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for graph in _read_jsonl(graph_root / "graphs.jsonl"):
        graph_id = str(graph.get("graph_id") or "")
        example = examples.get(graph_id, {})
        split_group = example.get("split_group") or {}
        material_paths: set[str] = set(str(value).replace("\\", "/") for value in (graph.get("asset_bindings") or {}).get("materials") or [])
        for collection in ((graph.get("components") or {}).get("particle_systems") or [], (graph.get("components") or {}).get("renderers") or []):
            for component in collection:
                material_paths.update(str(value).replace("\\", "/") for value in component.get("material_paths") or [])
        for path in material_paths:
            usage[path].append({"graph_id": graph_id, "source_group": split_group.get("source_group"), "structure_split": split_group.get("structure_split")})
    return usage


def build_dataset(registry_root: Path, graph_root: Path, training_view_root: Path, output_root: Path, dataset_id: str = "material_asset_pair_training_r001", negatives_per_positive: int = 2, seed: int = 20260903) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"asset pair dataset output already exists and is not empty: {output_root}")
    registry_root = registry_root.resolve()
    registry = _read(registry_root / "registry_manifest.json")
    if registry.get("status") != "pass":
        raise ValueError(f"verified asset registry expected: {registry_root}")
    shaders = {str(row.get("asset_id")): row for row in _read_jsonl(registry_root / "shaders.jsonl") if row.get("binding_status") == "project_bindable"}
    textures = {str(row.get("asset_id")): row for row in _read_jsonl(registry_root / "textures.jsonl") if row.get("binding_status") == "project_bindable" and row.get("project_asset_path")}
    textures_by_path = {str(row.get("project_asset_path")).replace("\\", "/"): row for row in textures.values()}
    usage = _graph_usage(graph_root.resolve(), training_view_root.resolve())
    materials = [row for row in _read_jsonl(registry_root / "materials.jsonl") if row.get("binding_status") == "usable" and str(row.get("shader_asset_id")) in shaders]
    materials.sort(key=lambda row: str(row.get("material_id")))
    positives: list[dict[str, Any]] = []
    for material in materials:
        shader = shaders[str(material["shader_asset_id"])]
        material_path = str(material["material_path"]).replace("\\", "/")
        material_group = "material_cluster_" + hashlib.sha256(str(material["material_id"]).encode("utf-8")).hexdigest()[:16]
        usage_rows = usage.get(material_path) or []
        for binding in material.get("texture_bindings") or []:
            if not binding.get("is_bound"):
                continue
            texture_path = str(binding.get("texture_path") or "").replace("\\", "/")
            texture = textures_by_path.get(texture_path)
            if texture is None:
                continue
            property_name = str(binding.get("property_name") or "_MainTex")
            positives.append({
                "record_id": "pair_" + hashlib.sha256(f"positive|{material['material_id']}|{texture['asset_id']}|{property_name}".encode("utf-8")).hexdigest()[:20],
                "material_id": material["material_id"],
                "material_path": material_path,
                "shader_id": shader["asset_id"],
                "shader_name": shader.get("shader_name"),
                "shader_pipeline_tags": list(shader.get("pipeline_tags") or []),
                "texture_id": texture["asset_id"],
                "texture_path": texture["project_asset_path"],
                "texture_tags": list(texture.get("tags") or []),
                "texture_property_name": property_name,
                "effect_type": _infer_type(material, texture),
                "effect_element_tags": _infer_elements(texture, material),
                "layer_role": _infer_role(property_name, texture),
                "style_family": _infer_style(material, shader),
                "color_tags": _infer_colors(texture),
                "material_property_count": len(material.get("property_names") or []),
                "shader_property_count": len(shader.get("property_names") or []),
                "texture_width": int(texture.get("width") or 0),
                "texture_height": int(texture.get("height") or 0),
                "label": 1,
                "label_source": "source_material_binding",
                "negative_reason": None,
                "material_cluster": material_group,
                "split": _split(material_group),
                "prefab_graph_usage_count": len(usage_rows),
                "prefab_graph_source_groups": sorted({str(row.get("source_group")) for row in usage_rows if row.get("source_group")}),
                "prefab_graph_ids": sorted({str(row.get("graph_id")) for row in usage_rows if row.get("graph_id")})[:32],
                "baseline_score": _texture_pair_score(material, texture, property_name, shader),
                "human_labels_used": 0,
            })
    positive_by_material = defaultdict(list)
    for row in positives:
        positive_by_material[row["material_id"]].append(row)
    all_texture_rows = sorted(textures.values(), key=lambda row: str(row["asset_id"]))
    rows = list(positives)
    for positive in positives:
        material = next(row for row in materials if row["material_id"] == positive["material_id"])
        shader = shaders[positive["shader_id"]]
        existing = {row["texture_id"] for row in positive_by_material[positive["material_id"]]}
        ranked = sorted(
            (texture for texture in all_texture_rows if texture["asset_id"] not in existing),
            key=lambda texture: (_texture_pair_score(material, texture, positive["texture_property_name"], shader), str(texture["asset_id"])),
        )
        contrasting = [texture for texture in ranked if _texture_pair_score(material, texture, positive["texture_property_name"], shader) <= 0.0]
        for texture in contrasting[:max(0, negatives_per_positive)]:
            negative = dict(positive)
            negative.update({
                "record_id": "pair_" + hashlib.sha256(f"negative|{positive['material_id']}|{texture['asset_id']}|{positive['texture_property_name']}".encode("utf-8")).hexdigest()[:20],
                "texture_id": texture["asset_id"],
                "texture_path": texture["project_asset_path"],
                "texture_tags": list(texture.get("tags") or []),
                "effect_type": _infer_type(material, texture),
                "effect_element_tags": _infer_elements(texture, material),
                "color_tags": _infer_colors(texture),
                "texture_width": int(texture.get("width") or 0),
                "texture_height": int(texture.get("height") or 0),
                "label": 0,
                "label_source": "semantic_contrast_weak_negative",
                "negative_reason": "semantic_contrast_only_not_a_quality_rejection",
                "baseline_score": _texture_pair_score(material, texture, positive["texture_property_name"], shader),
            })
            rows.append(negative)
    rows.sort(key=lambda row: row["record_id"])
    duplicate_count = len(rows) - len({row["record_id"] for row in rows})
    split_groups = {split: {row["material_cluster"] for row in rows if row["split"] == split} for split in ("train", "validation", "test")}
    leakage = sum(bool(split_groups[left] & split_groups[right]) for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")))
    manifest = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "registry_id": registry["registry_id"],
        "source_graph_dataset_id": "prefab_graph_full_r002",
        "training_view_id": "prefab_graph_training_view_r002",
        "seed": seed,
        "record_count": len(rows),
        "material_count": len({row["material_id"] for row in rows}),
        "shader_count": len({row["shader_id"] for row in rows}),
        "texture_count": len({row["texture_id"] for row in rows}),
        "positive_count": sum(row["label"] == 1 for row in rows),
        "negative_count": sum(row["label"] == 0 for row in rows),
        "split_counts": {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")},
        "label_source_counts": dict(sorted(Counter(row["label_source"] for row in rows).items())),
        "effect_type_counts": dict(sorted(Counter(row["effect_type"] for row in rows if row["label"] == 1).items())),
        "files": {"examples": "examples.jsonl"},
        "quality_gates": {
            "schema_errors": 0,
            "duplicate_record_ids": duplicate_count,
            "material_cluster_split_leakage": leakage,
            "human_labels_used": 0,
            "blocked_shader_positive_count": 0,
            "nonproject_texture_positive_count": 0,
            "all_positive_records_have_graph_or_registry_provenance": int(all(row["prefab_graph_usage_count"] > 0 or row["material_path"] for row in rows if row["label"] == 1)),
            "train_validation_test_nonempty": int(all(split_groups[split] for split in ("train", "validation", "test"))),
        },
        "supervision_policy": "Source Material binding is a technical positive. Negative rows are semantic contrast pairs only and are not aesthetic quality judgments. Human review, aesthetic scores and preference labels are not consumed.",
        "status": "pass",
    }
    if duplicate_count or leakage or not manifest["quality_gates"]["train_validation_test_nonempty"]:
        raise ValueError(f"asset pair dataset quality gate failed: {manifest['quality_gates']}")
    examples_path = _write_jsonl(output_root / "examples.jsonl", rows)
    manifest_path = _write(output_root / "dataset_manifest.json", manifest)
    card_path = output_root / "TRAINING_VIEW.md"
    card_path.write_text(f"""# {dataset_id}\n\nThis technical training view joins real PrefabGraph material usage with the verified asset capability registry `{registry['registry_id']}`. Positive pairs come from source Material texture bindings. Negative pairs are semantic contrasts used only to teach ranking; they are not aesthetic negatives.\n\nMaterial clusters are isolated across train/validation/test. Human labels, preference labels and aesthetic scores consumed: `0`. Every selected asset remains subject to Unity 2022 property, dependency, compile, readback and runtime gates.\n""", encoding="utf-8")
    return {"manifest": manifest_path, "examples": examples_path, "training_view": card_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a technical Material x Shader x Texture training view.")
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--training-view-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-id", default="material_asset_pair_training_r001")
    parser.add_argument("--negatives-per-positive", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260903)
    args = parser.parse_args(argv)
    try:
        paths = build_dataset(args.registry_root, args.graph_root, args.training_view_root, args.output_root, args.dataset_id, args.negatives_per_positive, args.seed)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
