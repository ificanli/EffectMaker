"""Run same-seed, fixed-asset checks of actual Prompt-to-Unity controls."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from .material_plan import apply_material_plan
from .procedure_prefab_graph import build_procedure_execution
from .prompt_execution_controls import execution_fingerprint


CASES = {
    "blue_vertical_short": "风格化蓝色纵向闪电，持续0.15秒",
    "red_vertical_short": "风格化红色纵向闪电，持续0.15秒",
    "blue_horizontal_short": "风格化蓝色横向闪电，持续0.15秒",
    "blue_vertical_long": "风格化蓝色纵向闪电，持续0.45秒",
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def prepare_regression(procedure_path: Path, material_plan_path: Path, output_root: Path, asset_root: str, seed: int) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"regression output is not empty: {output_root}")
    procedure, material_plan = _read(procedure_path), _read(material_plan_path)
    cases, compile_requests, render_requests = [], [], []
    for name, prompt in CASES.items():
        graph, controls = build_procedure_execution(procedure, prompt, "lightning", seed)
        if {row["component_id"] for row in material_plan["layers"]} != {row["component_id"] for row in graph["components"]["particle_systems"]}:
            raise ValueError("MaterialPlan component set does not match the ProcedureSpec; regenerate the asset plan after a topology correction.")
        fixed_plan = copy.deepcopy(material_plan)
        fixed_plan["graph_id"] = graph["graph_id"]
        graph = apply_material_plan(graph, fixed_plan)
        root = output_root / name
        graph_path = _write(root / "graph.json", graph)
        _write(root / "execution_controls.json", controls)
        prefab_path = f"{asset_root.rstrip('/')}/{name}/GeneratedRoot.prefab"
        compile_path, readback_path = root / "compile_result.json", root / "readback_result.json"
        capture_path = root / "capture_manifest.json"
        cases.append({"case_id": name, "prompt": prompt, "graph_path": graph_path.as_posix(), "graph_id": graph["graph_id"], "execution_sha256": execution_fingerprint(graph), "prefab_path": prefab_path, "compile_result_path": compile_path.as_posix(), "readback_graph_path": (root / "readback.json").as_posix(), "readback_result_path": readback_path.as_posix(), "capture_manifest_path": capture_path.as_posix()})
        compile_requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": prefab_path, "result_path": compile_path.as_posix()})
        render_requests.append({"candidate_id": name, "random_seed_key": f"prompt_execution_regression:{seed}", "prefab_path": prefab_path, "capture_dir": (root / "captures").as_posix(), "capture_manifest_path": capture_path.as_posix(), "material_timeline_path": (root / "material_timeline.json").as_posix(), "source_script_fidelity": "generated_graph_no_source_scripts", "ignored_script_dependency_count": 0, "missing_script_count": 0, "capture_category": "lightning", "forced_camera_view": "front", "force_orthographic": True, "forced_orthographic_size": 3.2})
    manifest = _write(output_root / "regression_manifest.json", {"schema_version": "vfx_prompt_execution_regression.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": output_root.name, "seed": seed, "source_procedure": procedure_path.resolve().as_posix(), "source_material_plan": material_plan_path.resolve().as_posix(), "scope": "parameter_control_test_not_aesthetic_acceptance", "cases": cases, "training_eligibility": {"controller_sft": False, "positive_generation_supervision": False}})
    compile_request = _write(output_root / "compile_request.json", {"requests": compile_requests})
    renders = _write(output_root / "render_requests.json", {"schema_version": "effectdemo_source_render_requests.v1", "run_id": output_root.name, "scene": "PromptExecutionRegression", "camera": "PromptExecutionCamera", "width": 640, "height": 640, "sampling_mode": "adaptive_runtime", "sampling": {"target_intervals": 48, "short_effect_target_intervals": 48, "min_interval_seconds": 0.005, "max_interval_seconds": 0.01, "max_duration_seconds": 0.7, "include_zero": True, "duration_sources": ["particle_system"]}, "capture_material_timeline": True, "requests": render_requests})
    return {"manifest": manifest, "compile_request": compile_request, "render_requests": renders}


def _capture_metrics(path: Path) -> dict[str, Any]:
    manifest = _read(path)
    frames = []
    for frame in manifest["frames"]:
        image_path = Path(manifest["capture_root"]) / frame["path"]
        if not frame.get("valid") or not image_path.is_file():
            continue
        with Image.open(image_path) as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
        background = np.median(np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1])), axis=0)
        delta = np.maximum(rgb - background, 0)
        mask = delta.max(axis=2) > 8.0
        ys, xs = np.where(mask)
        color = delta[mask].mean(axis=0).tolist() if xs.size else [0.0, 0.0, 0.0]
        frames.append({"path": image_path.as_posix(), "time": frame.get("simulation_elapsed_seconds", frame["capture_time_seconds"]), "visible_pixels": int(xs.size), "width": int(xs.max() - xs.min() + 1) if xs.size else 0, "height": int(ys.max() - ys.min() + 1) if xs.size else 0, "mean_foreground_rgb": color})
    peak = max(frames, key=lambda frame: frame["visible_pixels"], default={"visible_pixels": 0})
    threshold = max(8.0, peak["visible_pixels"] * 0.04)
    visible = [frame for frame in frames if frame["visible_pixels"] > threshold]
    pipeline_instance = manifest.get("render_pipeline_instance_type", "unrecorded")
    pipeline_matches = manifest.get("render_pipeline_verified") is True and pipeline_instance == "UnityEngine.Rendering.Universal.UniversalRenderPipeline"
    return {"valid_frame_count": manifest.get("valid_frame_count", 0), "image_sequence_eligible": manifest.get("image_sequence_training_eligible", False), "material_error_frames": manifest.get("material_render_error_frame_count", 0), "unity_version": manifest.get("unity_version", "unrecorded"), "active_render_pipeline_type": manifest.get("active_render_pipeline_type", "unrecorded"), "render_pipeline_instance_type": pipeline_instance, "target_pipeline_match": pipeline_matches, "particle_seeds": manifest.get("particle_random_seeds", []), "peak": peak, "last_visible_time": max((frame["time"] for frame in visible), default=0.0), "limitations": manifest.get("visual_evidence_limitations", [])}


def finalize_regression(manifest_path: Path) -> Path:
    manifest = _read(manifest_path)
    rows = {}
    for case in manifest["cases"]:
        compiled, readback = _read(Path(case["compile_result_path"])), _read(Path(case["readback_result_path"]))
        capture = _capture_metrics(Path(case["capture_manifest_path"]))
        rows[case["case_id"]] = {**capture, "compile_pass": compiled.get("status") == "pass", "readback_pass": readback.get("status") == "pass", "prefab_path": case["prefab_path"]}
    blue, red = rows["blue_vertical_short"], rows["red_vertical_short"]
    horizontal, long = rows["blue_horizontal_short"], rows["blue_vertical_long"]
    blue_rgb, red_rgb = blue["peak"]["mean_foreground_rgb"], red["peak"]["mean_foreground_rgb"]
    gates = {
        "compile_and_readback": all(row["compile_pass"] and row["readback_pass"] for row in rows.values()),
        "all_captures_visible": all(row["peak"]["visible_pixels"] > 64 and row["material_error_frames"] == 0 for row in rows.values()),
        "particle_seeds_match": all(row["particle_seeds"] == blue["particle_seeds"] for row in rows.values()),
        "color_changed_to_red": red_rgb[0] > red_rgb[2] and blue_rgb[2] > blue_rgb[0],
        "orientation_changed": blue["peak"]["height"] > blue["peak"]["width"] * 1.5 and horizontal["peak"]["width"] > horizontal["peak"]["height"] * 1.5,
        "duration_extended": long["last_visible_time"] > blue["last_visible_time"] + 0.15,
        "target_pipeline_match": all(row["target_pipeline_match"] for row in rows.values()),
    }
    sheet = Image.new("RGB", (1280, 1340), "#090b10")
    draw = ImageDraw.Draw(sheet)
    for index, (name, row) in enumerate(rows.items()):
        x, y = (index % 2) * 640, (index // 2) * 670
        if row["peak"].get("path"):
            with Image.open(row["peak"]["path"]) as image:
                sheet.paste(image.convert("RGB").resize((640, 640)), (x, y + 30))
        draw.text((x + 12, y + 8), name, fill="white")
    sheet.save(manifest_path.parent / "contact_sheet.png")
    control_pass = all(value for key, value in gates.items() if key != "target_pipeline_match")
    return _write(manifest_path.parent / "regression_report.json", {"schema_version": "vfx_prompt_execution_regression_report.v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_id": manifest["run_id"], "cases": rows, "gates": gates, "status": "pass_parameter_controls_only" if all(gates.values()) else "diagnostic_controls_pass_pipeline_mismatch" if control_pass else "blocked", "training_eligibility": {"controller_sft": False, "positive_generation_supervision": False}, "limitations": ["This measures bounded parameter controls, not overall aesthetic quality or a trained Planner.", "Particle seeds are held constant; global Shader time is not reset between captures."]})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--procedure", type=Path, required=True)
    prepare.add_argument("--material-plan", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--asset-root", required=True)
    prepare.add_argument("--seed", type=int, default=20260907)
    finish = commands.add_parser("finalize")
    finish.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_regression(args.procedure, args.material_plan, args.output_root, args.asset_root, args.seed) if args.command == "prepare" else {"report": finalize_regression(args.manifest)}
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
