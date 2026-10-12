"""Generate deterministic material-motion curriculum specs from imported Unity assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator


SCHEMA_VERSION = "material_trajectory_spec.v1"
MANIFEST_VERSION = "material_curriculum_manifest.v1"
DEFAULT_QUOTAS = {
    "dissolve": 20,
    "flow_distortion": 15,
    "emission_alpha": 15,
    "mpb": 15,
    "texture_swap": 10,
    "keyword_material": 10,
    "negative": 15,
}
CURVES = ("linear", "ease_in", "ease_out", "smoothstep", "pulse")
CONTROL_SCOPES = ("material", "renderer_mpb", "slot_mpb")
SEMANTIC_TERMS = {
    "dissolve": ("dissolv", "cutoff", "threshold", "clip", "burn", "erosion"),
    "flow_distortion": ("flow", "speed", "distort", "rotation", "rotate", "uv", "tiling", "offset"),
    "emission_alpha": ("emission", "glow", "alpha", "opacity", "fade", "color", "tint", "intensity"),
}
EXCLUDED_DYNAMIC_TERMS = ("blend", "zwrite", "ztest", "cull", "stencil", "mode", "queue", "particle", "global")


@dataclass
class MaterialCandidate:
    material_path: str
    material_name: str
    shader_name: str
    shader_path: str | None
    floats: dict[str, float] = field(default_factory=dict)
    ints: dict[str, int] = field(default_factory=dict)
    colors: dict[str, list[float]] = field(default_factory=dict)
    vectors: dict[str, list[float]] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    texture_bindings: list[dict[str, Any]] = field(default_factory=list)
    effect_families: list[str] = field(default_factory=list)
    source_categories: list[str] = field(default_factory=list)
    style_families: list[str] = field(default_factory=list)
    style_keywords: list[str] = field(default_factory=list)

    @property
    def material_group(self) -> str:
        return hashlib.sha1(self.material_path.encode("utf-8")).hexdigest()[:12]

    @property
    def shader_group(self) -> str:
        return hashlib.sha1(self.shader_name.encode("utf-8")).hexdigest()[:12]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _normalize_unity_path(value: str) -> str:
    return value.replace("\\", "/")


def _load_unity_material(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("%"))
    text = re.sub(r"^--- !u!\d+ &\d+\s*$", "---", text, flags=re.MULTILINE)
    document = yaml.safe_load(text)
    if not isinstance(document, dict) or not isinstance(document.get("Material"), dict):
        raise ValueError(f"Unity Material document expected: {path}")
    return document["Material"]


def _list_map(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and len(item) == 1:
            key, entry = next(iter(item.items()))
            result[str(key)] = entry
    return result


def _material_properties(material: dict[str, Any]) -> tuple[dict[str, float], dict[str, int], dict[str, list[float]], list[str]]:
    saved = material.get("m_SavedProperties") if isinstance(material.get("m_SavedProperties"), dict) else {}
    floats = {name: float(value) for name, value in _list_map(saved.get("m_Floats")).items() if isinstance(value, (int, float)) and not isinstance(value, bool)}
    ints = {name: int(value) for name, value in _list_map(saved.get("m_Ints")).items() if isinstance(value, int) and not isinstance(value, bool)}
    colors: dict[str, list[float]] = {}
    for name, value in _list_map(saved.get("m_Colors")).items():
        if isinstance(value, dict):
            colors[name] = [float(value.get(component, 0.0)) for component in ("r", "g", "b", "a")]
    keywords = sorted({str(value) for value in material.get("m_ValidKeywords", []) if isinstance(value, str) and value.strip()})
    return floats, ints, colors, keywords


def _case_context(cases: Iterable[dict[str, Any]]) -> dict[str, dict[str, set[str] | str | None]]:
    context: dict[str, dict[str, set[str] | str | None]] = defaultdict(
        lambda: {
            "shader_path": None,
            "effect_families": set(),
            "source_categories": set(),
            "style_families": set(),
            "style_keywords": set(),
        }
    )
    for case in cases:
        source = case.get("source") if isinstance(case.get("source"), dict) else {}
        inputs = case.get("inputs") if isinstance(case.get("inputs"), dict) else {}
        family = source.get("effect_family_hint")
        categories = source.get("source_category") if isinstance(source.get("source_category"), list) else []
        styles = [inputs.get("target_style_profile"), case.get("observations", {}).get("observed_style_profile") if isinstance(case.get("observations"), dict) else None]
        selection = inputs.get("material_selection") if isinstance(inputs.get("material_selection"), dict) else {}
        for material in selection.get("materials", []) if isinstance(selection.get("materials"), list) else []:
            if not isinstance(material, dict) or not isinstance(material.get("material_path"), str):
                continue
            path = _normalize_unity_path(material["material_path"])
            record = context[path]
            if isinstance(material.get("primary_shader_path"), str):
                record["shader_path"] = _normalize_unity_path(material["primary_shader_path"])
            if isinstance(family, str) and family:
                record["effect_families"].add(family)
            record["source_categories"].update(str(value) for value in categories)
            for style in styles:
                if not isinstance(style, dict):
                    continue
                if isinstance(style.get("family"), str):
                    record["style_families"].add(style["family"])
                record["style_keywords"].update(str(value) for value in style.get("keywords", []) if isinstance(value, str))
    return context


def load_material_candidates(
    unity_project: Path,
    prefab_cases_path: Path,
    material_audit_path: Path,
    texture_tags_path: Path,
) -> list[MaterialCandidate]:
    project = unity_project.resolve()
    cases = _read_jsonl(prefab_cases_path)
    context = _case_context(cases)
    texture_tags = {
        _normalize_unity_path(str(record["relative_path"])): sorted(set(str(tag) for tag in record.get("tags", [])))
        for record in _read_jsonl(texture_tags_path)
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str)
    }
    audit = _read_json(material_audit_path)
    candidates: list[MaterialCandidate] = []
    seen: set[str] = set()
    for record in audit.get("materials", []) if isinstance(audit.get("materials"), list) else []:
        if not isinstance(record, dict) or not isinstance(record.get("material_path"), str):
            continue
        material_path = _normalize_unity_path(record["material_path"])
        if material_path in seen or not material_path.lower().endswith(".mat"):
            continue
        physical_path = project / Path(material_path)
        if not physical_path.is_file():
            continue
        seen.add(material_path)
        try:
            material = _load_unity_material(physical_path)
            saved_floats, saved_ints, saved_colors, keywords = _material_properties(material)
        except (OSError, ValueError, yaml.YAMLError):
            continue
        property_types = {
            str(item.get("property_name")): str(item.get("property_type")).lower()
            for item in record.get("properties", [])
            if isinstance(item, dict) and isinstance(item.get("property_name"), str) and isinstance(item.get("property_type"), str)
        }
        floats = {name: value for name, value in saved_floats.items() if property_types.get(name) in {"float", "range"}}
        ints = {name: value for name, value in saved_ints.items() if property_types.get(name) == "int"}
        colors = {name: value for name, value in saved_colors.items() if property_types.get(name) == "color"}
        vectors = {name: value for name, value in saved_colors.items() if property_types.get(name) == "vector"}
        bindings = []
        for binding in record.get("bindings", []) if isinstance(record.get("bindings"), list) else []:
            if not isinstance(binding, dict) or not binding.get("is_bound") or not isinstance(binding.get("texture_path"), str):
                continue
            texture_path = _normalize_unity_path(binding["texture_path"])
            bindings.append(
                {
                    "property_name": str(binding.get("property_name") or ""),
                    "texture_path": texture_path,
                    "tags": texture_tags.get(texture_path, []),
                }
            )
        item_context = context.get(material_path, {})
        candidates.append(
            MaterialCandidate(
                material_path=material_path,
                material_name=str(material.get("m_Name") or Path(material_path).stem),
                shader_name=str(record.get("shader_name") or "unknown"),
                shader_path=item_context.get("shader_path") if isinstance(item_context.get("shader_path"), str) else None,
                floats=floats,
                ints=ints,
                colors=colors,
                vectors=vectors,
                keywords=keywords,
                texture_bindings=bindings,
                effect_families=sorted(item_context.get("effect_families", set())),
                source_categories=sorted(item_context.get("source_categories", set())),
                style_families=sorted(item_context.get("style_families", set())),
                style_keywords=sorted(item_context.get("style_keywords", set())),
            )
        )
    return sorted(candidates, key=lambda item: item.material_path.casefold())


def _semantic(name: str) -> str:
    lowered = name.lower()
    for semantic, terms in SEMANTIC_TERMS.items():
        if any(term in lowered for term in terms):
            return semantic
    return "generic_parameter"


def _eligible_properties(material: MaterialCandidate, category: str) -> list[tuple[str, str, list[float]]]:
    properties: list[tuple[str, str, list[float]]] = []
    for name, value in material.floats.items():
        lowered = name.lower()
        if any(term in lowered for term in EXCLUDED_DYNAMIC_TERMS):
            continue
        semantic = _semantic(name)
        if category in SEMANTIC_TERMS and semantic != category:
            continue
        properties.append((name, "float", [value]))
    for name, value in material.colors.items():
        semantic = _semantic(name)
        if category in SEMANTIC_TERMS and semantic != category:
            continue
        properties.append((name, "color", list(value)))
    for name, value in material.ints.items():
        semantic = _semantic(name)
        if category in SEMANTIC_TERMS and semantic != category:
            continue
        properties.append((name, "int", [float(value)]))
    for name, value in material.vectors.items():
        semantic = _semantic(name)
        if category in SEMANTIC_TERMS and semantic != category:
            continue
        properties.append((name, "vector", list(value)))
    return properties


def _source_payload(material: MaterialCandidate) -> dict[str, Any]:
    return {
        "material_path": material.material_path,
        "material_name": material.material_name,
        "shader_name": material.shader_name,
        "shader_path": material.shader_path,
        "texture_bindings": material.texture_bindings,
        "effect_families": material.effect_families,
        "source_categories": material.source_categories,
    }


def _style_payload(material: MaterialCandidate) -> dict[str, Any]:
    preferred = [value for value in material.style_families if value and value != "unknown"]
    return {"family": preferred[0] if preferred else "unknown", "keywords": material.style_keywords}


def _track(
    name: str,
    value_kind: str,
    start: list[float],
    end: list[float],
    semantic: str,
    curve: str,
    duration: float,
    start_time: float = 0.0,
) -> dict[str, Any]:
    return {
        "property_name": name,
        "semantic": semantic,
        "value_kind": value_kind,
        "start_value": [round(float(value), 6) for value in start],
        "end_value": [round(float(value), 6) for value in end],
        "curve": curve,
        "start_time_seconds": round(start_time, 4),
        "duration_seconds": round(max(0.02, duration - start_time), 4),
        "clamp_min": 0.0 if semantic in {"dissolve", "emission_alpha"} else None,
        "clamp_max": 1.0 if semantic == "dissolve" else None,
    }


def _signal_for_scope(scope: str) -> str:
    return {
        "material": "material_property_changed",
        "renderer_mpb": "renderer_property_block_changed",
        "slot_mpb": "slot_property_block_changed",
    }[scope]


def _replacement_texture(material: MaterialCandidate, textures: list[dict[str, Any]], rng: random.Random, incompatible: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    source = rng.choice(material.texture_bindings)
    source_tags = set(source["tags"])
    role_tags = {tag for tag in source_tags if tag.startswith("slot.") or tag.startswith("role.") or tag.startswith("semantic.")}
    pool = [item for item in textures if item["texture_path"] != source["texture_path"]]
    if incompatible:
        filtered = [item for item in pool if role_tags and not role_tags.intersection(item["tags"])]
    else:
        filtered = [item for item in pool if role_tags.intersection(item["tags"])]
    return source, rng.choice(filtered or pool)


def _base_spec(material: MaterialCandidate, curriculum_id: str, trajectory_id: str, seed: int, category: str, label: str, scope: str, duration: float) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "trajectory_id": trajectory_id,
        "curriculum_id": curriculum_id,
        "seed": seed,
        "category": category,
        "label": label,
        "source_asset": _source_payload(material),
        "style_profile": _style_payload(material),
        "control_scope": scope,
        "duration_seconds": round(duration, 4),
        "parameter_tracks": [],
        "keyword_events": [],
        "texture_swap_events": [],
        "material_replace_events": [],
        "expected_signals": [],
        "negative_mutation": None,
        "split_group": {"shader_group": material.shader_group, "material_group": material.material_group},
    }


def generate_specs(candidates: list[MaterialCandidate], texture_records: list[dict[str, Any]], curriculum_id: str, seed: int, quotas: dict[str, int]) -> list[dict[str, Any]]:
    if not candidates:
        raise ValueError("no imported .mat material candidates were found")
    rng = random.Random(seed)
    same_shader: dict[str, list[MaterialCandidate]] = defaultdict(list)
    for candidate in candidates:
        same_shader[candidate.shader_name].append(candidate)
    eligible = {
        "dissolve": [item for item in candidates if _eligible_properties(item, "dissolve")],
        "flow_distortion": [item for item in candidates if _eligible_properties(item, "flow_distortion")],
        "emission_alpha": [item for item in candidates if _eligible_properties(item, "emission_alpha")],
        "mpb": [item for item in candidates if _eligible_properties(item, "generic_parameter") or _eligible_properties(item, "emission_alpha")],
        "texture_swap": [item for item in candidates if item.texture_bindings],
        "keyword_material": [item for item in candidates if item.keywords or len(same_shader[item.shader_name]) > 1],
    }
    missing = [category for category in quotas if category != "negative" and quotas[category] > 0 and not eligible.get(category)]
    if missing:
        raise ValueError(f"no eligible materials for curriculum category: {missing[0]}")

    specs: list[dict[str, Any]] = []
    ordinal = 0
    for category, count in quotas.items():
        for index in range(count):
            ordinal += 1
            spec_seed = rng.randrange(0, 2**31)
            local = random.Random(spec_seed)
            duration = local.choice((0.6, 0.8, 1.0, 1.2, 1.5, 2.0))
            scope = local.choice(CONTROL_SCOPES)
            source_category = category if category != "negative" else local.choice(("dissolve", "flow_distortion", "emission_alpha", "mpb", "texture_swap"))
            pool = eligible[source_category]
            material = local.choice(pool)
            stem = re.sub(r"[^a-z0-9]+", "_", material.material_name.lower()).strip("_") or "material"
            trajectory_id = f"mtc_{ordinal:03d}_{category}_{stem}"
            spec = _base_spec(material, curriculum_id, trajectory_id, spec_seed, category, "negative" if category == "negative" else "positive", scope, duration)

            if source_category in {"dissolve", "flow_distortion", "emission_alpha", "mpb"}:
                property_category = source_category if source_category != "mpb" else "generic_parameter"
                options = _eligible_properties(material, property_category) or _eligible_properties(material, "emission_alpha")
                name, kind, start = local.choice(options)
                semantic = _semantic(name)
                if kind == "color":
                    end = [min(4.0, max(0.0, value * local.uniform(0.25, 2.0))) for value in start]
                    if semantic == "emission_alpha":
                        end[3] = local.choice((0.0, 1.0))
                elif kind == "vector":
                    end = [value + local.uniform(-2.0, 2.0) for value in start]
                elif kind == "int":
                    end = [float(int(start[0]) + local.choice((-2, -1, 1, 2)))]
                else:
                    if semantic == "dissolve":
                        start, end = [0.0], [1.0]
                    elif semantic == "flow_distortion":
                        end = [local.uniform(-3.0, 3.0)]
                    else:
                        end = [local.uniform(0.0, 3.0)]
                spec["parameter_tracks"].append(_track(name, kind, start, end, semantic, local.choice(CURVES), duration))
                spec["expected_signals"] = [_signal_for_scope(scope)]
                if semantic == "dissolve":
                    spec["expected_signals"].append("dissolve_parameter_changed")
            elif source_category == "texture_swap":
                source, replacement = _replacement_texture(material, texture_records, local, incompatible=category == "negative")
                spec["texture_swap_events"].append(
                    {
                        "time_seconds": round(duration * 0.45, 4),
                        "property_name": source["property_name"],
                        "from_texture_path": source["texture_path"],
                        "to_texture_path": replacement["texture_path"],
                        "from_tags": source["tags"],
                        "to_tags": replacement["tags"],
                    }
                )
                spec["expected_signals"] = ["texture_changed"]
            elif source_category == "keyword_material":
                if material.keywords:
                    spec["keyword_events"].append({"time_seconds": round(duration * 0.4, 4), "keyword": local.choice(material.keywords), "enabled": False})
                    spec["expected_signals"] = ["shader_keywords_changed"]
                else:
                    replacement = local.choice([item for item in same_shader[material.shader_name] if item.material_path != material.material_path])
                    spec["material_replace_events"].append(
                        {
                            "time_seconds": round(duration * 0.5, 4),
                            "from_material_path": material.material_path,
                            "to_material_path": replacement.material_path,
                            "same_shader_required": True,
                        }
                    )
                    spec["expected_signals"] = ["material_instance_replaced"]

            if category == "negative":
                mutation = local.choice(("abrupt_jump", "overshoot", "no_op", "incompatible_texture", "late_peak"))
                if spec["texture_swap_events"]:
                    mutation = "incompatible_texture"
                elif mutation == "incompatible_texture":
                    mutation = "abrupt_jump"
                if spec["parameter_tracks"]:
                    track = spec["parameter_tracks"][0]
                    if mutation == "abrupt_jump":
                        track["curve"] = "step"
                    elif mutation == "overshoot":
                        track["end_value"] = [value * 8.0 + 4.0 for value in track["end_value"]]
                        track["clamp_min"] = None
                        track["clamp_max"] = None
                    elif mutation == "no_op":
                        track["end_value"] = list(track["start_value"])
                        spec["expected_signals"] = []
                    elif mutation == "late_peak":
                        track["start_time_seconds"] = round(duration * 0.9, 4)
                        track["duration_seconds"] = round(duration * 0.1, 4)
                spec["negative_mutation"] = {
                    "type": mutation,
                    "severity": round(local.uniform(0.55, 1.0), 3),
                    "reason": {
                        "abrupt_jump": "Parameter changes in one visible step instead of a readable transition.",
                        "overshoot": "Parameter exceeds the source material's usable range.",
                        "no_op": "The trajectory requests no effective value change.",
                        "incompatible_texture": "Texture swap intentionally violates semantic slot tags.",
                        "late_peak": "The peak occurs too late to establish readable timing.",
                    }[mutation],
                }
                spec["expected_signals"] = sorted(set(spec["expected_signals"] + ["negative_trajectory"]))
            specs.append(spec)
    return specs


def _parse_quotas(values: list[str]) -> dict[str, int]:
    quotas = dict(DEFAULT_QUOTAS)
    for value in values:
        if "=" not in value:
            raise ValueError(f"quota must use category=count: {value}")
        category, raw_count = value.split("=", 1)
        if category not in DEFAULT_QUOTAS:
            raise ValueError(f"unknown quota category: {category}")
        count = int(raw_count)
        if count < 0:
            raise ValueError("quota count must be non-negative")
        quotas[category] = count
    return quotas


def build_curriculum(
    unity_project: Path,
    dataset_root: Path,
    material_audit_path: Path,
    output_root: Path,
    curriculum_id: str,
    seed: int,
    quotas: dict[str, int],
) -> dict[str, Any]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"curriculum output already exists and is not empty: {output_root}")
    candidates = load_material_candidates(
        unity_project,
        dataset_root / "prefab_cases.jsonl",
        material_audit_path,
        dataset_root / "texture_tags.jsonl",
    )
    textures_by_path: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        for binding in candidate.texture_bindings:
            textures_by_path[binding["texture_path"]] = {
                "property_name": binding["property_name"],
                "texture_path": binding["texture_path"],
                "tags": binding["tags"],
            }
    specs = generate_specs(candidates, list(textures_by_path.values()), curriculum_id, seed, quotas)
    schema_path = Path(__file__).parents[2] / "data/vfx_generation/schemas/material_trajectory.schema.json"
    schema = _read_json(schema_path)
    validator = Draft202012Validator(schema)
    spec_paths: list[str] = []
    specs_root = output_root / "specs"
    jsonl_lines: list[str] = []
    for spec in specs:
        errors = list(validator.iter_errors(spec))
        if errors:
            raise ValueError(f"generated invalid spec {spec['trajectory_id']}: {errors[0].message}")
        path = specs_root / f"{spec['trajectory_id']}.json"
        _write_json(path, spec)
        spec_paths.append(path.relative_to(output_root).as_posix())
        jsonl_lines.append(json.dumps(spec, ensure_ascii=False, sort_keys=True))
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "specs.jsonl").write_text("\n".join(jsonl_lines) + "\n", encoding="utf-8")
    category_counts = Counter(spec["category"] for spec in specs)
    label_counts = Counter(spec["label"] for spec in specs)
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "curriculum_id": curriculum_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "unity_project": unity_project.resolve().as_posix(),
        "dataset_root": dataset_root.resolve().as_posix(),
        "material_audit_path": material_audit_path.resolve().as_posix(),
        "material_candidate_count": len(candidates),
        "texture_candidate_count": len(textures_by_path),
        "spec_count": len(specs),
        "category_counts": dict(sorted(category_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "shader_group_count": len({spec["split_group"]["shader_group"] for spec in specs}),
        "material_group_count": len({spec["split_group"]["material_group"] for spec in specs}),
        "spec_paths": spec_paths,
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic material trajectory curriculum specs.")
    parser.add_argument("--unity-project", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--material-audit", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--curriculum-id", required=True)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--quota", action="append", default=[], help="override one category count, e.g. dissolve=20")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        quotas = _parse_quotas(args.quota)
        manifest = build_curriculum(
            args.unity_project,
            args.dataset_root,
            args.material_audit,
            args.output_root,
            args.curriculum_id,
            args.seed,
            quotas,
        )
    except (FileExistsError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
