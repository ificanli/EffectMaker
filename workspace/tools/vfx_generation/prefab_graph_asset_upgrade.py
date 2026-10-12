"""Upgrade constrained structure candidates with an auditable technical asset plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .prefab_graph import _read_json, _schema_root, _write_json, assign_graph_id


UPGRADE_SCHEMA = "vfx_prefab_graph_asset_upgrade.v1"
ASSET_PLAN_SCHEMA = "vfx_prefab_asset_plan.v1"
TEMPLATE_PATH = "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_S_fozu/mat/Mat_fozu_03.mat"


def _validate(schema_name: str, value: dict[str, Any], label: str) -> None:
    schema = _read_json(_schema_root() / schema_name)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _asset_sha256(repo_root: Path, asset_path: str) -> str:
    path = repo_root / "UnityDemo/EffectDemo" / Path(asset_path)
    if not path.is_file():
        raise FileNotFoundError(f"audited material template is missing: {asset_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _asset_guid(repo_root: Path, asset_path: str) -> str | None:
    meta = repo_root / "UnityDemo/EffectDemo" / Path(asset_path + ".meta")
    if not meta.is_file():
        return None
    match = re.search(r"^guid:\s*([0-9a-f]{32})\s*$", meta.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def _upgrade_graph(source: dict[str, Any], profile: str, prompt: str, effect_family: str, style_family: str, seed: int, repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = json.loads(json.dumps(source, ensure_ascii=False))
    graph["condition"] = {
        "prompt": prompt,
        "effect_family": effect_family,
        "style_family": style_family,
        "seed": seed,
        "parent_prefab_path": None,
    }
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["reconstruction"] = {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []}
    graph["training"] = {
        "eligible_tasks": ["component_prediction", "full_reconstruction", "hierarchy_modeling", "particle_parameter_modeling"],
        "excluded_tasks": ["aesthetic_preference", "prompt_condition"],
        "aesthetic_label_source": "ai_hypothesis",
    }
    template_sha256 = _asset_sha256(repo_root, TEMPLATE_PATH)
    template_guid = _asset_guid(repo_root, TEMPLATE_PATH)
    texture_profiles: list[str] = []
    for index, particle in enumerate(graph["components"].get("particle_systems") or []):
        parameters = particle.setdefault("parameters", {})
        texture_profile = "spark" if index == len(graph["components"]["particle_systems"]) - 1 else "soft_disc"
        parameters["texture_profile"] = texture_profile
        parameters["material_template_path"] = TEMPLATE_PATH
        parameters["serialized_modules"] = {"profile": "asset_upgraded_particle_v1"}
        texture_profiles.append(texture_profile)
    graph["provenance"] = {
        "source_dataset_id": "constrained_decode_asset_upgrade",
        "source_run_id": None,
        "exporter": "prefab_graph_constrained.v1",
        "assumptions": [
            "The structure came from a Grammar-constrained neural decode.",
            "Material template selection is technical routing evidence, not aesthetic acceptance.",
            "Texture assets are generated deterministically by the Unity compiler after this plan.",
        ],
    }
    graph = assign_graph_id(graph)
    _validate("prefab_graph.schema.json", graph, f"upgraded Graph {graph['graph_id']}")
    assets: list[dict[str, Any]] = []
    if graph["components"].get("particle_systems"):
        assets.append({
            "asset_role": "material_template",
            "selection_mode": "audited_local_template",
            "path": TEMPLATE_PATH,
            "shader_name": "Common/ColorDefault",
            "texture_profile": None,
            "asset_id": template_guid,
            "sha256": template_sha256,
            "authorization_status": "local_source_unconfirmed",
            "selection_basis": ["Unity material binding audit", "explicit SrcAlpha/OneMinusSrcAlpha/ZWriteOff configuration", "material is present in EffectDemo 2022"],
        })
        for texture_profile in sorted(set(texture_profiles)):
            assets.append({
                "asset_role": "generated_texture",
                "selection_mode": "deterministic_generated",
                "path": None,
                "shader_name": None,
                "texture_profile": texture_profile,
                "asset_id": None,
                "sha256": None,
                "authorization_status": "generated",
                "selection_basis": [f"deterministic Texture2D profile: {texture_profile}", "generated inside Unity compiler after asset-plan validation"],
            })
    plan = {
        "schema_version": ASSET_PLAN_SCHEMA,
        "plan_id": f"asset_plan_{graph['graph_id']}",
        "candidate_id": graph["graph_id"],
        "parent_prefab_path": None,
        "assets": assets,
        "selection_basis": ["No parent Prefab is read.", "Audited material template is cloned into a new output material.", "Generated textures are not source assets and are created by the compiler."],
        "training_scope": "technical_asset_routing; no aesthetic or human preference supervision",
        "status": "pass",
    }
    _validate("prefab_asset_plan.schema.json", plan, f"asset plan {plan['plan_id']}")
    return graph, plan


def upgrade_decode(decode_path: Path, output_root: Path, prompt: str, effect_family: str, style_family: str, seed: int) -> Path:
    decode_path = decode_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"asset upgrade output already exists and is not empty: {output_root}")
    source = _read_json(decode_path)
    if source.get("schema_version") != "vfx_prefab_graph_constrained_decode.v1" or source.get("status") != "pass":
        raise ValueError(f"verified constrained decode expected: {decode_path}")
    repo_root = Path(__file__).parents[3].resolve()
    candidates = []
    for candidate in source.get("candidates") or []:
        profile = str(candidate.get("profile") or "")
        graph, plan = _upgrade_graph(candidate["graph"], profile, prompt, effect_family, style_family, seed, repo_root)
        graph_path = output_root / "graphs" / f"{graph['graph_id']}.json"
        plan_path = output_root / "asset_plans" / f"{plan['plan_id']}.json"
        _write_json(graph_path, graph)
        _write_json(plan_path, plan)
        candidates.append({
            "candidate_id": graph["graph_id"],
            "profile": profile,
            "graph_path": str(graph_path.relative_to(repo_root)).replace("\\", "/"),
            "asset_plan_path": str(plan_path.relative_to(repo_root)).replace("\\", "/"),
            "graph_status": graph["reconstruction"]["status"],
            "parent_prefab_path": graph["condition"]["parent_prefab_path"],
        })
    result = {
        "schema_version": UPGRADE_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_decode_path": str(decode_path.relative_to(repo_root)).replace("\\", "/"),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "status": "pass",
    }
    _validate("prefab_graph_asset_upgrade.schema.json", result, "asset upgrade")
    return _write_json(output_root / "upgrade_manifest.json", result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upgrade constrained PrefabGraph candidates with technical asset plans.")
    parser.add_argument("--decode", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--prompt", default="卡通蓝色能量冲击，快速爆发，不要长拖尾")
    parser.add_argument("--effect-family", default="explosion")
    parser.add_argument("--style-family", default="cartoon")
    parser.add_argument("--seed", type=int, default=20260901)
    args = parser.parse_args(argv)
    try:
        path = upgrade_decode(args.decode, args.output_root, args.prompt, args.effect_family, args.style_family, args.seed)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "manifest": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
