"""Train a prompt-conditioned profile router and emit legal PrefabGraph candidates."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from PIL import Image
from torch import Tensor, nn
from jsonschema import Draft202012Validator

from .prefab_asset_router import build_asset_route_plan
from .prefab_graph import _read_json, _schema_root, assign_graph_id
from .prefab_graph_constrained import tokens_to_graph, valid_templates, validate_token_grammar
from .material_plan import apply_material_plan, build_material_plan, load_registry
from .material_asset_pair_model import load_model as load_asset_pair_model


CONDITION_DATASET_SCHEMA = "vfx_prompt_graph_condition_training_dataset.v1"
GENERATION_SCHEMA = "vfx_prompt_graph_generation_manifest.v1"
MODEL_SCHEMA = "vfx_prompt_graph_condition_model.v1"
MODEL_VERSION = "prompt_graph_profile_mlp.v1"
PROFILE_CLASSES = ("particle_v1", "multi_particle")
FEATURE_SPACE = {
    "effect_family": ("lightning", "explosion", "slash", "fire", "shield", "smoke", "water", "magic_circle"),
    "style_family": ("realistic", "cartoon", "stylized", "anime"),
    "timing_profile": ("fast_impact", "short", "medium", "long", "loop"),
    "performance_tier": ("mobile", "standard"),
    "color": ("blue", "cyan", "orange", "red", "purple", "white"),
}
FAMILY_TERMS = {
    "impact": ("命中", "受击", "击中", "爆点", "hit", "impact"),
    "explosion": ("爆炸", "爆破", "explosion"),
    "slash": ("刀光", "斩击", "斩", "slash", "blade"),
    "magic_circle": ("法阵", "符文", "magic circle", "rune"),
    "laser": ("激光", "laser", "beam"),
    "lightning": ("雷电", "闪电", "雷", "电", "lightning", "thunder", "electric"),
    "fire": ("火焰", "火球", "燃烧", "火", "fire", "flame"),
    "shield": ("护盾", "屏障", "盾", "shield", "barrier"),
    "smoke": ("烟雾", "烟", "smoke"),
    "water": ("水花", "水", "water", "splash"),
}
ELEMENT_TERMS = {
    "fire": ("火焰", "火球", "燃烧", "火", "fire", "flame"),
    "ice": ("冰霜", "寒冰", "冰", "frost", "ice", "snow"),
    "lightning": ("雷电", "闪电", "雷", "电", "lightning", "thunder", "electric"),
    "energy": ("能量", "能量体", "energy", "plasma"),
    "water": ("水花", "水", "water", "splash"),
    "smoke": ("烟雾", "烟", "smoke", "dust"),
    "wind": ("风", "气流", "wind"),
    "earth": ("岩石", "土", "大地", "earth", "stone"),
    "light": ("圣光", "holy light"),
    "dark": ("暗影", "黑暗", "暗", "dark", "shadow"),
}
STYLE_TERMS = {"realistic": ("写实", "realistic"), "cartoon": ("卡通", "cartoon"), "stylized": ("风格化", "stylized"), "anime": ("动漫", "二次元", "anime")}
TIMING_TERMS = {"fast_impact": ("快速", "瞬间", "短促", "fast", "burst"), "loop": ("循环", "持续", "loop"), "long": ("长", "long"), "short": ("短", "short")}
COLOR_TERMS = {"blue": ("蓝", "blue"), "cyan": ("青", "cyan"), "orange": ("橙", "orange"), "red": ("红", "red"), "purple": ("紫", "purple"), "white": ("白", "white")}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _validate(schema_name: str, value: dict[str, Any], label: str) -> None:
    schema = _read_json(_schema_root() / schema_name)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _contains(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def parse_prompt_condition(text: str, prompt_id: str, seed: int, performance_tier: str = "standard") -> dict[str, Any]:
    effect_type = next((name for name, terms in FAMILY_TERMS.items() if _contains(text, terms)), "lightning")
    effect_element_tags = [name for name, terms in ELEMENT_TERMS.items() if _contains(text, terms)]
    if not effect_element_tags:
        effect_element_tags = ["energy"] if _contains(text, ("能量", "energy")) else ["lightning"]
    style = next((name for name, terms in STYLE_TERMS.items() if _contains(text, terms)), "realistic")
    timing_text = text
    for marker in ("不要", "避免", "禁止", "without", "no"):
        if marker in timing_text.lower():
            timing_text = timing_text[:timing_text.lower().index(marker)]
            break
    timing = next((name for name, terms in TIMING_TERMS.items() if _contains(timing_text, terms)), "medium")
    colors = [name for name, terms in COLOR_TERMS.items() if _contains(text, terms)]
    color = colors[0] if colors else "blue"
    condition = {
        "schema_version": "vfx_prompt_condition.v2",
        "prompt_id": prompt_id,
        "text": text,
        "style_family": style,
        "color_keywords": colors or [color],
        "effect_element_tags": effect_element_tags,
        "effect_type": effect_type,
        "target_effect_family": effect_type,
        "effect_families": [effect_type],
        "source_categories": ["battle"],
        "motion_keywords": ["impact"] if timing == "fast_impact" or effect_type == "impact" else ["flow"],
        "timing_profile": timing,
        "negative_constraints": ["长拖尾"] if "不要长拖尾" in text or "without long trail" in text.lower() else [],
        "candidate_count": 4,
        "seed": seed,
        "performance_tier": performance_tier,
    }
    _validate("vfx_prompt_condition_v2.schema.json", condition, "Prompt condition")
    return condition


def _target_profile(family: str, timing: str, performance: str) -> str:
    if performance == "mobile":
        return "particle_v1"
    return "multi_particle" if family in {"impact", "explosion", "fire", "shield", "magic_circle", "smoke", "water"} else "particle_v1"


def _condition_prompt(family: str, style: str, timing: str, color: str, performance: str) -> str:
    family_names = {"lightning": "雷电", "explosion": "爆炸冲击", "slash": "刀光", "fire": "火焰", "shield": "护盾", "smoke": "烟雾", "water": "水花", "magic_circle": "法阵"}
    timing_names = {"fast_impact": "快速爆发", "short": "短促", "medium": "中等节奏", "long": "长持续", "loop": "循环"}
    return f"{style} {color} {family_names[family]}，{timing_names[timing]}，{performance}，不要长拖尾"


def build_condition_dataset(output_root: Path, dataset_id: str = "prefab_graph_prompt_condition_r001") -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"condition dataset output already exists and is not empty: {output_root}")
    rows: list[dict[str, Any]] = []
    families = tuple(FEATURE_SPACE["effect_family"])
    styles = ("realistic", "cartoon")
    timings = ("fast_impact", "loop")
    colors = ("blue", "orange")
    performances = ("standard", "mobile")
    index = 0
    for family in families:
        for style in styles:
            for timing in timings:
                for color in colors:
                    performance = performances[index % len(performances)]
                    prompt = _condition_prompt(family, style, timing, color, performance)
                    condition = parse_prompt_condition(prompt, f"pgc_{index:03d}", 20260902 + index, performance)
                    rows.append({
                        "schema_version": "vfx_prompt_graph_condition_training_example.v1",
                        "example_id": f"{dataset_id}_{index:03d}",
                        "prompt_condition": condition,
                        "effect_family": family,
                        "style_family": style,
                        "timing_profile": timing,
                        "performance_tier": performance,
                        "target_profile": _target_profile(family, timing, performance),
                        "split": "train",
                        "split_group": {"prompt_group": f"condition_template_{index:03d}"},
                        "supervision": {"label_source": "ai_hypothesis", "human_label": False, "aesthetic_label": False, "status": "hypothesis_only"},
                    })
                    index += 1
    profile_seen: dict[str, int] = {}
    for row in rows:
        profile = str(row["target_profile"])
        local_index = profile_seen.get(profile, 0)
        row["split"] = "validation" if local_index % 5 == 0 else "test" if local_index % 5 == 1 else "train"
        profile_seen[profile] = local_index + 1
    examples_path = _write_jsonl(output_root / "examples.jsonl", rows)
    manifest = {
        "schema_version": CONDITION_DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "example_count": len(rows),
        "split_counts": {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")},
        "effect_families": list(families),
        "supervision": {"label_source": "ai_hypothesis", "human_labels_used": 0, "aesthetic_labels_used": 0, "status": "hypothesis_only"},
        "files": {"examples": examples_path.name},
        "status": "pass",
    }
    _validate("prompt_graph_condition_training_dataset.schema.json", manifest, "Prompt Graph condition dataset")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {"manifest": manifest_path, "examples": examples_path}


def _feature_vector(condition: dict[str, Any]) -> list[float]:
    values: list[float] = []
    family = str((condition.get("effect_families") or ["lightning"])[0])
    color = str((condition.get("color_keywords") or ["blue"])[0])
    for key, categories in FEATURE_SPACE.items():
        if key == "effect_family":
            value = family
        elif key == "color":
            value = color
        else:
            value = str(condition.get(key) or "")
        values.extend(1.0 if value == category else 0.0 for category in categories)
    return values


class PromptGraphProfileModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 32, class_count: int = len(PROFILE_CLASSES)) -> None:
        super().__init__()
        self.network = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, class_count))

    def forward(self, inputs: Tensor) -> Tensor:
        return self.network(inputs)


def _evaluate(model: PromptGraphProfileModel, rows: list[dict[str, Any]], device: torch.device) -> dict[str, float]:
    if not rows:
        return {"example_count": 0.0, "accuracy": 0.0, "cross_entropy": 0.0}
    model.eval()
    x = torch.tensor([_feature_vector(row["prompt_condition"]) for row in rows], dtype=torch.float32, device=device)
    y = torch.tensor([PROFILE_CLASSES.index(row["target_profile"]) for row in rows], dtype=torch.long, device=device)
    with torch.inference_mode():
        logits = model(x)
        loss = nn.CrossEntropyLoss()(logits, y)
    return {"example_count": float(len(rows)), "accuracy": float((logits.argmax(dim=-1) == y).float().mean().item()), "cross_entropy": float(loss.item())}


def train_profile_model(dataset_root: Path, output_dir: Path, epochs: int = 80, hidden_dim: int = 32, learning_rate: float = 0.01, seed: int = 20260902) -> dict[str, Path]:
    dataset_root = dataset_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"model output already exists and is not empty: {output_dir}")
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    if manifest.get("schema_version") != CONDITION_DATASET_SCHEMA or manifest.get("status") != "pass":
        raise ValueError(f"verified Prompt Graph condition dataset expected: {dataset_root}")
    rows = _read_jsonl(dataset_root / manifest["files"]["examples"])
    if any(row.get("supervision", {}).get("label_source") != "ai_hypothesis" or row.get("supervision", {}).get("human_label") for row in rows):
        raise ValueError("Prompt profile model only accepts explicit ai_hypothesis condition labels")
    splits = {name: [row for row in rows if row["split"] == name] for name in ("train", "validation", "test")}
    device = torch.device("cpu")
    random.seed(seed)
    torch.manual_seed(seed)
    model = PromptGraphProfileModel(len(_feature_vector(rows[0]["prompt_condition"])), hidden_dim).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    x = torch.tensor([_feature_vector(row["prompt_condition"]) for row in splits["train"]], dtype=torch.float32, device=device)
    y = torch.tensor([PROFILE_CLASSES.index(row["target_profile"]) for row in splits["train"]], dtype=torch.long, device=device)
    class_counts = torch.bincount(y, minlength=len(PROFILE_CLASSES)).float()
    class_weights = class_counts.sum() / torch.clamp(class_counts * len(PROFILE_CLASSES), min=1.0)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(x), y)
        loss.backward()
        optimizer.step()
    metrics = {name: _evaluate(model, split_rows, device) for name, split_rows in splits.items()}
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "prompt_graph_profile_model.pt"
    torch.save({"schema_version": MODEL_SCHEMA, "model_version": MODEL_VERSION, "state_dict": model.state_dict(), "feature_space": FEATURE_SPACE, "profile_classes": PROFILE_CLASSES, "config": {"input_dim": len(_feature_vector(rows[0]["prompt_condition"])), "hidden_dim": hidden_dim}}, checkpoint_path)
    metrics_path = _write_json(output_dir / "metrics.json", {"schema_version": MODEL_SCHEMA, "model_version": MODEL_VERSION, "dataset_id": manifest["dataset_id"], "metrics": metrics, "human_labels_used": 0, "aesthetic_labels_used": 0, "supervision_status": "ai_hypothesis_only", "status": "experimental_ai_hypothesis_router", "created_at": datetime.now(timezone.utc).isoformat()})
    card_path = output_dir / "MODEL_CARD.md"
    card_path.write_text(f"""# Prompt Graph Profile Model

Status: `experimental_ai_hypothesis_router`.

This is a small MLP that routes canonical Prompt condition fields to a legal PrefabGraph profile. The {manifest['example_count']} training targets are curriculum/type priors marked `ai_hypothesis`; no human aesthetic labels, A/B labels, images or source Prefab paths were used.

It does not understand arbitrary natural language beyond the explicit keyword parser, does not learn visual quality, and does not generate Material, Shader, Texture or Mesh content. Every output still requires Grammar validation, AssetPlan routing, Unity compilation, Play Mode capture and visual review.
""", encoding="utf-8")
    return {"checkpoint": checkpoint_path, "metrics": metrics_path, "model_card": card_path}


def _load_profile_model(checkpoint_path: Path) -> tuple[PromptGraphProfileModel, dict[str, Any]]:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    if payload.get("schema_version") != MODEL_SCHEMA or payload.get("model_version") != MODEL_VERSION:
        raise ValueError(f"unsupported Prompt Graph profile checkpoint: {checkpoint_path}")
    config = payload["config"]
    model = PromptGraphProfileModel(int(config["input_dim"]), int(config["hidden_dim"]), len(payload["profile_classes"]))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, payload


def _predict_profile(model: PromptGraphProfileModel, payload: dict[str, Any], condition: dict[str, Any]) -> tuple[str, float]:
    with torch.inference_mode():
        probabilities = torch.softmax(model(torch.tensor([_feature_vector(condition)], dtype=torch.float32)), dim=-1)[0]
    index = int(probabilities.argmax().item())
    return str(payload["profile_classes"][index]), float(probabilities[index].item())


def _apply_condition(graph: dict[str, Any], condition: dict[str, Any], family: str, style: str, profile: str, candidate_seed: int, variation_index: int) -> dict[str, Any]:
    graph["condition"] = {"prompt": condition["text"], "effect_family": family, "style_family": style, "seed": candidate_seed, "parent_prefab_path": None}
    duration = 0.8 if condition["timing_profile"] == "fast_impact" else 1.2 if condition["timing_profile"] == "short" else 1.5
    looping = condition["timing_profile"] == "loop"
    color_map = {"blue": [0.08, 0.35, 1.0, 0.95], "cyan": [0.05, 0.9, 1.0, 0.95], "orange": [1.0, 0.3, 0.05, 0.95], "red": [1.0, 0.06, 0.02, 0.95], "purple": [0.55, 0.15, 1.0, 0.95], "white": [1.0, 1.0, 1.0, 0.95]}
    start_color = color_map.get(condition["color_keywords"][0], color_map["blue"])
    end_color = [start_color[0] * 0.35, start_color[1] * 0.35, start_color[2], 0.0]
    scale = 0.8 + (variation_index % 4) * 0.15
    speed_scale = 0.75 + (variation_index % 3) * 0.25
    for particle_index, particle in enumerate(graph["components"]["particle_systems"]):
        parameters = particle["parameters"]
        parameters.update({"duration_seconds": duration * (0.9 + 0.05 * (variation_index % 3)), "looping": looping, "max_particles": 32 if condition["performance_tier"] == "mobile" else 64, "start_color_rgba": start_color, "end_color_rgba": end_color, "burst_particle_count": (8 if condition["timing_profile"] == "fast_impact" else 16) + variation_index % 5, "start_size_max": max(0.05, float(parameters.get("start_size_max") or 1.0) * scale * (1.0 + particle_index * 0.08)), "start_speed_max": float(parameters.get("start_speed_max") or 1.0) * speed_scale, "shape_radius": max(0.05, float(parameters.get("shape_radius") or 0.1) * scale)})
        parameters["serialized_modules"] = {"profile": f"prompt_condition_{profile}", "condition_family": family, "condition_style": style, "variation_index": variation_index}
    graph["reconstruction"] = {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []}
    graph["training"] = {"eligible_tasks": ["component_prediction", "full_reconstruction", "hierarchy_modeling", "particle_parameter_modeling"], "excluded_tasks": ["aesthetic_preference", "prompt_condition"], "aesthetic_label_source": "ai_hypothesis"}
    return graph


def generate_from_prompt(
    prompt: str,
    profile_checkpoint: Path,
    structure_checkpoint: Path,
    output_root: Path,
    material_audit_path: Path | None,
    texture_tag_path: Path | None,
    mesh_root: Path | None,
    mesh_audit_path: Path | None,
    candidate_count: int = 1,
    seed: int = 20260902,
    performance_tier: str = "standard",
    asset_registry_root: Path | None = None,
    asset_pair_model_path: Path | None = None,
) -> Path:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"generation output already exists and is not empty: {output_root}")
    profile_model, profile_payload = _load_profile_model(profile_checkpoint)
    structure_payload = torch.load(structure_checkpoint.resolve(), map_location="cpu", weights_only=True)
    vocabulary = structure_payload.get("vocabulary")
    if not isinstance(vocabulary, dict):
        raise ValueError("structure checkpoint vocabulary is missing")
    prompt_condition = parse_prompt_condition(prompt, "prompt_graph_generation_001", seed, performance_tier)
    registry = load_registry(asset_registry_root) if asset_registry_root is not None else None
    asset_pair_model = load_asset_pair_model(asset_pair_model_path) if asset_pair_model_path is not None else None
    profile, profile_probability = _predict_profile(profile_model, profile_payload, prompt_condition)
    templates = valid_templates(vocabulary, profile)
    candidates: list[dict[str, Any]] = []
    for index in range(max(1, candidate_count)):
        tokens = templates[index % len(templates)]
        grammar_events = validate_token_grammar(tokens, profile)
        graph = tokens_to_graph(tokens, profile, prompt, prompt_condition["style_family"], seed + index, "prompt_condition_generation")
        candidate_seed = seed + index
        graph = _apply_condition(graph, prompt_condition, prompt_condition["effect_type"], prompt_condition["style_family"], profile, candidate_seed, index)
        graph = assign_graph_id(graph)
        if registry is not None:
            condition = {**prompt_condition, "effect_family": prompt_condition["effect_type"]}
            plan = build_material_plan(graph, registry, condition, seed=candidate_seed, alternatives_per_layer=4, asset_pair_model=asset_pair_model)
            if plan["status"] == "pass":
                for layer in plan["layers"]:
                    layer["selected_candidate_id"] = layer["candidates"][index % len(layer["candidates"])]["candidate_id"]
                graph = apply_material_plan(graph, plan)
                plan["graph_id"] = graph["graph_id"]
                plan["plan_id"] = f"material_plan_{graph['graph_id']}"
            plan_file_name = "material_plan.json"
        else:
            if any(value is None for value in (material_audit_path, texture_tag_path, mesh_root, mesh_audit_path)):
                raise ValueError("legacy asset routing requires material audit, texture tags, mesh root and mesh audit")
            plan = build_asset_route_plan(graph, material_audit_path, texture_tag_path, mesh_root, mesh_audit_path, prompt=prompt, effect_family=prompt_condition["effect_type"], style_family=prompt_condition["style_family"], seed=candidate_seed)
            billboard = next(route for route in plan["routes"] if route["route_kind"] == "billboard")
            for particle in graph["components"]["particle_systems"]:
                particle["material_paths"] = []
                particle["parameters"]["material_template_path"] = billboard["material"]["path"]
                particle["parameters"]["texture_asset_path"] = billboard["texture"]["path"]
                particle["parameters"]["texture_property_name"] = "_MainTex"
                particle["parameters"]["texture_profile"] = None
            for renderer in graph["components"]["renderers"]:
                renderer["material_paths"] = []
            graph["asset_bindings"]["materials"] = [billboard["material"]["path"]]
            graph = assign_graph_id(graph)
            plan["graph_id"] = graph["graph_id"]
            plan["plan_id"] = f"asset_route_{graph['graph_id']}"
            plan_file_name = "asset_route_plan.json"
        candidate_id = f"{prompt_condition['prompt_id']}_{index:03d}_{graph['graph_id']}"
        candidate_root = output_root / "candidates" / candidate_id
        graph_path = _write_json(candidate_root / "graph.json", graph)
        plan_path = _write_json(candidate_root / plan_file_name, plan)
        candidates.append({"candidate_id": candidate_id, "graph_id": graph["graph_id"], "profile": profile, "graph_path": graph_path.as_posix(), "asset_plan_path": plan_path.as_posix(), "parent_prefab_path": None, "grammar_valid": bool(grammar_events), "graph_schema_valid": True, "asset_plan_status": plan["status"], "unity_compile_status": "not_run", "runtime_visibility_status": "not_run", "compile_result_path": None, "capture_manifest_path": None, "max_visible_area_ratio": None, "profile_probability": profile_probability, "training_scope": "prompt_condition_ai_hypothesis_only", "seed": candidate_seed, "generator_version": MODEL_VERSION, "ai_hypothesis_score": None, "ai_hypothesis_label_source": "ai_hypothesis", "in_success_set": False})
    graph_ids = [candidate["graph_id"] for candidate in candidates]
    manifest = {"schema_version": GENERATION_SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name, "prompt_condition": prompt_condition, "model": {"profile_checkpoint": profile_checkpoint.resolve().as_posix(), "structure_checkpoint": structure_checkpoint.resolve().as_posix(), "predicted_profile": profile, "profile_probability": profile_probability, "asset_registry": asset_registry_root.resolve().as_posix() if asset_registry_root is not None else None, "asset_pair_model": asset_pair_model_path.resolve().as_posix() if asset_pair_model_path is not None else None, "supervision_status": "ai_hypothesis_only"}, "candidate_count": len(candidates), "candidates": candidates, "quality_gates": {"schema_valid_count": len(candidates), "grammar_valid_count": sum(row["grammar_valid"] for row in candidates), "asset_plan_pass_count": sum(row["asset_plan_status"] == "pass" for row in candidates), "unity_compile_pass_count": 0, "runtime_visible_count": 0, "technical_success_count": 0, "unique_graph_ids": len(graph_ids) == len(set(graph_ids)), "human_aesthetic_labels_used": 0}, "status": "generated_pending_unity" if any(row["asset_plan_status"] == "pass" for row in candidates) else "blocked"}
    _validate("prompt_graph_generation_manifest.schema.json", manifest, "Prompt Graph generation manifest")
    return _write_json(output_root / "generation_manifest.json", manifest)


def _visible_ratio(path: Path) -> float:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    height, width = rgb.shape[:2]
    corners = np.concatenate((rgb[:8, :8].reshape(-1, 3), rgb[:8, -8:].reshape(-1, 3), rgb[-8:, :8].reshape(-1, 3), rgb[-8:, -8:].reshape(-1, 3)))
    background = np.median(corners, axis=0)
    return float((np.max(np.abs(rgb - background), axis=2) > 8).mean())


def build_runtime_request(manifest_paths: Iterable[Path], output_path: Path, width: int = 512, height: int = 512) -> Path:
    output_path = output_path.resolve()
    capture_root = output_path.parent / "runtime_captures"
    requests: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        manifest_path = manifest_path.resolve()
        manifest = _read_json(manifest_path)
        for candidate in manifest["candidates"]:
            candidate_id = str(candidate["candidate_id"])
            compile_result_path = manifest_path.parent / "compile_results" / f"{candidate_id}.json"
            compile_result = _read_json(compile_result_path)
            if compile_result.get("status") != "pass":
                raise ValueError(f"passing compile result required for runtime capture: {candidate_id}")
            candidate_root = capture_root / candidate_id
            requests.append({
                "candidate_id": candidate_id,
                "prefab_path": compile_result["output_prefab_path"],
                "capture_dir": (candidate_root / "captures").as_posix(),
                "capture_manifest_path": (candidate_root / "capture_manifest.json").as_posix(),
                "material_timeline_path": (candidate_root / "material_timeline.json").as_posix(),
                "source_script_fidelity": "generated_graph_no_source_scripts",
                "ignored_script_dependency_count": 0,
                "missing_script_count": 0,
                "capture_category": "generated_prefab",
            })
    if not requests:
        raise ValueError("at least one compiled Prompt Graph candidate is required")
    payload = {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_path.parent.name,
        "scene": "PromptGraphRuntimeCapture",
        "camera": "PromptGraphRuntimeCamera",
        "width": width,
        "height": height,
        "sampling_mode": "adaptive_runtime",
        "sampling": {"target_intervals": 10, "min_interval_seconds": 0.02, "max_interval_seconds": 0.1, "max_duration_seconds": 8.0, "include_zero": True, "duration_sources": ["particle_system"]},
        "requests": requests,
    }
    return _write_json(output_path, payload)


def build_compile_request(manifest_paths: Iterable[Path], output_path: Path, asset_root: str) -> Path:
    output_path = output_path.resolve()
    requests: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        manifest_path = manifest_path.resolve()
        manifest = _read_json(manifest_path)
        family = str((manifest.get("prompt_condition", {}).get("effect_families") or ["unknown"])[0])
        for index, candidate in enumerate(manifest["candidates"]):
            if candidate.get("asset_plan_status") != "pass":
                raise ValueError(f"passing MaterialPlan or AssetPlan required before compile: {candidate.get('candidate_id')}")
            requests.append({
                "graph_path": str(Path(candidate["graph_path"]).resolve()),
                "output_prefab_path": f"{asset_root.rstrip('/')}/{family}/candidate_{index:03d}/GeneratedRoot.prefab",
                "result_path": str((manifest_path.parent / "compile_results" / f"{candidate['candidate_id']}.json").resolve()),
            })
    if not requests:
        raise ValueError("at least one generated Prompt Graph is required for batch compile")
    return _write_json(output_path, {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})


def finalize_generation_manifest(manifest_path: Path, compile_results_dir: Path, capture_root: Path) -> Path:
    manifest_path = manifest_path.resolve()
    manifest = _read_json(manifest_path)
    compile_results_dir = compile_results_dir.resolve()
    capture_root = capture_root.resolve()
    for candidate in manifest["candidates"]:
        candidate_id = str(candidate["candidate_id"])
        graph = _read_json(Path(candidate["graph_path"]).resolve())
        candidate.setdefault("graph_id", graph["graph_id"])
        candidate.setdefault("seed", int((graph.get("condition") or {}).get("seed") or 0))
        candidate.setdefault("generator_version", MODEL_VERSION)
        candidate.setdefault("ai_hypothesis_score", None)
        candidate.setdefault("ai_hypothesis_label_source", "ai_hypothesis")
        candidate.setdefault("in_success_set", False)
        result_path = compile_results_dir / f"{candidate_id}.json"
        capture_path = capture_root / candidate_id / "capture_manifest.json"
        compile_result = _read_json(result_path) if result_path.is_file() else {}
        capture = _read_json(capture_path) if capture_path.is_file() else {}
        candidate["unity_compile_status"] = "pass" if compile_result.get("status") == "pass" else "fail"
        candidate["compile_result_path"] = result_path.as_posix() if result_path.is_file() else None
        candidate["capture_manifest_path"] = capture_path.as_posix() if capture_path.is_file() else None
        frames = [capture_path.parent / "captures" / str(frame.get("path")) for frame in capture.get("frames") or []]
        if not frames:
            frames = [capture_path.parent / "frames" / str(frame.get("path")) for frame in capture.get("frames") or []]
        existing = [path for path in frames if path.is_file()]
        max_ratio = max((_visible_ratio(path) for path in existing), default=0.0)
        candidate["max_visible_area_ratio"] = max_ratio
        if candidate["unity_compile_status"] != "pass":
            candidate["runtime_visibility_status"] = "fail"
        elif capture.get("render_error") or int(capture.get("invalid_frame_count") or 0) > 0:
            candidate["runtime_visibility_status"] = "fail"
        else:
            candidate["runtime_visibility_status"] = "visible" if max_ratio >= 0.001 else "near_blank"
        technical_success = candidate["graph_schema_valid"] and candidate["grammar_valid"] and candidate["asset_plan_status"] == "pass" and candidate["unity_compile_status"] == "pass" and candidate["runtime_visibility_status"] == "visible"
        candidate["in_success_set"] = technical_success
        candidate["ai_hypothesis_score"] = round((0.4 + min(0.6, max_ratio * 12.0)) if technical_success else 0.0, 6)
    graph_ids = [row["graph_id"] for row in manifest["candidates"]]
    success_count = sum(row["in_success_set"] for row in manifest["candidates"])
    manifest["quality_gates"] = {"schema_valid_count": sum(row["graph_schema_valid"] for row in manifest["candidates"]), "grammar_valid_count": sum(row["grammar_valid"] for row in manifest["candidates"]), "asset_plan_pass_count": sum(row["asset_plan_status"] == "pass" for row in manifest["candidates"]), "unity_compile_pass_count": sum(row["unity_compile_status"] == "pass" for row in manifest["candidates"]), "runtime_visible_count": sum(row["runtime_visibility_status"] == "visible" for row in manifest["candidates"]), "technical_success_count": success_count, "unique_graph_ids": len(graph_ids) == len(set(graph_ids)), "human_aesthetic_labels_used": 0}
    manifest["status"] = "pass_technical_prompt_unscored" if success_count > 0 else "blocked"
    _validate("prompt_graph_generation_manifest.schema.json", manifest, "final Prompt Graph generation manifest")
    return _write_json(manifest_path, manifest)


def build_dual_family_report(manifest_paths: Iterable[Path], output_path: Path) -> Path:
    rows: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        manifest_path = manifest_path.resolve()
        manifest = _read_json(manifest_path)
        family = str((manifest["prompt_condition"].get("effect_families") or ["unknown"])[0])
        candidates = manifest["candidates"]
        particle_budgets = []
        generated_material_count = 0
        generated_texture_count = 0
        source_prefab_reads = 0
        vfxspec_valid_count = 0
        for candidate in candidates:
            graph = _read_json(Path(candidate["graph_path"]).resolve())
            particle_budgets.append(sum(int(item.get("parameters", {}).get("max_particles") or 0) for item in graph["components"]["particle_systems"]))
            compile_result = _read_json(Path(candidate["compile_result_path"]).resolve())
            generated_material_count += len(compile_result.get("generated_material_paths") or [])
            generated_texture_count += len(compile_result.get("generated_texture_paths") or [])
            source_prefab_reads += int(bool(compile_result.get("source_prefab_read")))
            spec_path = Path(str(candidate.get("vfxspec_path") or ""))
            if spec_path.is_file():
                spec = _read_json(spec_path)
                _validate("vfxspec.schema.json", spec, f"VFXSpec {candidate['candidate_id']}")
                vfxspec_valid_count += 1
        successful = [candidate for candidate in candidates if candidate.get("in_success_set")]
        selected = max(successful, key=lambda value: (float(value.get("ai_hypothesis_score") or 0.0), float(value.get("max_visible_area_ratio") or 0.0))) if successful else None
        count = len(candidates)
        rows.append({
            "effect_family": family,
            "manifest_path": manifest_path.as_posix(),
            "candidate_count": count,
            "unique_graph_count": len({candidate["graph_id"] for candidate in candidates}),
            "unique_seed_count": len({candidate["seed"] for candidate in candidates}),
            "schema_valid_count": manifest["quality_gates"]["schema_valid_count"],
            "asset_plan_pass_count": manifest["quality_gates"]["asset_plan_pass_count"],
            "unity_compile_pass_count": manifest["quality_gates"]["unity_compile_pass_count"],
            "runtime_visible_count": manifest["quality_gates"]["runtime_visible_count"],
            "technical_success_count": len(successful),
            "compile_rate": manifest["quality_gates"]["unity_compile_pass_count"] / max(1, count),
            "runtime_visible_rate": manifest["quality_gates"]["runtime_visible_count"] / max(1, count),
            "max_particle_budget": max(particle_budgets, default=0),
            "generated_material_count": generated_material_count,
            "generated_texture_count": generated_texture_count,
            "source_prefab_read_count": source_prefab_reads,
            "vfxspec_valid_count": vfxspec_valid_count,
            "dependency_closed": len(successful) > 0 and source_prefab_reads == 0,
            "selected_candidate": None if selected is None else {"candidate_id": selected["candidate_id"], "graph_id": selected["graph_id"], "seed": selected["seed"], "ai_hypothesis_score": selected["ai_hypothesis_score"], "max_visible_area_ratio": selected["max_visible_area_ratio"], "label_source": "ai_hypothesis"},
        })
    rows.sort(key=lambda value: value["effect_family"])
    pass_status = len(rows) == 2 and {row["effect_family"] for row in rows} == {"explosion", "slash"} and all(row["candidate_count"] >= 8 and row["vfxspec_valid_count"] == row["candidate_count"] and row["technical_success_count"] >= 1 and row["dependency_closed"] for row in rows)
    report = {
        "schema_version": "vfx_prompt_graph_dual_family_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "family_count": len(rows),
        "families": rows,
        "human_aesthetic_labels_used": 0,
        "limitations": ["AI scores are technical visibility hypotheses, not human aesthetic feedback.", "Current explosion and slash frames remain basic colored particle shapes, not high-quality family-specific effects.", "Performance values are configured particle budgets, not target-device GPU profiler measurements."],
        "status": "pass_technical_prompt_unscored" if pass_status else "blocked",
    }
    _validate("prompt_graph_dual_family_report.schema.json", report, "Prompt Graph dual-family report")
    return _write_json(output_path.resolve(), report)


def _candidate_vfxspec(manifest: dict[str, Any], candidate: dict[str, Any], graph: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    family = str((manifest["prompt_condition"].get("effect_families") or ["unknown"])[0])
    role_map = {"explosion": ("core_flash", "shockwave_ring", "debris_burst", "residual_smoke"), "slash": ("core_blade", "support_arc", "hit_accent", "residual_trail")}
    roles = role_map.get(family, ("core", "support", "hit", "residual"))
    particles_by_node = {item["node_id"]: item for item in graph["components"]["particle_systems"]}
    layers = []
    for index, node in enumerate(node for node in graph["nodes"] if node.get("role") != "root"):
        particle = particles_by_node.get(node["node_id"], {})
        parameters = particle.get("parameters") or {}
        layers.append({
            "role": roles[min(index, len(roles) - 1)],
            "status": "active",
            "topology": candidate["profile"],
            "shape_parameters": {"shape_type": parameters.get("shape_type"), "shape_radius": parameters.get("shape_radius"), "start_size_max": parameters.get("start_size_max")},
            "material_parameters": {"asset_plan_path": candidate["asset_plan_path"], "material_template_path": parameters.get("material_template_path"), "texture_profile": parameters.get("texture_profile")},
            "timing_parameters": {"duration_seconds": parameters.get("duration_seconds"), "start_lifetime_max": parameters.get("start_lifetime_max"), "burst_particle_count": parameters.get("burst_particle_count")},
            "constraints": ["ai_hypothesis_only", "unity_runtime_validation_required"],
        })
    spec = {
        "schema_version": "vfxspec.v1",
        "effect_family": family,
        "effect_type": family,
        "adapter": {"name": f"{family}.adapter", "version": MODEL_VERSION, "generator_family": candidate["profile"], "specialized_metrics": []},
        "prompt": manifest["prompt_condition"]["text"],
        "negative_prompt": ", ".join(manifest["prompt_condition"].get("negative_constraints") or []),
        "generation": {"run_id": manifest["run_id"], "candidate_id": candidate["candidate_id"], "seed": candidate["seed"], "generator": "prompt_graph_generator", "generator_version": candidate["generator_version"], "parent_candidate_id": None, "profile_checkpoint": manifest["model"]["profile_checkpoint"], "structure_checkpoint": manifest["model"]["structure_checkpoint"], "graph_id": graph["graph_id"]},
        "layers": layers,
        "render_plan": {"unity_project": "UnityDemo/EffectDemo", "scene": "PromptGraphRuntimeCapture", "camera": "PromptGraphRuntimeCamera", "resolution": "512x512", "time_points_seconds": []},
        "training_scope": "ai_hypothesis_only; no human aesthetic label",
    }
    _validate("vfxspec.schema.json", spec, f"VFXSpec {candidate['candidate_id']}")
    return spec


def attach_vfxspec(manifest_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    manifest = _read_json(manifest_path)
    for candidate in manifest["candidates"]:
        graph = _read_json(Path(candidate["graph_path"]).resolve())
        plan = _read_json(Path(candidate["asset_plan_path"]).resolve())
        spec_path = Path(candidate["graph_path"]).resolve().parent / "vfxspec.json"
        _write_json(spec_path, _candidate_vfxspec(manifest, candidate, graph, plan))
        candidate["vfxspec_path"] = spec_path.as_posix()
    _validate("prompt_graph_generation_manifest.schema.json", manifest, "Prompt Graph manifest with VFXSpec")
    return _write_json(manifest_path, manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train and run a Prompt-conditioned PrefabGraph profile router.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-dataset")
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--dataset-id", default="prefab_graph_prompt_condition_r001")
    train = commands.add_parser("train")
    train.add_argument("--dataset-root", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--epochs", type=int, default=80)
    generate = commands.add_parser("generate")
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--profile-checkpoint", type=Path, required=True)
    generate.add_argument("--structure-checkpoint", type=Path, required=True)
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--asset-registry", type=Path)
    generate.add_argument("--asset-pair-model", type=Path)
    generate.add_argument("--material-audit", type=Path)
    generate.add_argument("--texture-tags", type=Path)
    generate.add_argument("--mesh-root", type=Path)
    generate.add_argument("--mesh-audit", type=Path)
    generate.add_argument("--candidate-count", type=int, default=1)
    generate.add_argument("--seed", type=int, default=20260902)
    generate.add_argument("--performance-tier", choices=("standard", "mobile"), default="standard")
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--manifest", type=Path, required=True)
    finalize.add_argument("--compile-results-dir", type=Path, required=True)
    finalize.add_argument("--capture-root", type=Path, required=True)
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--manifest", type=Path, action="append", required=True)
    runtime.add_argument("--output", type=Path, required=True)
    runtime.add_argument("--width", type=int, default=512)
    runtime.add_argument("--height", type=int, default=512)
    compile_request = commands.add_parser("prepare-compile")
    compile_request.add_argument("--manifest", type=Path, action="append", required=True)
    compile_request.add_argument("--output", type=Path, required=True)
    compile_request.add_argument("--asset-root", default="Assets/VFXGenerated/PromptGraphDualR001")
    report = commands.add_parser("dual-report")
    report.add_argument("--manifest", type=Path, action="append", required=True)
    report.add_argument("--output", type=Path, required=True)
    specs = commands.add_parser("attach-vfxspec")
    specs.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-dataset":
            paths = build_condition_dataset(args.output_root, args.dataset_id)
        elif args.command == "train":
            paths = train_profile_model(args.dataset_root, args.output_dir, epochs=args.epochs)
        elif args.command == "generate":
            paths = {"manifest": generate_from_prompt(args.prompt, args.profile_checkpoint, args.structure_checkpoint, args.output_root, args.material_audit, args.texture_tags, args.mesh_root, args.mesh_audit, args.candidate_count, args.seed, args.performance_tier, args.asset_registry, args.asset_pair_model)}
        elif args.command == "finalize":
            paths = {"manifest": finalize_generation_manifest(args.manifest, args.compile_results_dir, args.capture_root)}
        elif args.command == "prepare-runtime":
            paths = {"request": build_runtime_request(args.manifest, args.output, args.width, args.height)}
        elif args.command == "prepare-compile":
            paths = {"request": build_compile_request(args.manifest, args.output, args.asset_root)}
        elif args.command == "dual-report":
            paths = {"report": build_dual_family_report(args.manifest, args.output)}
        else:
            paths = {"manifest": attach_vfxspec(args.manifest)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
