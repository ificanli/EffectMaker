"""Build same-topology Shockwave-static pairs for the verified explosion Teacher rule."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .prefab_graph import assign_graph_id
from .professional_shockwave_teacher_reproduction import _radial_summary, _window_metrics
from .professional_teacher_guided_generation import _load_teacher_rule, _single_role_component, _validate_graph
from .professional_teacher_reproduction import _capture_summary, _difference_paths, _paired_frame_comparison


SCHEMA_VERSION = "vfx_professional_shockwave_ablation_batch.v1"
RULE_ID = "professional_explosion_shockwave_expansion_r001"


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


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _support_window(graph: dict[str, Any]) -> tuple[float, float]:
    support = _single_role_component(graph, "particle_systems", "support")
    parameters = support["parameters"]
    delay = float(parameters.get("start_delay_max") or 0.0)
    lifetime = float(parameters.get("start_lifetime_max") or 0.5)
    return max(0.075, delay + 0.025), min(0.6, delay + lifetime)


def create_shockwave_ablation(graph: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "explosion":
        raise ValueError("shockwave ablation requires an explosion PrefabGraph")
    support = _single_role_component(result, "particle_systems", "support")
    support["parameters"]["end_size_multiplier"] = 1.0
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, ["support.parameters.end_size_multiplier"]


def _controlled_graph_comparison(static_graph: dict[str, Any], expanding_graph: dict[str, Any]) -> dict[str, Any]:
    static = copy.deepcopy(static_graph)
    expanding = copy.deepcopy(expanding_graph)
    static.pop("graph_id", None)
    expanding.pop("graph_id", None)
    paths = _difference_paths(static, expanding)
    particles = (static.get("components") or {}).get("particle_systems") or []
    support = _single_role_component(static, "particle_systems", "support")
    support_index = next(index for index, row in enumerate(particles) if row is support)
    expected = f"components.particle_systems[{support_index}].parameters.end_size_multiplier"
    return {
        "difference_paths": paths,
        "expected_difference_path": expected,
        "only_shockwave_scale_curve_differs": paths == [expected],
    }


def prepare(source_manifest_path: Path, teacher_ready_path: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"shockwave ablation output already exists and is not empty: {output_root}")
    source_manifest = _read(source_manifest_path.resolve())
    teacher, report, _ = _load_teacher_rule(teacher_ready_path.resolve(), RULE_ID)
    if source_manifest.get("effect_family") != "explosion":
        raise ValueError("shockwave ablation source manifest must be an explosion family batch")

    candidates: list[dict[str, Any]] = []
    requests: list[dict[str, str]] = []
    for index, source_candidate in enumerate(source_manifest["candidates"]):
        source_graph_path = _resolve(source_candidate["graph_path"])
        source_graph = _read(source_graph_path)
        static_graph, changed_fields = create_shockwave_ablation(source_graph)
        pair_id = f"layered_shockwave_pair_{index:03d}_{source_graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / pair_id / "static_graph.json", static_graph)
        output_prefab = f"{asset_root.rstrip('/')}/{pair_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{pair_id}.json"
        readback_graph = output_root / "readback" / f"{pair_id}.json"
        readback_result = output_root / "readback_results" / f"{pair_id}.json"
        source_compile = _read(_resolve(source_candidate["compile_result_path"]))
        source_readback = _read(_resolve(source_candidate["readback_result_path"]))
        if source_compile.get("status") != "pass" or source_readback.get("status") != "pass":
            raise ValueError(f"source layered explosion is not technically valid: {source_candidate['candidate_id']}")
        window_start, window_end = _support_window(source_graph)
        candidates.append({
            "candidate_id": pair_id,
            "source_candidate_id": source_candidate["candidate_id"],
            "source_graph_id": source_graph["graph_id"],
            "source_graph_path": _portable(source_graph_path),
            "guided_graph_id": source_graph["graph_id"],
            "guided_graph_path": _portable(source_graph_path),
            "guided_prefab_path": source_compile["output_prefab_path"],
            "baseline_graph_id": static_graph["graph_id"],
            "baseline_graph_path": _portable(graph_path),
            "output_prefab_path": output_prefab,
            "compile_result_path": _portable(compile_result),
            "readback_graph_path": _portable(readback_graph),
            "readback_result_path": _portable(readback_result),
            "baseline_capture_manifest_path": _portable(output_root / "runtime_baselines" / pair_id / "capture_manifest.json"),
            "capture_manifest_path": _portable(output_root / "runtime_captures" / pair_id / "capture_manifest.json"),
            "measurement_window_seconds": [window_start, window_end],
            "changed_fields": changed_fields,
        })
        requests.append({
            "graph_path": graph_path.as_posix(),
            "output_prefab_path": output_prefab,
            "result_path": compile_result.as_posix(),
        })

    manifest_path = _write(output_root / "guided_generation_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "source_manifest_path": _portable(source_manifest_path.resolve()),
        "teacher_ready_path": _portable(teacher_ready_path.resolve()),
        "teacher_rule": {
            "record_id": RULE_ID,
            "effect_family": "explosion",
            "judgment_axes": teacher["judgment_axes"],
            "expert_judgment": teacher["expert_judgment"],
            "reproduction_report": teacher["unity_reproduction_report"],
            "controller_prior": report["validated_controller_prior"],
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "status": "prepared_pending_unity",
    })
    compile_path = _write(output_root / "compile_request.json", {
        "schema_version": "vfx_prefab_graph_batch_compile_request.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requests": requests,
    })
    return {"manifest": manifest_path, "compile_request": compile_path}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    requests = []
    for candidate in manifest["candidates"]:
        ablation_compile = _read(_resolve(candidate["compile_result_path"]))
        if ablation_compile.get("status") != "pass":
            raise ValueError(f"passing Shockwave-static compile result required: {candidate['candidate_id']}")
        for prefab_path, root_name in (
            (ablation_compile["output_prefab_path"], "runtime_baselines"),
            (candidate["guided_prefab_path"], "runtime_captures"),
        ):
            case_root = output_path.resolve().parent / root_name / candidate["candidate_id"]
            requests.append({
                "candidate_id": candidate["source_candidate_id"],
                "prefab_path": prefab_path,
                "capture_dir": (case_root / "captures").as_posix(),
                "capture_manifest_path": (case_root / "capture_manifest.json").as_posix(),
                "material_timeline_path": (case_root / "material_timeline.json").as_posix(),
                "source_script_fidelity": "generated_graph_no_source_scripts",
                "ignored_script_dependency_count": 0,
                "missing_script_count": 0,
                "capture_category": "explosion",
                "forced_camera_view": "front",
                "force_orthographic": True,
                "forced_orthographic_size": 3.0,
            })
    return _write(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "scene": "LayeredExplosionShockwaveAblation",
        "camera": "LayeredExplosionShockwaveAblationCamera",
        "width": 640,
        "height": 640,
        "sampling_mode": "adaptive_runtime",
        "sampling": {
            "target_intervals": 32,
            "short_effect_target_intervals": 32,
            "min_interval_seconds": 0.01,
            "max_interval_seconds": 0.025,
            "max_duration_seconds": 1.5,
            "include_zero": True,
            "duration_sources": ["particle_system"],
        },
        "capture_material_timeline": True,
        "requests": requests,
    })


def _difference_frame_metrics(static_path: Path, expanding_path: Path) -> dict[str, float]:
    with Image.open(static_path) as static_image, Image.open(expanding_path) as expanding_image:
        static = np.asarray(static_image.convert("RGB"), dtype=np.int16)
        expanding = np.asarray(expanding_image.convert("RGB"), dtype=np.int16)
    if static.shape != expanding.shape:
        raise ValueError(f"paired frame sizes differ: {static_path} vs {expanding_path}")
    delta_rgb = np.abs(expanding - static)
    delta = np.max(delta_rgb, axis=2)
    visible = delta > 8
    mae = float(delta_rgb.mean() / 255.0)
    if not visible.any():
        return {
            "difference_visible_area_ratio": 0.0,
            "difference_radius_p10": 0.0,
            "difference_radius_p90": 0.0,
            "difference_radial_span": 0.0,
            "difference_mae": mae,
        }
    height, width = visible.shape
    yy, xx = np.nonzero(visible)
    radius = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (height - 1) / 2.0) ** 2) / (min(width, height) / 2.0)
    radius_p10 = float(np.percentile(radius, 10))
    radius_p90 = float(np.percentile(radius, 90))
    return {
        "difference_visible_area_ratio": float(visible.mean()),
        "difference_radius_p10": radius_p10,
        "difference_radius_p90": radius_p90,
        "difference_radial_span": radius_p90 - radius_p10,
        "difference_mae": mae,
    }


def _paired_difference_summary(
    static: dict[str, Any],
    expanding: dict[str, Any],
    start: float,
    end: float,
) -> dict[str, Any]:
    static_by_time = {round(float(row["time_seconds"]), 6): row for row in static["frames"]}
    expanding_by_time = {round(float(row["time_seconds"]), 6): row for row in expanding["frames"]}
    frames = []
    for time_seconds in sorted(set(static_by_time) & set(expanding_by_time)):
        if not start <= time_seconds <= end:
            continue
        left, right = static_by_time[time_seconds], expanding_by_time[time_seconds]
        metrics = _difference_frame_metrics(_resolve(left["path"]), _resolve(right["path"]))
        frames.append({"time_seconds": time_seconds, **metrics})
    active = [row for row in frames if row["difference_visible_area_ratio"] >= 0.0001]
    radii = [row["difference_radius_p90"] for row in active]
    radius_growth = 0.0 if len(radii) < 2 else max(radii) - radii[0]
    nondecreasing = 0.0 if len(radii) < 2 else sum(
        radii[index] + 0.005 >= radii[index - 1] for index in range(1, len(radii))
    ) / (len(radii) - 1)
    return {
        "matched_frame_count": len(frames),
        "active_difference_frame_count": len(active),
        "initial_difference_radius_p90": radii[0] if radii else 0.0,
        "peak_difference_radius_p90": max(radii, default=0.0),
        "difference_radius_growth": radius_growth,
        "nondecreasing_step_ratio": nondecreasing,
        "peak_difference_radial_span": max((row["difference_radial_span"] for row in active), default=0.0),
        "peak_difference_visible_area_ratio": max((row["difference_visible_area_ratio"] for row in active), default=0.0),
        "peak_difference_mae": max((row["difference_mae"] for row in frames), default=0.0),
        "frames": frames,
    }


def _nearest_frame(summary: dict[str, Any], target: float) -> dict[str, Any] | None:
    frames = summary.get("frames") or []
    return min(frames, key=lambda row: abs(float(row["time_seconds"]) - target)) if frames else None


def _build_contact_sheet(records: list[dict[str, Any]], output: Path) -> Path:
    tile_size = (172, 172)
    label_width, header_height = 250, 36
    columns_per_variant = 5
    width = label_width + tile_size[0] * columns_per_variant * 2
    height = header_height + tile_size[1] * len(records)
    canvas = Image.new("RGB", (width, height), "#101418")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 10), "pair", fill="#f0f2f4")
    draw.text((label_width + 8, 10), "static shockwave", fill="#aeb8c2")
    draw.text((label_width + tile_size[0] * columns_per_variant + 8, 10), "expanding shockwave", fill="#ffba6a")
    for row_index, record in enumerate(records):
        top = header_height + row_index * tile_size[1]
        draw.text((8, top + 8), record["candidate_id"][:34], fill="#f0f2f4")
        draw.text((8, top + 30), f"growth {record['difference_radius_growth']:.3f}", fill="#ffba6a")
        start, end = record["measurement_window_seconds"]
        targets = [start + (end - start) * step / (columns_per_variant - 1) for step in range(columns_per_variant)]
        for variant_index, key in enumerate(("baseline_summary", "guided_summary")):
            summary = record[key]
            for column, target in enumerate(targets):
                frame = _nearest_frame(summary, target)
                if frame is None:
                    continue
                with Image.open(_resolve(frame["path"])) as source:
                    tile = ImageOps.contain(source.convert("RGB"), (tile_size[0] - 8, tile_size[1] - 24))
                left = label_width + (variant_index * columns_per_variant + column) * tile_size[0]
                canvas.paste(tile, (left + 4, top + 20))
                draw.text((left + 5, top + 4), f"{float(frame['time_seconds']):.3f}s", fill="#d9dee3")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def finalize(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read(manifest_path.resolve())
    prior = manifest["teacher_rule"]["controller_prior"]
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        readback_result = _read(_resolve(candidate["readback_result_path"]))
        static_graph = _read(_resolve(candidate["baseline_graph_path"]))
        expanding_graph = _read(_resolve(candidate["guided_graph_path"]))
        graph_comparison = _controlled_graph_comparison(static_graph, expanding_graph)
        baseline_capture = _capture_summary(_resolve(candidate["baseline_capture_manifest_path"]))
        guided_capture = _capture_summary(_resolve(candidate["capture_manifest_path"]))
        paired = _paired_frame_comparison(baseline_capture, guided_capture)
        baseline = _radial_summary(_resolve(candidate["baseline_capture_manifest_path"]))
        guided = _radial_summary(_resolve(candidate["capture_manifest_path"]))
        start, end = (float(value) for value in candidate["measurement_window_seconds"])
        baseline_window = _window_metrics(baseline, start, end)
        guided_window = _window_metrics(guided, start, end)
        difference = _paired_difference_summary(baseline, guided, start, end)
        baseline_by_time = {round(float(row["time_seconds"]), 6): row for row in baseline["frames"]}
        guided_by_time = {round(float(row["time_seconds"]), 6): row for row in guided["frames"]}
        paired_radius_gains = [
            guided_by_time[t]["visible_radius_p90"] - baseline_by_time[t]["visible_radius_p90"]
            for t in sorted(set(baseline_by_time) & set(guided_by_time))
            if start <= t <= end
        ]
        peak_paired_radius_gain = max(paired_radius_gains, default=0.0)
        static_support = _single_role_component(static_graph, "particle_systems", "support")["parameters"]
        expanding_support = _single_role_component(expanding_graph, "particle_systems", "support")["parameters"]
        technical_gates = {
            "controlled_graph_difference_only_shockwave_scale": graph_comparison["only_shockwave_scale_curve_differs"],
            "static_end_size_multiplier_is_one": abs(float(static_support["end_size_multiplier"]) - 1.0) <= 1e-6,
            "expanding_end_size_multiplier_is_larger": float(expanding_support["end_size_multiplier"]) > 1.0,
            "shockwave_static_compile_pass": compile_result.get("status") == "pass",
            "shockwave_static_texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")),
            "shockwave_static_prefab_api_readback_pass": readback_result.get("status") == "pass",
            "both_runtime_eligible": baseline["image_sequence_training_eligible"] and guided["image_sequence_training_eligible"],
            "no_material_render_errors": baseline["material_render_error_frame_count"] == guided["material_render_error_frame_count"] == 0,
            "same_forced_camera": baseline["selected_camera_view"] == guided["selected_camera_view"] == "front" and baseline["camera_mode"] == guided["camera_mode"] == "forced_request_view_fixed_frame",
            "equal_nonzero_frame_count": baseline["valid_frame_count"] > 0 and baseline["valid_frame_count"] == guided["valid_frame_count"],
            "all_frames_matched_by_time": paired["matched_frame_count"] == baseline["valid_frame_count"] == guided["valid_frame_count"],
        }
        technical_pass = all(technical_gates.values())
        rule_gates = {
            "difference_frames_present": difference["active_difference_frame_count"] >= 4,
            "difference_reaches_teacher_radial_growth": max(
                difference["difference_radius_growth"],
                difference["peak_difference_radial_span"],
            ) >= float(prior["minimum_radius_growth"]),
            "difference_is_mostly_outward": difference["nondecreasing_step_ratio"] >= 0.65,
            "paired_radial_separation": difference["peak_difference_radial_span"] >= float(prior["minimum_paired_radius_gain"]),
        }
        rule_pass = technical_pass and all(rule_gates.values())
        records.append({
            "candidate_id": candidate["candidate_id"],
            "source_candidate_id": candidate["source_candidate_id"],
            "guided_graph_id": candidate["guided_graph_id"],
            "measurement_window_seconds": [start, end],
            "graph_comparison": graph_comparison,
            "technical_gates": technical_gates,
            "rule_gates": rule_gates,
            "technical_pass": technical_pass,
            "professional_rule_transfer_pass": rule_pass,
            "baseline_window_metrics": baseline_window,
            "guided_window_metrics": guided_window,
            "peak_paired_radius_gain": peak_paired_radius_gain,
            "difference_radius_growth": difference["difference_radius_growth"],
            "peak_difference_radial_span": difference["peak_difference_radial_span"],
            "difference_nondecreasing_step_ratio": difference["nondecreasing_step_ratio"],
            "difference_summary": difference,
            "baseline_summary": baseline,
            "guided_summary": guided,
            "training_eligibility": {
                "eligible_tasks": ["explosion_shockwave_expansion_rule_controller"] if rule_pass else [],
                "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"],
                "label_scope": "relative_shockwave_expansion_within_verified_pair",
            },
        })
    contact_sheet = _build_contact_sheet(records, output_path.resolve().parent / "shockwave_pair_contact_sheet.png")
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "teacher_rule": manifest["teacher_rule"],
        "candidate_count": len(records),
        "technical_pass_count": sum(row["technical_pass"] for row in records),
        "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records),
        "contact_sheet_path": _portable(contact_sheet),
        "records": records,
        "status": "pass" if records and all(row["technical_pass"] for row in records) and all(row["professional_rule_transfer_pass"] for row in records) else "blocked",
        "training_scope": "same-topology explosion shockwave-expansion ablation pairs only",
    }
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build same-topology explosion Shockwave-static pairs.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--source-manifest", type=Path, required=True)
    build.add_argument("--teacher-ready", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--asset-root", required=True)
    runtime = commands.add_parser("prepare-runtime")
    runtime.add_argument("--manifest", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--manifest", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            paths = prepare(args.source_manifest, args.teacher_ready, args.output_root, args.asset_root)
        elif args.command == "prepare-runtime":
            paths = {"runtime_request": prepare_runtime(args.manifest, args.output)}
        else:
            paths = {"report": finalize(args.manifest, args.output)}
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
