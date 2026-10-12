"""Build and verify a controlled Unity reproduction for one professional VFX rule."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .prefab_graph import assign_graph_id


SCHEMA_VERSION = "vfx_professional_teacher_reproduction.v1"
RULE_ID = "professional_explosion_core_readability_r001"
SHARED_CAPTURE_SEED_ID = "professional_explosion_core_pair_r001"
CORE_MATERIAL_TEMPLATE = "Assets/QFX/ProjectilesFX/VFX_Resources/Materials/Nature/MFX_Flare_4.mat"
CORE_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Glow/FX_Glow_1.TGA"


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    path.write_text(payload, encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _core_particle(graph: dict[str, Any]) -> dict[str, Any]:
    role_by_node = {str(node["node_id"]): str(node.get("role") or "") for node in graph.get("nodes") or []}
    values = [row for row in (graph.get("components") or {}).get("particle_systems") or [] if role_by_node.get(str(row.get("node_id"))) == "core"]
    if len(values) != 1:
        raise ValueError(f"exactly one core ParticleSystem expected, found {len(values)}")
    return values[0]


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = json.loads(json.dumps(source, ensure_ascii=False))
    graph.pop("graph_id", None)
    core = _core_particle(graph)
    parameters = core["parameters"]
    color = [1.0, 1.0, 1.0, 1.0]
    if variant == "empty_core":
        color[3] = 0.0
    elif variant == "reinforced_core":
        color[3] = 0.95
    else:
        raise ValueError(f"unsupported reproduction variant: {variant}")
    parameters["start_color_rgba"] = color
    parameters.update({
        "end_color_rgba": [1.0, 1.0, 1.0, 0.0],
        "color_over_lifetime_enabled": True,
        "burst_particle_count": 1,
        "emission_rate_over_time_max": 0.0,
        "start_size_max": 0.9,
        "start_speed_max": 0.0,
        "shape_radius": 0.0,
        "end_size_multiplier": 1.5,
        "sorting_order": 10,
        "material_template_path": CORE_MATERIAL_TEMPLATE,
        "texture_asset_path": CORE_TEXTURE,
        "texture_property_name": "_MainTex",
    })
    for renderer in (graph.get("components") or {}).get("renderers") or []:
        if str(renderer.get("node_id")) == str(core.get("node_id")):
            renderer.setdefault("parameters", {})["sorting_order"] = 10
    parameters["serialized_modules"] = {
        **(parameters.get("serialized_modules") or {}),
        "professional_rule_id": RULE_ID,
        "controlled_variable": "core_start_color_alpha",
    }
    graph["condition"] = {
        "prompt": "专业爆炸核心可读性对照实验",
        "effect_family": "explosion",
        "style_family": str((graph.get("condition") or {}).get("style_family") or "cartoon"),
        "seed": 20261003,
        "parent_prefab_path": None,
    }
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {
        "source_dataset_id": "professional_teacher_reproduction_r001",
        "source_run_id": RULE_ID,
        "exporter": "professional_teacher_reproduction.v1",
        "assumptions": [
            "The two variants share structure, Support/Hit parameters, Material, Shader, Texture, timing and capture seed.",
            "Only the Core ParticleSystem start alpha differs between variants.",
            "The experiment validates the measurable center-occupancy consequence, not universal aesthetic superiority.",
        ],
    }
    return assign_graph_id(graph)


def prepare(source_graph: Path, output_root: Path, asset_root: str = "Assets/Generated/ProfessionalTeacherExplosionCoreR001") -> dict[str, Path]:
    source_graph = source_graph.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional reproduction output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants = []
    compile_requests = []
    for variant in ("empty_core", "reinforced_core"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        result_path = output_root / "compile_results" / f"{variant}.json"
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        readback_graph_path = output_root / "readback" / f"{variant}.json"
        readback_result_path = output_root / "readback_results" / f"{variant}.json"
        variants.append({
            "variant": variant,
            "graph_id": graph["graph_id"],
            "graph_path": _portable(graph_path),
            "output_prefab_path": output_prefab,
            "compile_result_path": _portable(result_path),
            "readback_graph_path": _portable(readback_graph_path),
            "readback_result_path": _portable(readback_result_path),
        })
        compile_requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": result_path.resolve().as_posix()})
    experiment = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "source_graph_path": _portable(source_graph),
        "professional_source": {
            "source_id": "SRC-2026-001",
            "title": "20260415点评-一定要练基本功",
            "author": "三生路_王先生特效",
            "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md: 作者页面说明为网易资深特效师",
            "source_url": "https://www.bilibili.com/video/BV1xmQnBaE6b/",
            "license_scope": "internal_learning_only_no_redistribution",
            "timecodes": ["00:09:29-00:12:07"],
            "frame_paths": [
                "knowledge/sources/SRC-2026-001/visual_check/03_explosion_core/09m29.00s.jpg",
                "knowledge/sources/SRC-2026-001/visual_check/03_explosion_core/09m41.00s.jpg",
                "knowledge/sources/SRC-2026-001/visual_check/03_explosion_core/10m30.00s.jpg",
                "knowledge/sources/SRC-2026-001/visual_check/03_explosion_core/11m30.00s.jpg"
            ],
            "expert_judgment": "爆炸需要核心体积与外扩元素；外围细节不能替代核心，中心空会削弱主体体积和力量感。",
            "judgment_axes": ["core_readability", "layer_separation", "composition"],
        },
        "controlled_variables": {"changed": ["core.start_color_rgba.alpha"], "held_constant": ["graph topology", "shared core reproduction profile", "support parameters", "hit parameters", "material paths", "texture paths", "shader paths", "timing", "capture seed"]},
        "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID,
        "variants": variants,
        "status": "prepared",
    }
    experiment_path = _write(output_root / "experiment_manifest.json", experiment)
    compile_path = _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": compile_requests})
    return {"experiment": experiment_path, "compile_request": compile_path}


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment_path = experiment_path.resolve()
    experiment = _read(experiment_path)
    requests = []
    capture_root = output_path.resolve().parent / "runtime_captures"
    for variant in experiment["variants"]:
        compile_result = _read(_repo_root() / variant["compile_result_path"])
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        case_root = capture_root / variant["variant"]
        requests.append({
            "candidate_id": experiment["shared_capture_seed_id"],
            "prefab_path": compile_result["output_prefab_path"],
            "capture_dir": (case_root / "captures").as_posix(),
            "capture_manifest_path": (case_root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (case_root / "material_timeline.json").as_posix(),
            "source_script_fidelity": "generated_graph_no_source_scripts",
            "ignored_script_dependency_count": 0,
            "missing_script_count": 0,
            "capture_category": "explosion",
        })
    return _write(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_path.resolve().parent.name,
        "scene": "ProfessionalTeacherExplosionCore",
        "camera": "ProfessionalTeacherExplosionCoreCamera",
        "width": 640,
        "height": 360,
        "sampling_mode": "adaptive_runtime",
        "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.05, "max_duration_seconds": 2.0, "include_zero": True, "duration_sources": ["particle_system"]},
        "capture_material_timeline": True,
        "requests": requests,
    })


def _frame_metrics(path: Path) -> dict[str, float]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    corners = np.concatenate((rgb[:5, :5].reshape(-1, 3), rgb[:5, -5:].reshape(-1, 3), rgb[-5:, :5].reshape(-1, 3), rgb[-5:, -5:].reshape(-1, 3)))
    background = np.median(corners, axis=0)
    visible = np.max(np.abs(rgb - background), axis=2) > 8
    height, width = visible.shape
    half = max(4, int(min(width, height) * 0.1))
    center_slice = (slice(height // 2 - half, height // 2 + half), slice(width // 2 - half, width // 2 + half))
    center = visible[center_slice]
    luma = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]) / 255.0
    center_luma = luma[center_slice]
    outer_half = max(half + 2, int(min(width, height) * 0.18))
    outer_slice = (slice(height // 2 - outer_half, height // 2 + outer_half), slice(width // 2 - outer_half, width // 2 + outer_half))
    outer_luma = luma[outer_slice]
    ring_mask = np.ones(outer_luma.shape, dtype=bool)
    offset = outer_half - half
    ring_mask[offset:offset + center_luma.shape[0], offset:offset + center_luma.shape[1]] = False
    ring_luminance = float(outer_luma[ring_mask].mean()) if ring_mask.any() else float(background.mean() / 255.0)
    center_luminance = float(center_luma.mean())
    return {
        "visible_area_ratio": float(visible.mean()),
        "center_occupancy_ratio": float(center.mean()),
        "center_visible_share": float(center.sum() / max(1, visible.sum())),
        "center_luminance": center_luminance,
        "center_local_contrast": center_luminance - ring_luminance,
    }


def _capture_summary(path: Path) -> dict[str, Any]:
    manifest = _read(path)
    capture_root = Path(str(manifest["capture_root"])).resolve()
    frames = []
    for frame in manifest.get("frames") or []:
        if not frame.get("valid") or not frame.get("path"):
            continue
        frame_path = capture_root / str(frame["path"])
        metrics = _frame_metrics(frame_path)
        frames.append({"path": _portable(frame_path), "time_seconds": float(frame.get("requested_time_seconds") or 0.0), **metrics})
    peak = max(frames, key=lambda row: (row["center_occupancy_ratio"], row["visible_area_ratio"])) if frames else None
    return {
        "manifest_path": _portable(path),
        "visual_evidence_status": manifest.get("visual_evidence_status"),
        "image_sequence_training_eligible": bool(manifest.get("image_sequence_training_eligible")),
        "full_visual_training_eligible": bool(manifest.get("full_visual_training_eligible")),
        "material_render_error_frame_count": int(manifest.get("material_render_error_frame_count") or 0),
        "selected_camera_view": (manifest.get("camera_selection") or {}).get("selected_view"),
        "valid_frame_count": int(manifest.get("valid_frame_count") or 0),
        "frames": frames,
        "peak_center_occupancy_ratio": 0.0 if peak is None else peak["center_occupancy_ratio"],
        "peak_center_visible_share": 0.0 if peak is None else peak["center_visible_share"],
        "peak_center_luminance": 0.0 if not frames else max(row["center_luminance"] for row in frames),
        "peak_center_local_contrast": 0.0 if not frames else max(row["center_local_contrast"] for row in frames),
        "peak_frame_path": None if peak is None else peak["path"],
        "peak_time_seconds": None if peak is None else peak["time_seconds"],
    }


def _paired_frame_comparison(empty: dict[str, Any], reinforced: dict[str, Any]) -> dict[str, Any]:
    empty_by_time = {round(float(row["time_seconds"]), 6): row for row in empty["frames"]}
    reinforced_by_time = {round(float(row["time_seconds"]), 6): row for row in reinforced["frames"]}
    pairs = []
    for time_seconds in sorted(set(empty_by_time) & set(reinforced_by_time)):
        empty_frame = empty_by_time[time_seconds]
        reinforced_frame = reinforced_by_time[time_seconds]
        pairs.append({
            "time_seconds": time_seconds,
            "empty_frame_path": empty_frame["path"],
            "reinforced_frame_path": reinforced_frame["path"],
            "center_luminance_gain": reinforced_frame["center_luminance"] - empty_frame["center_luminance"],
            "center_local_contrast_gain": reinforced_frame["center_local_contrast"] - empty_frame["center_local_contrast"],
            "center_occupancy_gain": reinforced_frame["center_occupancy_ratio"] - empty_frame["center_occupancy_ratio"],
        })
    best = max(pairs, key=lambda row: (row["center_luminance_gain"], row["center_local_contrast_gain"])) if pairs else None
    return {
        "matched_frame_count": len(pairs),
        "best_time_seconds": None if best is None else best["time_seconds"],
        "peak_center_luminance_gain": 0.0 if best is None else best["center_luminance_gain"],
        "peak_center_local_contrast_gain": 0.0 if best is None else best["center_local_contrast_gain"],
        "best_empty_frame_path": None if best is None else best["empty_frame_path"],
        "best_reinforced_frame_path": None if best is None else best["reinforced_frame_path"],
        "pairs": pairs,
    }


def _difference_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if type(left) is not type(right):
        return [prefix or "<root>"]
    if isinstance(left, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(_difference_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list):
        paths = []
        if len(left) != len(right):
            paths.append(f"{prefix}.length")
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            paths.extend(_difference_paths(left_item, right_item, f"{prefix}[{index}]"))
        return paths
    return [] if left == right else [prefix or "<root>"]


def _controlled_graph_comparison(empty_graph: dict[str, Any], reinforced_graph: dict[str, Any]) -> dict[str, Any]:
    empty = json.loads(json.dumps(empty_graph, ensure_ascii=False))
    reinforced = json.loads(json.dumps(reinforced_graph, ensure_ascii=False))
    empty.pop("graph_id", None)
    reinforced.pop("graph_id", None)
    paths = _difference_paths(empty, reinforced)

    core = _core_particle(empty)
    particle_systems = (empty.get("components") or {}).get("particle_systems") or []
    core_index = next(index for index, row in enumerate(particle_systems) if row is core)
    expected_path = f"components.particle_systems[{core_index}].parameters.start_color_rgba[3]"
    return {
        "difference_paths": paths,
        "expected_difference_path": expected_path,
        "only_core_alpha_differs": paths == [expected_path],
    }


def _compile_summary(experiment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        summaries[variant["variant"]] = {
            "result_path": variant["compile_result_path"],
            "status": result.get("status"),
            "output_prefab_path": result.get("output_prefab_path"),
            "planned_texture_readback_match": bool(result.get("planned_texture_readback_match")),
            "material_texture_readback_count": len(result.get("material_texture_readbacks") or []),
        }
    return summaries


def _readback_summary(experiment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for variant in experiment["variants"]:
        result_path = _repo_root() / variant["readback_result_path"]
        result = _read(result_path)
        summaries[variant["variant"]] = {
            "result_path": variant["readback_result_path"],
            "status": result.get("status"),
            "output_graph_path": result.get("output_graph_path"),
            "prefab_path": result.get("prefab_path"),
        }
    return summaries


def finalize(experiment_path: Path, output_path: Path) -> dict[str, Path]:
    experiment_path = experiment_path.resolve()
    experiment = _read(experiment_path)
    graphs = {
        variant["variant"]: _read(_repo_root() / variant["graph_path"])
        for variant in experiment["variants"]
    }
    graph_comparison = _controlled_graph_comparison(graphs["empty_core"], graphs["reinforced_core"])
    compile_summaries = _compile_summary(experiment)
    readback_summaries = _readback_summary(experiment)
    runtime_root = experiment_path.parent / "runtime_captures"
    summaries = {variant: _capture_summary(runtime_root / variant / "capture_manifest.json") for variant in ("empty_core", "reinforced_core")}
    empty = summaries["empty_core"]
    reinforced = summaries["reinforced_core"]
    paired_comparison = _paired_frame_comparison(empty, reinforced)
    center_gain = reinforced["peak_center_occupancy_ratio"] - empty["peak_center_occupancy_ratio"]
    share_gain = reinforced["peak_center_visible_share"] - empty["peak_center_visible_share"]
    gates = {
        "controlled_graph_difference_only_core_alpha": graph_comparison["only_core_alpha_differs"],
        "both_compile_pass": all(row["status"] == "pass" for row in compile_summaries.values()),
        "both_texture_readbacks_match_plan": all(row["planned_texture_readback_match"] for row in compile_summaries.values()),
        "both_prefab_api_readbacks_pass": all(row["status"] == "pass" for row in readback_summaries.values()),
        "both_runtime_eligible": all(row["image_sequence_training_eligible"] for row in summaries.values()),
        "no_material_render_errors": all(row["material_render_error_frame_count"] == 0 for row in summaries.values()),
        "same_camera_view": bool(empty["selected_camera_view"]) and empty["selected_camera_view"] == reinforced["selected_camera_view"],
        "equal_nonzero_frame_count": empty["valid_frame_count"] > 0 and empty["valid_frame_count"] == reinforced["valid_frame_count"],
        "all_frames_matched_by_time": paired_comparison["matched_frame_count"] == empty["valid_frame_count"],
        "reinforced_core_luminance_gain": paired_comparison["peak_center_luminance_gain"] >= 0.03,
        "reinforced_core_local_contrast_gain": paired_comparison["peak_center_local_contrast_gain"] >= 0.02,
    }
    verified = all(gates.values())
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": experiment["rule_id"],
        "professional_source": experiment["professional_source"],
        "controlled_variables": experiment["controlled_variables"],
        "experiment_manifest_path": _portable(experiment_path),
        "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"},
        "graph_comparison": graph_comparison,
        "compile_results": compile_summaries,
        "prefab_api_readbacks": readback_summaries,
        "variants": summaries,
        "comparison": {
            "center_occupancy_gain": center_gain,
            "center_visible_share_gain": share_gain,
            **paired_comparison,
        },
        "validated_controller_prior": {
            "status": "eligible" if verified else "blocked",
            "effect_family": "explosion",
            "target_role": "core",
            "judgment_axis": "core_readability",
            "reference_graph_path": next(
                variant["graph_path"] for variant in experiment["variants"] if variant["variant"] == "reinforced_core"
            ),
            "minimum_center_luminance_gain": 0.03,
            "minimum_center_local_contrast_gain": 0.02,
            "allowed_use": "explosion_core_rule_controller_only" if verified else "knowledge_prior_only",
        },
        "quality_gates": gates,
        "conclusion": "Unity reproduction supports the professional rule that an explicit Core layer measurably fills the explosion center while Support and Hit are held constant." if verified else "Unity reproduction did not meet the controlled center-readability gates; keep the rule as a knowledge prior only.",
        "status": "verified" if verified else "blocked",
    }
    report_path = _write(output_path.resolve(), report)
    teacher_index_root = output_path.resolve().parent / "teacher_index"
    record = {
        "schema_version": "course_knowledge_record.v1",
        "record_id": RULE_ID,
        "source_path": "knowledge/sources/SRC-2026-001/visual_review_front.md",
        "heading": "爆炸中心与爆炸层次",
        "line_start": 30,
        "line_end": 38,
        "excerpt": experiment["professional_source"]["expert_judgment"],
        "record_type": "tutorial_fact",
        "status": "verified" if verified else "pending",
        "effect_family": "explosion",
        "evidence_level": "high" if verified else "medium",
        "timecodes": experiment["professional_source"]["timecodes"],
        "frame_paths": [*experiment["professional_source"]["frame_paths"], *[row["peak_frame_path"] for row in summaries.values() if row["peak_frame_path"]]],
        "judgment_axes": experiment["professional_source"]["judgment_axes"],
        "source_expertise_status": "verified_professional",
        "unity_reproduction_status": "verified" if verified else "blocked",
        "unity_reproduction_report": _portable(report_path),
        "eligible_for_vfxspec_prior": verified,
        "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "reason": "Teacher rule may supervise Judge rule axis only; it is not a generated-Prefab quality label."},
    }
    records_path = _write_jsonl(teacher_index_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_index_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_explosion_core_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "unverified_assumption_is_not_vfxspec_prior": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a controlled professional VFX rule reproduction.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("--source-graph", type=Path, required=True)
    prepare_command.add_argument("--output-root", type=Path, required=True)
    prepare_command.add_argument("--asset-root", default="Assets/Generated/ProfessionalTeacherExplosionCoreR001")
    runtime_command = commands.add_parser("prepare-runtime")
    runtime_command.add_argument("--experiment", type=Path, required=True)
    runtime_command.add_argument("--output", type=Path, required=True)
    finalize_command = commands.add_parser("finalize")
    finalize_command.add_argument("--experiment", type=Path, required=True)
    finalize_command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            paths = prepare(args.source_graph, args.output_root, args.asset_root)
        elif args.command == "prepare-runtime":
            paths = {"runtime_request": prepare_runtime(args.experiment, args.output)}
        else:
            paths = finalize(args.experiment, args.output)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
