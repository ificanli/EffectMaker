"""Prepare and verify constrained, non-training Prompt variation proposals."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from jsonschema import Draft202012Validator


PARENT_CANDIDATE_ID = "prompt_cartoon_blue_energy_impact_001_c004"

VARIANTS = {
    "blue-fast-explosion-ground": {
        "variant_id": "pcv_001_blue_fast_impact_magic_orb_4",
        "material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/magic_orb 4.mat",
        "renderer_role": "ground_minor_layer",
        "start_main_color": [1.6245048, 1.6245048, 1.6245048, 1.0],
        "end_main_color": [0.08, 0.62, 3.2, 1.0],
    },
    "blue-fast-explosion-core": {
        "variant_id": "pcv_005_blue_fast_impact_multi_material_particle",
        "material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_daodan_01.mat",
        "renderer_role": "explosion_core_burst_start_size_6",
        "start_main_color": [48.594265, 24.071533, 16.732931, 1.0],
        "end_main_color": [0.12, 0.9, 5.4, 1.0],
        "particle_color_tracks": [
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_daodan_01.mat", "start_color": [0.06, 0.34, 1.6, 1.0], "end_color": [0.12, 0.84, 5.0, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_Shoulei_Glow_03.mat", "start_color": [0.04, 0.22, 1.2, 1.0], "end_color": [0.08, 0.66, 4.2, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_daodan_02.mat", "start_color": [0.05, 0.26, 1.4, 1.0], "end_color": [0.1, 0.74, 4.6, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/xulie3.mat", "start_color": [0.08, 0.36, 1.8, 1.0], "end_color": [0.14, 0.9, 5.2, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/Mat_27_Glow_01.mat", "start_color": [0.04, 0.22, 1.2, 1.0], "end_color": [0.08, 0.66, 4.2, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/Mat_27_Glow_03.mat", "start_color": [0.04, 0.22, 1.2, 1.0], "end_color": [0.08, 0.66, 4.2, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/magic_orb 4.mat", "start_color": [0.04, 0.22, 1.2, 1.0], "end_color": [0.08, 0.66, 4.2, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_A_aidawang/mat/Mat_aidawang_02.mat", "start_color": [0.04, 0.22, 1.2, 1.0], "end_color": [0.08, 0.66, 4.2, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_shoulei_somke_01.mat", "start_color": [0.04, 0.22, 1.2, 1.0], "end_color": [0.08, 0.66, 4.2, 1.0]},
            {"target_material_path": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_daodan_03.mat", "start_color": [0.04, 0.22, 1.2, 1.0], "end_color": [0.08, 0.66, 4.2, 1.0]},
        ],
        "material_property_targets": [
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_daodan_01.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_Shoulei_Glow_03.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_daodan_02.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/xulie3.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/Mat_27_Glow_01.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/Mat_27_Glow_03.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/__Materials/magic_orb 4.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_A_aidawang/mat/Mat_aidawang_02.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_shoulei_somke_01.mat",
            "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/Effect/daqiang/Mat_daodan_03.mat",
        ],
    },
}


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read_image(path: Path) -> np.ndarray | None:
    try:
        return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        return None


def _blue_fraction(paths: list[Path]) -> tuple[float, float]:
    fractions = []
    for path in paths:
        image = _read_image(path)
        if image is None:
            raise FileNotFoundError(f"could not read variation frame: {path}")
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        corners = np.concatenate((
            image[:8, :8].reshape(-1, 3), image[:8, -8:].reshape(-1, 3),
            image[-8:, :8].reshape(-1, 3), image[-8:, -8:].reshape(-1, 3),
        ))
        background = np.median(corners, axis=0).astype(np.uint8)
        visible = cv2.cvtColor(cv2.absdiff(image, background), cv2.COLOR_BGR2GRAY) > 8
        saturated = hsv[:, :, 1] >= 45
        if not (visible & saturated).any():
            fractions.append(0.0)
            continue
        blue = (hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 132)
        fractions.append(float(blue[visible & saturated].mean()))
    return round(max(fractions, default=0.0), 8), round(sum(fractions) / len(fractions), 8) if fractions else 0.0


def _schema(name: str) -> dict[str, Any]:
    return _read_json(_repo_root() / "workspace/data/vfx_generation/schemas" / name)


def _prefab_material_selection() -> dict[str, dict[str, Any]]:
    path = _repo_root() / "workspace/data/vfx_generation/datasets/prefab_structure_r005c_training_r005/image_feature_examples.jsonl"
    for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()):
        if row["candidate_id"] == "trains_fx_118_fx_aidawang_baozha":
            return {str(item["material_path"]): item for item in row["inputs"]["material_selection"]["materials"]}
    raise ValueError("could not find material selection for the explosion parent Prefab")


def _source_asset(
    parent: dict[str, Any],
    parent_spec: dict[str, Any],
    material_selection: dict[str, Any],
    material_path: str,
) -> dict[str, Any]:
    if material_path == parent_spec["source_asset"]["material_path"]:
        return parent_spec["source_asset"]
    material = material_selection.get(material_path)
    if material is None:
        raise ValueError("variation material is not a direct dependency of the explosion Prefab")
    return {
        "material_path": material_path,
        "material_name": Path(material_path).stem,
        "shader_name": parent_spec["source_asset"]["shader_name"],
        "shader_path": material["primary_shader_path"],
        # The Prefab dataset retains texture slot roles but not a one-to-one Shader
        # property mapping. The live Unity material retains those bindings unchanged.
        "texture_bindings": [],
        "effect_families": [parent["source_prefab"]["effect_family_hint"]],
        "source_categories": parent["source_prefab"]["source_category"],
    }


def prepare_blue_fast_impact_variant(
    composition_root: Path,
    output_root: Path,
    *,
    unity_project: Path = Path("UnityDemo/EffectDemo"),
    execution_project: Path | None = None,
    variant_key: str = "blue-fast-explosion-ground",
) -> dict[str, Path]:
    composition_root, output_root = composition_root.resolve(), output_root.resolve()
    unity_project = unity_project.resolve()
    execution_project = (execution_project or unity_project).resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"variation output already exists and is not empty: {output_root}")
    definition = VARIANTS.get(variant_key)
    if definition is None:
        raise ValueError(f"unsupported variation key: {variant_key}")
    variant_id = str(definition["variant_id"])

    composition = _read_json(composition_root / "composition_manifest.json")
    parent = next((row for row in composition["candidates"] if row["candidate_id"] == PARENT_CANDIDATE_ID), None)
    if parent is None:
        raise ValueError(f"required explosion parent candidate is absent: {PARENT_CANDIDATE_ID}")
    if parent["source_prefab"]["effect_family_hint"] != "explosion":
        raise ValueError("selected parent is not an explosion candidate")
    parent_result = _read_json(composition_root / "candidates" / PARENT_CANDIDATE_ID / "execution_result.json")
    parent_spec_path = Path(parent["material_trajectory"]["spec_path"])
    if not parent_spec_path.is_absolute():
        parent_spec_path = _repo_root() / parent_spec_path
    parent_spec = _read_json(parent_spec_path)
    material_path = str(definition["material_path"])
    material_selection = _prefab_material_selection()
    source_asset = _source_asset(parent, parent_spec, material_selection, material_path)

    base_parameter_tracks = [
        {
            "property_name": "_Distort_Dissolve_Intensity", "semantic": "dissolve", "value_kind": "float",
            "start_value": [0.0], "end_value": [1.0], "curve": "pulse",
            "start_time_seconds": 0.0, "duration_seconds": 0.65, "clamp_min": 0.0, "clamp_max": 1.0,
        },
    ]
    material_property_tracks = [
        {
            "target_material_path": target, "property_name": "_Main_SolidColor", "value_kind": "float",
            "start_value": [0.85], "end_value": [1.0], "curve": "ease_out",
            "start_time_seconds": 0.0, "duration_seconds": 0.12,
        }
        for target in definition.get("material_property_targets", [])
    ] + [
        {
            "target_material_path": target, "property_name": "_Main_Color", "value_kind": "color",
            "start_value": [0.04, 0.22, 1.4, 1.0], "end_value": [0.12, 0.9, 5.4, 1.0], "curve": "ease_out",
            "start_time_seconds": 0.0, "duration_seconds": 0.12,
        }
        for target in definition.get("material_property_targets", [])
    ]
    if not material_property_tracks:
        base_parameter_tracks = [
            {
                "property_name": "_Main_SolidColor", "semantic": "color_tint", "value_kind": "float",
                "start_value": [0.0], "end_value": [1.0], "curve": "ease_out",
                "start_time_seconds": 0.0, "duration_seconds": 0.12, "clamp_min": 0.0, "clamp_max": 1.0,
            },
            {
                "property_name": "_Main_Color", "semantic": "color_tint", "value_kind": "color",
                "start_value": definition["start_main_color"], "end_value": definition["end_main_color"],
                "curve": "ease_out", "start_time_seconds": 0.0, "duration_seconds": 0.12,
                "clamp_min": 0.0, "clamp_max": None,
            },
        ] + base_parameter_tracks
    spec = {
        "schema_version": "material_trajectory_spec.v1",
        "trajectory_id": variant_id,
        "curriculum_id": "prompt_variation_proposal.v1",
        "seed": 2026083101,
        "category": "emission_alpha",
        "label": "positive",
        "source_asset": source_asset,
        "style_profile": {"family": "unknown", "keywords": []},
        "control_scope": "material",
        "duration_seconds": 0.65,
        "parameter_tracks": base_parameter_tracks,
        "particle_color_tracks": ([{
            **track,
            "curve": "ease_out",
            "start_time_seconds": 0.0,
            "duration_seconds": 0.12,
            "disable_color_over_lifetime": True,
        } for track in definition["particle_color_tracks"]] if "particle_color_tracks" in definition else []),
        "material_property_tracks": material_property_tracks,
        "keyword_events": [], "texture_swap_events": [], "material_replace_events": [],
        "expected_signals": ["material_property_changed", "dissolve_parameter_changed"] + (["particle_color_changed"] if "particle_color_tracks" in definition else []) + (["multi_material_property_changed"] if material_property_tracks else []),
        "negative_mutation": None,
        "split_group": {
            "shader_group": parent_spec["split_group"]["shader_group"],
            "material_group": hashlib.sha256(material_path.encode("utf-8")).hexdigest()[:12],
        },
    }
    errors = list(Draft202012Validator(_schema("material_trajectory.schema.json")).iter_errors(spec))
    if errors:
        raise ValueError(f"variation spec schema error: {errors[0].message}")

    output_root.mkdir(parents=True, exist_ok=True)
    spec_path = _write_json(output_root / "specs" / f"{variant_id}.json", spec)
    candidate_root = output_root / "candidates" / variant_id
    request = {
        "schema_version": "effectdemo_material_trajectory_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "execution_mode": "selected",
        "curriculum_root": parent_spec_path.parent.parent.as_posix(),
        "unity_project": unity_project.as_posix(),
        "execution_project": execution_project.as_posix(),
        "width": 512, "height": 512, "target_intervals": 10,
        "run_resource_audit_path": (output_root / "run_resource_audit.json").as_posix(),
        "selection": {"kind": "prompt_variation_proposal", "variant_key": variant_key, "parent_candidate_id": PARENT_CANDIDATE_ID, "count": 1, "trajectory_ids": [variant_id]},
        "requests": [{
            "trajectory_id": variant_id, "candidate_id": variant_id, "prefab_path": parent["source_prefab"]["prefab_path"],
            "spec_path": spec_path.as_posix(), "capture_dir": (candidate_root / "frames").as_posix(),
            "material_timeline_path": (candidate_root / "material_timeline.json").as_posix(),
            "result_path": (candidate_root / "execution_result.json").as_posix(),
            "track_clamps": [{
                "has_min": track.get("clamp_min") is not None,
                "min": float(track.get("clamp_min") or 0.0),
                "has_max": track.get("clamp_max") is not None,
                "max": float(track.get("clamp_max") or 0.0),
            } for track in base_parameter_tracks],
            "has_negative_mutation": False,
        }],
    }
    request_path = _write_json(output_root / "execution_requests.json", request)
    proposal = {
        "schema_version": "prompt_variation_proposal.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "proposal_id": variant_id,
        "parent_composition_manifest": str(composition_root / "composition_manifest.json"),
        "parent_candidate_id": PARENT_CANDIDATE_ID,
        "prompt_condition": composition["prompt_condition"],
        "source_prefab": parent["source_prefab"],
        "material_path": material_path,
        "mutation_plan": {
            "goal": ["blue_color_candidate", "fast_impact_capture_window", "retain_explosion_prefab"],
            "target_renderer_role": definition["renderer_role"],
            "parameter_changes": ["_Main_SolidColor", "_Main_Color", "_Distort_Dissolve_Intensity"] + (["ParticleSystem.Main.startColor", "ParticleSystem.colorOverLifetime.enabled"] if "particle_color_tracks" in definition else []) + (["multi_material._Main_SolidColor", "multi_material._Main_Color"] if material_property_tracks else []),
            "source_texture_or_mesh_replacement": False,
            "training_status": "proposal_only_not_training",
        },
        "execution_request_path": str(request_path),
        "status": "prepared_pending_unity_execution",
    }
    proposal_path = _write_json(output_root / "proposal_manifest.json", proposal)
    return {"spec": spec_path, "execution_requests": request_path, "proposal_manifest": proposal_path}


def finalize_blue_fast_impact_variant(output_root: Path) -> Path:
    output_root = output_root.resolve()
    proposal = _read_json(output_root / "proposal_manifest.json")
    variant_id = str(proposal["proposal_id"])
    result = _read_json(output_root / "candidates" / variant_id / "execution_result.json")
    frame_paths = [output_root / "candidates" / variant_id / "frames" / str(frame["path"]) for frame in result["frames"]]
    if any(not path.is_file() for path in frame_paths):
        raise FileNotFoundError("variation execution is missing frames")
    blue_peak, blue_mean = _blue_fraction(frame_paths)
    resource = result.get("resource_audit") or {}
    technical = result.get("status") == "pass" and int(resource.get("runtime_materials_live", -1)) == 0 and int(resource.get("runtime_textures_live", -1)) == 0
    manifest = {
        "schema_version": "prompt_variation_execution_manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "proposal_manifest": str(output_root / "proposal_manifest.json"),
        "proposal_id": variant_id,
        "parent_candidate_id": PARENT_CANDIDATE_ID,
        "technical_status": "pass" if technical else "fail",
        "frame_count": len(frame_paths),
        "valid_frame_count": int(result["valid_frame_count"]),
        "visual_metrics": {"blue_visible_fraction_peak": blue_peak, "blue_visible_fraction_mean": blue_mean},
        "target_condition_status": {
            "blue": "candidate_signal_present" if blue_peak >= 0.35 else "candidate_signal_weak",
            "fast_impact": "capture_window_under_2_seconds",
            "explosion": "inherited_from_source_prefab_metadata",
            "human_prompt_condition_label": "pending",
        },
        "training_eligibility": {
            "prompt_condition_supervision": False,
            "positive_generation_supervision": False,
            "preference_training": False,
            "reason": "variation is a technical proposal pending independent human Prompt-condition evaluation",
        },
        "execution_result_path": str(output_root / "candidates" / variant_id / "execution_result.json"),
        "status": "technical_pass_pending_human_prompt_review" if technical else "technical_fail",
    }
    return _write_json(output_root / "variant_manifest.json", manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-blue-fast-impact")
    prepare.add_argument("--composition-root", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--unity-project", type=Path, default=Path("UnityDemo/EffectDemo"))
    prepare.add_argument("--execution-project", type=Path)
    prepare.add_argument("--variant", choices=sorted(VARIANTS), default="blue-fast-explosion-ground")
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = prepare_blue_fast_impact_variant(args.composition_root, args.output_root, unity_project=args.unity_project, execution_project=args.execution_project, variant_key=args.variant) if args.command == "prepare-blue-fast-impact" else {"variant_manifest": finalize_blue_fast_impact_variant(args.output_root)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
