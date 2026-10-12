"""Build same-topology Debris-off pairs for the verified explosion Teacher rule."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from .prefab_graph import assign_graph_id
from .professional_debris_teacher_reproduction import _pair_summary
from .professional_residual_teacher_reproduction import _early_pair_mae
from .professional_teacher_guided_generation import _load_teacher_rule, _single_role_component, _validate_graph
from .professional_teacher_reproduction import _capture_summary, _difference_paths, _paired_frame_comparison


SCHEMA_VERSION = "vfx_professional_debris_ablation_batch.v1"
RULE_ID = "professional_explosion_debris_branches_r001"


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


def create_debris_ablation(graph: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "explosion":
        raise ValueError("debris ablation requires an explosion PrefabGraph")
    debris = _single_role_component(result, "particle_systems", "hit")
    start_color = list(debris["parameters"].get("start_color_rgba") or [1.0, 1.0, 1.0, 1.0])
    start_color[3] = 0.0
    debris["parameters"]["start_color_rgba"] = start_color
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, ["hit.parameters.start_color_rgba[3]"]


def _controlled_graph_comparison(no_debris: dict[str, Any], radial_debris: dict[str, Any]) -> dict[str, Any]:
    left, right = copy.deepcopy(no_debris), copy.deepcopy(radial_debris)
    left.pop("graph_id", None)
    right.pop("graph_id", None)
    paths = _difference_paths(left, right)
    particles = (left.get("components") or {}).get("particle_systems") or []
    hit = _single_role_component(left, "particle_systems", "hit")
    hit_index = next(index for index, row in enumerate(particles) if row is hit)
    expected = f"components.particle_systems[{hit_index}].parameters.start_color_rgba[3]"
    return {"difference_paths": paths, "expected_difference_path": expected, "only_debris_alpha_differs": paths == [expected]}


def prepare(source_manifest_path: Path, teacher_ready_path: Path, output_root: Path, asset_root: str) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"debris ablation output already exists and is not empty: {output_root}")
    source_manifest = _read(source_manifest_path.resolve())
    teacher, report, _ = _load_teacher_rule(teacher_ready_path.resolve(), RULE_ID)
    if source_manifest.get("effect_family") != "explosion":
        raise ValueError("debris ablation source manifest must be an explosion family batch")
    candidates, requests = [], []
    for index, source_candidate in enumerate(source_manifest["candidates"]):
        source_graph_path = _resolve(source_candidate["graph_path"])
        source_graph = _read(source_graph_path)
        no_debris_graph, changed_fields = create_debris_ablation(source_graph)
        pair_id = f"layered_debris_pair_{index:03d}_{source_graph['graph_id']}"
        graph_path = _write(output_root / "candidates" / pair_id / "no_debris_graph.json", no_debris_graph)
        output_prefab = f"{asset_root.rstrip('/')}/{pair_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{pair_id}.json"
        readback_graph = output_root / "readback" / f"{pair_id}.json"
        readback_result = output_root / "readback_results" / f"{pair_id}.json"
        source_compile = _read(_resolve(source_candidate["compile_result_path"]))
        source_readback = _read(_resolve(source_candidate["readback_result_path"]))
        if source_compile.get("status") != "pass" or source_readback.get("status") != "pass":
            raise ValueError(f"source layered explosion is not technically valid: {source_candidate['candidate_id']}")
        candidates.append({
            "candidate_id": pair_id,
            "source_candidate_id": source_candidate["candidate_id"],
            "source_graph_id": source_graph["graph_id"],
            "source_graph_path": _portable(source_graph_path),
            "guided_graph_id": source_graph["graph_id"],
            "guided_graph_path": _portable(source_graph_path),
            "guided_prefab_path": source_compile["output_prefab_path"],
            "baseline_graph_id": no_debris_graph["graph_id"],
            "baseline_graph_path": _portable(graph_path),
            "output_prefab_path": output_prefab,
            "compile_result_path": _portable(compile_result),
            "readback_graph_path": _portable(readback_graph),
            "readback_result_path": _portable(readback_result),
            "baseline_capture_manifest_path": _portable(output_root / "runtime_baselines" / pair_id / "capture_manifest.json"),
            "capture_manifest_path": _portable(output_root / "runtime_captures" / pair_id / "capture_manifest.json"),
            "changed_fields": changed_fields,
        })
        requests.append({"graph_path": graph_path.as_posix(), "output_prefab_path": output_prefab, "result_path": compile_result.as_posix()})
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
        compile_result = _read(_resolve(candidate["compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing Debris-off compile result required: {candidate['candidate_id']}")
        for prefab_path, root_name in (
            (compile_result["output_prefab_path"], "runtime_baselines"),
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
        "scene": "LayeredExplosionDebrisAblation",
        "camera": "LayeredExplosionDebrisAblationCamera",
        "width": 640,
        "height": 640,
        "sampling_mode": "adaptive_runtime",
        "sampling": {"target_intervals": 32, "short_effect_target_intervals": 32, "min_interval_seconds": 0.01, "max_interval_seconds": 0.025, "max_duration_seconds": 1.2, "include_zero": True, "duration_sources": ["particle_system"]},
        "capture_material_timeline": True,
        "requests": requests,
    })


def _nearest_frame(summary: dict[str, Any], target: float) -> dict[str, Any] | None:
    frames = summary.get("frames") or []
    return min(frames, key=lambda row: abs(float(row["time_seconds"]) - target)) if frames else None


def _build_contact_sheet(records: list[dict[str, Any]], output: Path) -> Path:
    targets = [0.075, 0.15, 0.25, 0.4, 0.55]
    tile_width, tile_height, label_width = 152, 152, 225
    canvas = Image.new("RGB", (label_width + tile_width * 10, tile_height * len(records) + 34), "#101418")
    draw = ImageDraw.Draw(canvas)
    draw.text((label_width + 6, 10), "no debris", fill="#aeb8c2")
    draw.text((label_width + tile_width * 5 + 6, 10), "radial debris", fill="#ffba6a")
    for row_index, record in enumerate(records):
        top = 34 + row_index * tile_height
        draw.text((6, top + 8), record["candidate_id"][:31], fill="#f0f2f4")
        draw.text((6, top + 28), f"components {record['peak_component_count']:.0f}", fill="#ffba6a")
        for variant_index, key in enumerate(("baseline_summary", "guided_summary")):
            for column, target in enumerate(targets):
                frame = _nearest_frame(record[key], target)
                if frame is None:
                    continue
                with Image.open(_resolve(frame["path"])) as source:
                    tile = ImageOps.contain(source.convert("RGB"), (tile_width - 8, tile_height - 24))
                left = label_width + (variant_index * 5 + column) * tile_width
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
        baseline_graph = _read(_resolve(candidate["baseline_graph_path"]))
        guided_graph = _read(_resolve(candidate["guided_graph_path"]))
        graph_comparison = _controlled_graph_comparison(baseline_graph, guided_graph)
        baseline_manifest = _resolve(candidate["baseline_capture_manifest_path"])
        guided_manifest = _resolve(candidate["capture_manifest_path"])
        baseline_capture = _capture_summary(baseline_manifest)
        guided_capture = _capture_summary(guided_manifest)
        paired = _paired_frame_comparison(baseline_capture, guided_capture)
        summary = _pair_summary(baseline_manifest, guided_manifest)
        early_mae = _early_pair_mae(baseline_capture, guided_capture, 0.06)
        left, right = summary["left_capture"], summary["right_capture"]
        technical_gates = {
            "controlled_graph_difference_only_debris_alpha": graph_comparison["only_debris_alpha_differs"],
            "debris_off_compile_pass": compile_result.get("status") == "pass",
            "debris_off_texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")),
            "debris_off_prefab_api_readback_pass": readback_result.get("status") == "pass",
            "both_runtime_eligible": left["image_sequence_training_eligible"] and right["image_sequence_training_eligible"],
            "no_material_render_errors": left["material_render_error_frame_count"] == right["material_render_error_frame_count"] == 0,
            "same_forced_camera": left["selected_camera_view"] == right["selected_camera_view"] == "front",
            "equal_nonzero_frame_count": left["valid_frame_count"] > 0 and left["valid_frame_count"] == right["valid_frame_count"],
            "all_frames_matched_by_time": paired["matched_frame_count"] == left["valid_frame_count"] == right["valid_frame_count"],
            "pre_debris_frames_unchanged": early_mae <= 0.002,
        }
        technical_pass = all(technical_gates.values())
        rule_gates = {
            "multiple_debris_components": summary["peak_component_count"] >= float(prior["minimum_component_count"]),
            "debris_reaches_outside_core": summary["peak_radius_p90"] >= float(prior["minimum_peak_radius_p90"]),
            "debris_visible_across_frames": summary["active_difference_frame_count"] >= 5,
        }
        rule_pass = technical_pass and all(rule_gates.values())
        records.append({
            "candidate_id": candidate["candidate_id"],
            "source_candidate_id": candidate["source_candidate_id"],
            "guided_graph_id": candidate["guided_graph_id"],
            "graph_comparison": graph_comparison,
            "technical_gates": technical_gates,
            "rule_gates": rule_gates,
            "technical_pass": technical_pass,
            "professional_rule_transfer_pass": rule_pass,
            "early_frame_max_mae": early_mae,
            "peak_component_count": summary["peak_component_count"],
            "peak_radius_p90": summary["peak_radius_p90"],
            "active_difference_frame_count": summary["active_difference_frame_count"],
            "baseline_summary": left,
            "guided_summary": right,
            "training_eligibility": {
                "eligible_tasks": ["explosion_debris_branches_rule_controller"] if rule_pass else [],
                "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"],
                "label_scope": "relative_debris_branch_presence_within_verified_pair",
            },
        })
    sheet = _build_contact_sheet(records, output_path.resolve().parent / "debris_pair_contact_sheet.png")
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "teacher_rule": manifest["teacher_rule"],
        "candidate_count": len(records),
        "technical_pass_count": sum(row["technical_pass"] for row in records),
        "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records),
        "contact_sheet_path": _portable(sheet),
        "records": records,
        "status": "pass" if records and all(row["technical_pass"] for row in records) and all(row["professional_rule_transfer_pass"] for row in records) else "blocked",
        "training_scope": "same-topology explosion debris-branch ablation pairs only",
    }
    return _write(output_path.resolve(), report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build same-topology explosion Debris-off pairs.")
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
