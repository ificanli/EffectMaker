"""Grammar-constrained neural ranking for legal PrefabGraph structure candidates."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import torch
from jsonschema import Draft202012Validator

from .prefab_graph import GRAPH_SCHEMA, _read_json, _schema_root, _write_json, assign_graph_id
from .prefab_graph_model import MODEL_VERSION, PAD_TOKEN, UNK_TOKEN, PrefabGraphNextTokenModel


DECODE_SCHEMA = "vfx_prefab_graph_constrained_decode.v1"
TRAINING_SCOPE = "structure_only; no aesthetic or human preference supervision"
PROFILES = ("root_only", "particle_v1", "multi_particle")


def _token(vocabulary: dict[str, int], value: str) -> str:
    if value not in vocabulary:
        raise ValueError(f"required grammar token is absent from model vocabulary: {value}")
    return value


def _node_tokens(vocabulary: dict[str, int], depth: int, sibling: int, component_tokens: list[str], particle: bool, shape: str = "SHAPE_SPHERE", size: str = "SIZE_LOG2_0") -> list[str]:
    values = ["<NODE>", f"DEPTH_{depth}", f"SIBLING_{sibling}", "ACTIVE_1", *component_tokens]
    if particle:
        values.extend([
            "<PARTICLE>", "SIM_LOCAL", "LOOP_0", shape, "RENDER_BILLBOARD",
            "LIFETIME_LOG2_-1", size, "SPEED_LOG2_0", "MATERIALS_0", "</PARTICLE>",
            "<RENDERER>", "TYPE_PARTICLESYSTEMRENDERER", "ENABLED_1", "</RENDERER>",
        ])
    values.append("</NODE>")
    return [_token(vocabulary, value) for value in values]


def valid_templates(vocabulary: dict[str, int], profile: str) -> list[list[str]]:
    """Build a small finite language of structurally legal sequences."""
    prefix = [_token(vocabulary, "<PREFAB>"), _token(vocabulary, "RECON_STRUCTURE_ONLY")]
    close = [_token(vocabulary, "</PREFAB>")]
    root = _node_tokens(vocabulary, 0, 0, [_token(vocabulary, "COMP_TRANSFORM")], False)
    if profile == "root_only":
        return [prefix + root + close]
    if profile == "particle_v1":
        candidates = []
        for shape, size in (("SHAPE_SPHERE", "SIZE_LOG2_0"), ("SHAPE_CIRCLE", "SIZE_LOG2_1"), ("SHAPE_BOX", "SIZE_LOG2_0")):
            child = _node_tokens(vocabulary, 1, 0, [
                _token(vocabulary, "COMP_PARTICLESYSTEM"),
                _token(vocabulary, "COMP_PARTICLESYSTEMRENDERER"),
                _token(vocabulary, "COMP_TRANSFORM"),
            ], True, shape, size)
            candidates.append(prefix + root + child + close)
        return candidates
    if profile == "multi_particle":
        child_variants = [
            ("SHAPE_SPHERE", "SIZE_LOG2_0"),
            ("SHAPE_CIRCLE", "SIZE_LOG2_1"),
            ("SHAPE_BOX", "SIZE_LOG2_0"),
        ]
        children = [_node_tokens(vocabulary, 1, index, [
            _token(vocabulary, "COMP_PARTICLESYSTEM"),
            _token(vocabulary, "COMP_PARTICLESYSTEMRENDERER"),
            _token(vocabulary, "COMP_TRANSFORM"),
        ], True, shape, size) for index, (shape, size) in enumerate(child_variants)]
        return [prefix + root + sum(children, []) + close]
    raise ValueError(f"unsupported constrained decode profile: {profile}")


def validate_token_grammar(tokens: list[str], profile: str) -> list[dict[str, Any]]:
    allowed_events: list[dict[str, Any]] = []
    if not tokens or tokens[0] != "<PREFAB>":
        raise ValueError("grammar requires <PREFAB> as first token")
    state = "after_prefab"
    node_count = 0
    particle_count = 0
    component_count = 0
    for index, token in enumerate(tokens):
        before = state
        if index == 0:
            allowed = ["<PREFAB>"]
            state = "after_prefab"
        elif state == "after_prefab":
            allowed = ["RECON_STRUCTURE_ONLY"]
            if token != allowed[0]: raise ValueError(f"grammar rejected token {token} at {index}")
            state = "need_node"
        elif state == "need_node":
            allowed = ["<NODE>"]
            if token != allowed[0]: raise ValueError(f"grammar rejected token {token} at {index}")
            state = "node_header"
            node_count += 1
        elif state == "node_header":
            allowed = [token] if token.startswith(("DEPTH_", "SIBLING_", "ACTIVE_", "COMP_")) else []
            if not allowed: raise ValueError(f"grammar rejected node header token {token} at {index}")
            if token.startswith("COMP_"):
                component_count += 1
                state = "node_components"
            elif token.startswith("ACTIVE_"):
                state = "node_components"
        elif state == "node_components":
            allowed = [token] if token.startswith(("COMP_", "<PARTICLE>", "<RENDERER>", "</NODE>")) else []
            if not allowed: raise ValueError(f"grammar rejected node component token {token} at {index}")
            if token.startswith("COMP_"): component_count += 1
            if token == "<PARTICLE>": particle_count += 1; state = "particle_body"
            elif token == "<RENDERER>": state = "renderer_body"
            elif token == "</NODE>": state = "after_node"
        elif state == "particle_body":
            allowed = [token] if token == "</PARTICLE>" or token.startswith(("SIM_", "LOOP_", "SHAPE_", "RENDER_", "LIFETIME_", "SIZE_", "SPEED_", "MATERIALS_")) else []
            if not allowed: raise ValueError(f"grammar rejected particle token {token} at {index}")
            if token == "</PARTICLE>": state = "node_components"
        elif state == "renderer_body":
            allowed = [token] if token == "</RENDERER>" or token.startswith(("TYPE_", "ENABLED_")) else []
            if not allowed: raise ValueError(f"grammar rejected renderer token {token} at {index}")
            if token == "</RENDERER>": state = "node_components"
        elif state == "after_node":
            allowed = ["<NODE>", "</PREFAB>"]
            if token == "<NODE>": state = "node_header"; node_count += 1
            elif token == "</PREFAB>": state = "done"
            else: raise ValueError(f"grammar rejected token {token} at {index}")
        elif state == "done":
            raise ValueError(f"grammar has trailing token at {index}: {token}")
        else:
            raise ValueError(f"unknown grammar state: {state}")
        allowed_events.append({"position": index, "token": token, "state_before": before, "allowed_family": allowed})
    if state != "done":
        raise ValueError(f"grammar ended in incomplete state: {state}")
    expected_nodes = {"root_only": 1, "particle_v1": 2, "multi_particle": 4}[profile]
    if node_count != expected_nodes:
        raise ValueError(f"profile {profile} requires {expected_nodes} nodes, got {node_count}")
    if profile == "root_only" and particle_count != 0:
        raise ValueError("root_only cannot contain ParticleSystem blocks")
    if profile == "particle_v1" and particle_count != 1:
        raise ValueError("particle_v1 requires one ParticleSystem block")
    if profile == "multi_particle" and particle_count != 3:
        raise ValueError("multi_particle requires three ParticleSystem blocks")
    return allowed_events


def _score(model: PrefabGraphNextTokenModel, tokens: list[str], vocabulary: dict[str, int]) -> float:
    encoded = [vocabulary.get(token, vocabulary[UNK_TOKEN]) for token in tokens]
    model.eval()
    score = 0.0
    with torch.inference_mode():
        for index in range(1, len(encoded)):
            logits = model(torch.tensor([encoded[:index]], dtype=torch.long))[0, -1]
            score += float(torch.log_softmax(logits, dim=-1)[encoded[index]].item())
    return score


def _bucket_value(token: str, fallback: float) -> float:
    if token == "ZERO": return 0.0
    if "LOG2_" not in token: return fallback
    try: return max(0.01, 2.0 ** int(token.rsplit("_", 1)[-1]))
    except ValueError: return fallback


def tokens_to_graph(tokens: list[str], profile: str, prompt: str, style_family: str, seed: int, source_dataset_id: str = "constrained_decode") -> dict[str, Any]:
    node_tokens: list[list[str]] = []
    cursor = 0
    while cursor < len(tokens):
        if tokens[cursor] != "<NODE>": cursor += 1; continue
        end = tokens.index("</NODE>", cursor)
        node_tokens.append(tokens[cursor:end + 1]); cursor = end + 1
    nodes: list[dict[str, Any]] = []
    particle_components: list[dict[str, Any]] = []
    renderer_components: list[dict[str, Any]] = []
    path_by_index: dict[int, str] = {}
    depth_values: list[int] = []
    sibling_values: list[int] = []
    for index, sequence in enumerate(node_tokens):
        depth = next(int(token.rsplit("_", 1)[-1]) for token in sequence if token.startswith("DEPTH_"))
        sibling = next(int(token.rsplit("_", 1)[-1]) for token in sequence if token.startswith("SIBLING_"))
        active = next(token == "ACTIVE_1" for token in sequence if token.startswith("ACTIVE_"))
        parent_index = next((candidate for candidate in range(index - 1, -1, -1) if depth_values[candidate] == depth - 1), None)
        name = "GeneratedRoot" if depth == 0 else f"GeneratedLayer_{index:02d}"
        path = f"{name}[{sibling}]" if parent_index is None else f"{path_by_index[parent_index]}/{name}[{sibling}]"
        node_id = f"n{index:04d}"
        path_by_index[index] = path
        depth_values.append(depth); sibling_values.append(sibling)
        component_types = [
            "UnityEngine.ParticleSystem" if "COMP_PARTICLESYSTEM" in sequence else None,
            "UnityEngine.ParticleSystemRenderer" if "COMP_PARTICLESYSTEMRENDERER" in sequence else None,
            "UnityEngine.Transform" if "COMP_TRANSFORM" in sequence else None,
        ]
        component_types = [value for value in component_types if value]
        nodes.append({
            "node_id": node_id,
            "name": name,
            "role": "root" if depth == 0 else ("core" if index == 1 else "support" if index == 2 else "hit"),
            "sibling_index": sibling,
            "depth": depth,
            "parent_node_id": None if parent_index is None else f"n{parent_index:04d}",
            "hierarchy_path": path,
            "active_self": active,
            "component_types": component_types,
            "transform": {"local_position": [0.0, 0.0, 0.0], "local_rotation": [0.0, 0.0, 0.0, 1.0], "local_scale": [1.0, 1.0, 1.0]},
        })
        if "COMP_PARTICLESYSTEM" in sequence:
            shape = next((token.rsplit("_", 1)[-1].title() for token in sequence if token.startswith("SHAPE_")), "Sphere")
            lifetime = next((token for token in sequence if token.startswith("LIFETIME_")), "LIFETIME_LOG2_-1")
            size = next((token for token in sequence if token.startswith("SIZE_")), "SIZE_LOG2_0")
            speed = next((token for token in sequence if token.startswith("SPEED_")), "SPEED_LOG2_0")
            component_id = f"p{len(particle_components):04d}"
            particle_components.append({
                "component_id": component_id, "node_id": node_id,
                "parameters": {
                    "serialized_modules": {"profile": "constrained_structure_default"},
                    "duration_seconds": 0.8, "looping": False, "simulation_space": "Local", "max_particles": 64,
                    "start_lifetime_max": _bucket_value(lifetime, 0.5), "start_speed_max": _bucket_value(speed, 1.0), "start_size_max": _bucket_value(size, 1.0),
                    "start_color_rgba": [0.35, 0.75, 1.0, 0.9], "end_color_rgba": [0.05, 0.25, 1.0, 0.0],
                    "emission_enabled": True, "emission_rate_over_time_max": 0.0, "burst_particle_count": 16,
                    "shape_enabled": True, "shape_type": shape, "shape_radius": 0.1,
                    "color_over_lifetime_enabled": True, "size_over_lifetime_enabled": True, "end_size_multiplier": 0.05,
                    "renderer_mode": "Billboard", "sorting_order": 2,
                }, "material_paths": [], "mesh_paths": [],
            })
            renderer_components.append({
                "component_id": f"r{len(renderer_components):04d}", "node_id": node_id,
                "renderer_type": "ParticleSystemRenderer", "enabled": True,
                "parameters": {"particle_render_mode": "Billboard", "sorting_order": 2}, "material_paths": [], "mesh_paths": [],
            })
    graph = {
        "schema_version": GRAPH_SCHEMA,
        "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None},
        "condition": {"prompt": prompt, "effect_family": "unknown", "style_family": style_family, "seed": seed, "parent_prefab_path": None},
        "root_node_id": "n0000", "nodes": nodes,
        "components": {"particle_systems": particle_components, "renderers": renderer_components, "animations": []},
        "asset_bindings": {"materials": [], "meshes": []},
        "reconstruction": {"status": "structure_only", "compiler_profile": "none", "missing_fields": ["asset_plan", "full_particle_curves"], "unsupported_components": []},
        "training": {"eligible_tasks": ["hierarchy_modeling", "component_prediction"], "excluded_tasks": ["aesthetic_preference", "prompt_condition", "full_reconstruction"], "aesthetic_label_source": "ai_hypothesis"},
        "provenance": {"source_dataset_id": source_dataset_id, "source_run_id": None, "exporter": "prefab_graph_constrained.v1", "assumptions": ["Constrained decoder emits a structure-only graph with safe default particle parameters.", "No source or parent Prefab is read."]},
    }
    return assign_graph_id(graph)


def decode(checkpoint_path: Path, output_path: Path, profiles: list[str], prompt: str, style_family: str, seed: int, top_k: int, prefix_tokens: list[str] | None = None) -> Path:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    if payload.get("model_version") != MODEL_VERSION:
        raise ValueError("unsupported PrefabGraph model checkpoint")
    vocabulary = payload.get("vocabulary")
    if not isinstance(vocabulary, dict): raise ValueError("model vocabulary missing")
    model = PrefabGraphNextTokenModel(len(vocabulary), int(payload["config"]["embedding_dim"]), int(payload["config"]["hidden_dim"]), int(payload["config"]["pad_id"]))
    model.load_state_dict(payload["state_dict"])
    all_candidates: list[dict[str, Any]] = []
    prefix_tokens = prefix_tokens or []
    for token in prefix_tokens:
        _token(vocabulary, token)
    for profile in profiles:
        templates = valid_templates(vocabulary, profile)
        if prefix_tokens:
            templates = [template for template in templates if template[:len(prefix_tokens)] == prefix_tokens]
            if not templates:
                raise ValueError(f"prefix is not a valid prefix for profile {profile}: {prefix_tokens}")
        scored = []
        for tokens in templates:
            events = validate_token_grammar(tokens, profile)
            scored.append((
                _score(model, tokens, vocabulary),
                tokens,
                events,
            ))
        scored.sort(key=lambda value: value[0], reverse=True)
        for score, tokens, events in scored[:max(1, top_k)]:
            graph = tokens_to_graph(tokens, profile, prompt, style_family, seed, "constrained_decode")
            _validate_graph(graph)
            all_candidates.append({
                "candidate_id": graph["graph_id"], "profile": profile, "score": score, "tokens": tokens, "graph": graph,
                "grammar": {"valid": True, "masked_invalid_token_count": max(1, len(vocabulary) - 1), "selection_mode": "neural_ranked_valid_templates", "mask_events": events},
                "training_scope": TRAINING_SCOPE,
            })
    all_candidates.sort(key=lambda value: value["score"], reverse=True)
    result = {
        "schema_version": DECODE_SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION, "checkpoint_path": checkpoint_path.resolve().as_posix(),
        "profiles": profiles, "candidate_count": len(all_candidates), "candidates": all_candidates, "status": "pass",
    }
    validator = Draft202012Validator(_read_json(_schema_root() / "prefab_graph_constrained_decode.schema.json"))
    errors = list(validator.iter_errors(result))
    if errors: raise ValueError(f"constrained decode schema error: {errors[0].message}")
    return _write_json(output_path.resolve(), result)


def _validate_graph(graph: dict[str, Any]) -> None:
    validator = Draft202012Validator(_read_json(_schema_root() / "prefab_graph.schema.json"))
    errors = list(validator.iter_errors(graph))
    if errors: raise ValueError(f"decoded graph schema error: {errors[0].message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decode legal PrefabGraph candidates with neural model ranking.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, action="append", dest="profiles")
    parser.add_argument("--prompt", default="卡通蓝色能量冲击，快速爆发，不要长拖尾")
    parser.add_argument("--style-family", default="cartoon")
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--prefix-token", action="append", dest="prefix_tokens", default=[])
    args = parser.parse_args(argv)
    try:
        profiles = args.profiles or list(PROFILES)
        path = decode(args.checkpoint, args.output, profiles, args.prompt, args.style_family, args.seed, args.top_k, args.prefix_tokens)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "output": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
