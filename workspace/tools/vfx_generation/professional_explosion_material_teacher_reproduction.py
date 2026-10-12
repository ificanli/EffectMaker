"""Build a controlled Unity reproduction for structured explosion-core texture."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .explosion_family_generator import CORE_MATERIAL
from .prefab_graph import assign_graph_id
from .professional_teacher_guided_generation import _single_role_component, _validate_graph
from .professional_teacher_reproduction import _capture_summary, _difference_paths, _portable, _read, _repo_root, _write, _write_jsonl


SCHEMA_VERSION = "vfx_professional_explosion_material_teacher_reproduction.v1"
RULE_ID = "professional_explosion_core_texture_structure_r001"
SHARED_CAPTURE_SEED_ID = "professional_explosion_material_pair_r001"
FLAT_TEXTURE = "Assets/QFX/ProjectilesFX/VFX_Resources/Textures/Glow/FX_Glow_1.TGA"
STRUCTURED_TEXTURE = "Assets/VFXSourceIngest/Shared/Textures/0e/Tex_xingzhe_fire3_0e15be311470531b.png"


def _variant(source: dict[str, Any], variant: str) -> dict[str, Any]:
    graph = copy.deepcopy(source)
    graph.pop("graph_id", None)
    for node in graph.get("nodes") or []:
        if node.get("role") in {"support", "hit", "residual"}:
            node["active_self"] = False
    core = _single_role_component(graph, "particle_systems", "core")
    parameters = core["parameters"]
    parameters["material_template_path"] = CORE_MATERIAL
    if variant == "flat_glow":
        parameters["texture_asset_path"] = FLAT_TEXTURE
    elif variant == "structured_flame":
        parameters["texture_asset_path"] = STRUCTURED_TEXTURE
    else:
        raise ValueError(f"unsupported material reproduction variant: {variant}")
    graph["condition"] = {"prompt": "专业爆炸核心材质结构对照实验", "effect_family": "explosion", "style_family": "cartoon", "seed": 20261313, "parent_prefab_path": None}
    graph["source"] = {"source_kind": "generated", "prefab_path": None, "source_example_id": None}
    graph["provenance"] = {
        "source_dataset_id": "professional_explosion_material_teacher_r001",
        "source_run_id": RULE_ID,
        "exporter": "prefab_graph_constrained.v1",
        "assumptions": ["Support, Hit and Residual are disabled in both variants.", "Only the Core texture differs.", "The experiment validates texture structure and readable core luminance, not global aesthetic quality."],
    }
    graph = assign_graph_id(graph)
    _validate_graph(graph)
    return graph


def _controlled_graph_comparison(flat: dict[str, Any], structured: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(flat), copy.deepcopy(structured)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    particles = (left.get("components") or {}).get("particle_systems") or []
    core = _single_role_component(left, "particle_systems", "core")
    core_index = next(index for index, row in enumerate(particles) if row is core)
    expected = f"components.particle_systems[{core_index}].parameters.texture_asset_path"
    return {"difference_paths": paths, "expected_difference_path": expected, "only_core_texture_differs": paths == [expected]}


def prepare(source_graph: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    source_graph, output_root = source_graph.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"professional material output already exists and is not empty: {output_root}")
    source = _read(source_graph)
    variants, requests = [], []
    for variant in ("flat_glow", "structured_flame"):
        graph = _variant(source, variant)
        graph_path = _write(output_root / "graphs" / f"{variant}.json", graph)
        output_prefab = f"{asset_root.rstrip('/')}/{variant}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{variant}.json"
        readback_graph = output_root / "readback" / f"{variant}.json"
        readback_result = output_root / "readback_results" / f"{variant}.json"
        variants.append({"variant": variant, "graph_id": graph["graph_id"], "graph_path": _portable(graph_path), "output_prefab_path": output_prefab, "compile_result_path": _portable(compile_result), "readback_graph_path": _portable(readback_graph), "readback_result_path": _portable(readback_result)})
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
    experiment_path = _write(output_root / "experiment_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "source_graph_path": _portable(source_graph),
        "professional_source": {
            "source_id": "SRC-2026-SERIES-001-EP007",
            "title": "第07集作业点评：火焰核心、边缘和暗部",
            "author": "三生路_王先生特效",
            "author_expertise_evidence": "knowledge/sources/SRC-2026-001/source.md: 作者页面说明为网易资深特效师",
            "license_scope": "internal_learning_only_no_redistribution",
            "timecodes": ["01:01:14-01:09:43", "01:41:37-01:45:20"],
            "frame_paths": [
                "knowledge/sources/SRC-2026-SERIES-001/ep007/visual_check/07_fire_layers/01_03660.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep007/visual_check/07_fire_layers/02_03838.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep007/visual_check/11_fire_shape/02_06237.jpg",
                "knowledge/sources/SRC-2026-SERIES-001/ep007/visual_check/11_fire_shape/03_06534.jpg",
            ],
            "expert_judgment": "火焰不能只是一整块高亮贴片；应保留中心高亮、外部暗色、可识别轮廓和软边结构。",
            "judgment_axes": ["material", "core_readability", "composition"],
        },
        "controlled_variables": {"changed": ["core.texture_asset_path"], "held_constant": ["core material", "particle parameters", "color", "camera", "capture seed"]},
        "texture_audit": {"flat_texture": FLAT_TEXTURE, "structured_texture": STRUCTURED_TEXTURE, "structured_texture_is_single_frame": True},
        "shared_capture_seed_id": SHARED_CAPTURE_SEED_ID,
        "variants": variants,
        "status": "prepared",
    })
    compile_path = _write(output_root / "compile_request.json", {"schema_version": "vfx_prefab_graph_batch_compile_request.v1", "created_at": datetime.now(timezone.utc).isoformat(), "requests": requests})
    return {"experiment": experiment_path, "compile_request": compile_path}


def prepare_runtime(experiment_path: Path, output_path: Path) -> Path:
    experiment = _read(experiment_path.resolve())
    requests = []
    for variant in experiment["variants"]:
        result = _read(_repo_root() / variant["compile_result_path"])
        if result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {variant['variant']}")
        root = output_path.resolve().parent / "runtime_captures" / variant["variant"]
        requests.append({"candidate_id": experiment["shared_capture_seed_id"], "prefab_path": result["output_prefab_path"], "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": (root / "capture_manifest.json").as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "explosion", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 1.5})
    return _write(output_path.resolve(), {"schema_version": "effectdemo_source_render_requests.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_path.resolve().parent.name, "scene": "ProfessionalTeacherExplosionMaterial", "camera": "ProfessionalTeacherExplosionMaterialCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 0.8, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": requests})


def _frame_metrics(path: Path) -> dict[str, float]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    corners = np.concatenate((rgb[:5, :5].reshape(-1, 3), rgb[:5, -5:].reshape(-1, 3), rgb[-5:, :5].reshape(-1, 3), rgb[-5:, -5:].reshape(-1, 3)))
    background = np.median(corners, axis=0)
    delta = np.max(np.abs(rgb - background), axis=2)
    visible = delta > 8
    if not visible.any():
        return {"visible_area_ratio": 0.0, "bbox_fill_ratio": 0.0, "visible_luma_mean": 0.0, "visible_luma_std": 0.0, "edge_density": 0.0, "center_luminance": 0.0}
    yy, xx = np.nonzero(visible)
    bbox_area = max(1, (int(xx.max()) - int(xx.min()) + 1) * (int(yy.max()) - int(yy.min()) + 1))
    luma = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]) / 255.0
    gx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
    gy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
    height, width = visible.shape
    center = luma[height * 3 // 8:height * 5 // 8, width * 3 // 8:width * 5 // 8]
    return {
        "visible_area_ratio": float(visible.mean()),
        "bbox_fill_ratio": float(visible.sum() / bbox_area),
        "visible_luma_mean": float(luma[visible].mean()),
        "visible_luma_std": float(luma[visible].std()),
        "edge_density": float(((gx + gy) > 0.08)[visible].mean()),
        "center_luminance": float(center.mean()),
    }


def _variant_summary(manifest_path: Path, max_time_seconds: float = 0.45) -> dict[str, Any]:
    capture = _capture_summary(manifest_path)
    frames = []
    for row in capture["frames"]:
        if row["time_seconds"] <= max_time_seconds:
            frames.append({"time_seconds": row["time_seconds"], "path": row["path"], **_frame_metrics(_repo_root() / row["path"])})
    if not frames:
        raise ValueError(f"no material frames at or before {max_time_seconds}: {manifest_path}")
    peak = max(frames, key=lambda row: row["visible_area_ratio"])
    return {"capture": capture, "frames": frames, "peak": peak}


def _contact_sheet(summaries: dict[str, dict[str, Any]], output: Path) -> Path:
    targets = [0.05, 0.1, 0.175, 0.25, 0.35]
    tile_width, tile_height = 220, 210
    canvas = Image.new("RGB", (tile_width * len(targets), tile_height * 2 + 36), "#101418")
    draw = ImageDraw.Draw(canvas)
    for row_index, variant in enumerate(("flat_glow", "structured_flame")):
        top = 36 + row_index * tile_height
        draw.text((8, top + 5), variant, fill="#ffba6a" if row_index else "#aeb8c2")
        frames = summaries[variant]["frames"]
        for column, target in enumerate(targets):
            frame = min(frames, key=lambda row: abs(float(row["time_seconds"]) - target))
            with Image.open(_repo_root() / frame["path"]) as source:
                tile = ImageOps.contain(source.convert("RGB"), (tile_width - 8, tile_height - 28))
            left = column * tile_width
            canvas.paste(tile, (left + 4, top + 24))
            draw.text((left + 6, 9), f"{float(frame['time_seconds']):.3f}s", fill="#e4e7ea")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def finalize(experiment_path: Path, output_path: Path) -> dict[str, Path]:
    experiment = _read(experiment_path.resolve())
    graphs = {row["variant"]: _read(_repo_root() / row["graph_path"]) for row in experiment["variants"]}
    graph_comparison = _controlled_graph_comparison(graphs["flat_glow"], graphs["structured_flame"])
    compile_results = {row["variant"]: _read(_repo_root() / row["compile_result_path"]) for row in experiment["variants"]}
    readback_results = {row["variant"]: _read(_repo_root() / row["readback_result_path"]) for row in experiment["variants"]}
    runtime_root = experiment_path.resolve().parent / "runtime_captures"
    summaries = {variant: _variant_summary(runtime_root / variant / "capture_manifest.json") for variant in ("flat_glow", "structured_flame")}
    flat, structured = summaries["flat_glow"]["peak"], summaries["structured_flame"]["peak"]
    comparison = {
        "bbox_fill_reduction": flat["bbox_fill_ratio"] - structured["bbox_fill_ratio"],
        "visible_luma_std_gain": structured["visible_luma_std"] - flat["visible_luma_std"],
        "edge_density_gain": structured["edge_density"] - flat["edge_density"],
        "center_luminance_ratio": structured["center_luminance"] / max(flat["center_luminance"], 1e-6),
    }
    left_capture, right_capture = summaries["flat_glow"]["capture"], summaries["structured_flame"]["capture"]
    gates = {
        "controlled_graph_difference_only_core_texture": graph_comparison["only_core_texture_differs"],
        "both_compile_pass": all(row.get("status") == "pass" for row in compile_results.values()),
        "both_texture_readbacks_match_plan": all(bool(row.get("planned_texture_readback_match")) for row in compile_results.values()),
        "both_prefab_api_readbacks_pass": all(row.get("status") == "pass" for row in readback_results.values()),
        "both_runtime_eligible": left_capture["image_sequence_training_eligible"] and right_capture["image_sequence_training_eligible"],
        "no_material_render_errors": left_capture["material_render_error_frame_count"] == right_capture["material_render_error_frame_count"] == 0,
        "same_forced_camera": left_capture["selected_camera_view"] == right_capture["selected_camera_view"] == "front",
        "structured_core_remains_visible": structured["visible_area_ratio"] >= 0.001 and comparison["center_luminance_ratio"] >= 0.25,
        "structured_core_has_more_edge_structure": comparison["edge_density_gain"] >= 0.02,
        "structured_core_breaks_flat_fill": comparison["bbox_fill_reduction"] >= 0.08,
    }
    verified = all(gates.values())
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": RULE_ID,
        "professional_source": experiment["professional_source"],
        "controlled_variables": experiment["controlled_variables"],
        "texture_audit": experiment["texture_audit"],
        "experiment_manifest_path": _portable(experiment_path.resolve()),
        "unity": {"version": "2022.3.16f1c1", "project": "workspace/unity-render-staging/EffectDemoPromptHumanR001", "render_pipeline": "URP 14.0.9", "capture_mode": "play_mode_runtime_isolated_multiview.v2"},
        "graph_comparison": graph_comparison,
        "variants": summaries,
        "comparison": comparison,
        "quality_gates": gates,
        "validated_controller_prior": {"status": "eligible" if verified else "blocked", "effect_family": "explosion", "target_role": "core", "judgment_axis": "core_texture_structure", "reference_graph_path": next(row["graph_path"] for row in experiment["variants"] if row["variant"] == "structured_flame"), "minimum_bbox_fill_reduction": 0.08, "minimum_luma_std_gain": 0.02, "minimum_center_luminance_ratio": 0.25, "allowed_use": "explosion_core_texture_rule_controller_only" if verified else "knowledge_prior_only"},
        "conclusion": "Unity reproduction supports replacing a flat glow patch with a structured soft-edged core texture while retaining a readable center." if verified else "Unity reproduction did not satisfy the structured core-texture gates.",
        "status": "verified" if verified else "blocked",
    }
    report_path = _write(output_path.resolve(), report)
    sheet_path = _contact_sheet(summaries, output_path.resolve().parent / "material_pair_contact_sheet.png")
    teacher_root = output_path.resolve().parent / "teacher_index"
    record = {"schema_version": "course_knowledge_record.v1", "record_id": RULE_ID, "source_path": "knowledge/sources/SRC-2026-SERIES-001/ep007/visual_review_middle.md", "heading": "火焰需要核心、边缘和暗部", "line_start": 25, "line_end": 30, "excerpt": experiment["professional_source"]["expert_judgment"], "record_type": "tutorial_fact", "status": "verified" if verified else "pending", "effect_family": "explosion", "evidence_level": "high" if verified else "medium", "timecodes": experiment["professional_source"]["timecodes"], "frame_paths": experiment["professional_source"]["frame_paths"], "judgment_axes": experiment["professional_source"]["judgment_axes"], "source_expertise_status": "verified_professional", "unity_reproduction_status": "verified" if verified else "blocked", "unity_reproduction_report": _portable(report_path), "eligible_for_vfxspec_prior": verified, "training_eligibility": {"controller_sft": False, "prompt_condition_supervision": False, "positive_generation_supervision": False, "preference_training": False, "reason": "Teacher rule may supervise the explosion core-texture axis only; it is not a global quality label."}}
    records_path = _write_jsonl(teacher_root / "course_knowledge_records.jsonl", [record])
    index_path = _write(teacher_root / "course_knowledge_index.json", {"schema_version": "course_knowledge_index.v1", "created_at": datetime.now(timezone.utc).isoformat(), "index_id": "professional_teacher_explosion_material_r001", "input_count": 1, "record_count": 1, "record_type_counts": {"tutorial_fact": 1}, "status_counts": {record["status"]: 1}, "files": {"records": records_path.name}, "policy": {"source_text_is_evidence_not_training_label": True, "verified_course_fact_still_requires_unity_reproduction": True, "not_visible_is_not_training_data": True}, "status": "pass"})
    return {"report": report_path, "contact_sheet": sheet_path, "teacher_index": index_path, "teacher_records": records_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a controlled explosion core-material Teacher reproduction.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--source-graph", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--asset-root", required=True)
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--experiment", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--experiment", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            paths = prepare(args.source_graph, args.output_root, args.asset_root)
        elif args.command == "prepare-runtime":
            paths = {"runtime_request": prepare_runtime(args.experiment, args.output)}
        else:
            paths = finalize(args.experiment, args.output)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
