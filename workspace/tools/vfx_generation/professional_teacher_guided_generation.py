"""Apply verified professional Teacher rules to generated PrefabGraphs."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .prefab_graph import assign_graph_id
from .professional_teacher_reproduction import _capture_summary, _paired_frame_comparison


SCHEMA_VERSION = "vfx_professional_teacher_guided_batch.v1"
SUPPORTED_RULE_ID = "professional_explosion_core_readability_r001"
CORE_PRIOR_FIELDS = (
    "burst_particle_count",
    "color_over_lifetime_enabled",
    "emission_enabled",
    "emission_rate_over_time_max",
    "end_color_rgba",
    "end_size_multiplier",
    "material_template_path",
    "max_particles",
    "renderer_mode",
    "shape_enabled",
    "shape_radius",
    "shape_type",
    "shader_profile",
    "simulation_space",
    "size_over_lifetime_enabled",
    "sorting_order",
    "start_color_rgba",
    "start_lifetime_max",
    "start_size_max",
    "start_speed_max",
    "texture_asset_path",
    "texture_profile",
    "texture_property_name",
)


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value.resolve() if value.is_absolute() else (_repo_root() / value).resolve()


def _validate_graph(graph: dict[str, Any]) -> None:
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(graph), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"guided PrefabGraph schema error at {location}: {errors[0].message}")


def _role_map(graph: dict[str, Any]) -> dict[str, str]:
    return {str(node["node_id"]): str(node.get("role") or "") for node in graph.get("nodes") or []}


def _single_role_component(graph: dict[str, Any], collection: str, role: str) -> dict[str, Any]:
    roles = _role_map(graph)
    values = [row for row in (graph.get("components") or {}).get(collection) or [] if roles.get(str(row.get("node_id"))) == role]
    if len(values) != 1:
        raise ValueError(f"exactly one {role} {collection} entry expected, found {len(values)}")
    return values[0]


def _load_teacher_rule(teacher_ready_path: Path, rule_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    records = _read_jsonl(teacher_ready_path.resolve())
    matches = [row for row in records if row.get("record_id") == rule_id]
    if len(matches) != 1:
        raise ValueError(f"exactly one Teacher-ready rule {rule_id} expected, found {len(matches)}")
    record = matches[0]
    if not record.get("teacher_training_eligible") or record.get("allowed_use") != "aesthetic_teacher_training":
        raise ValueError(f"Teacher rule is not training-ready: {rule_id}")
    report_path = record.get("unity_reproduction_report")
    if not report_path:
        raise ValueError(f"Teacher rule has no Unity reproduction report: {rule_id}")
    report = _read_json(_resolve(str(report_path)))
    prior = report.get("validated_controller_prior") or {}
    if report.get("status") != "verified" or prior.get("status") != "eligible":
        raise ValueError(f"Teacher rule has no verified Controller prior: {rule_id}")
    supported_scopes = {
        "explosion": {"core", "support", "hit", "residual", "multi_layer"},
        "slash": {"core", "support", "core_support", "hit", "residual", "multi_layer"},
        "lightning": {"core", "support", "core_support", "hit", "residual", "multi_layer"},
    }
    if prior.get("target_role") not in supported_scopes.get(str(prior.get("effect_family")), set()):
        raise ValueError(f"unsupported Teacher rule scope: {prior}")
    reference_graph = _read_json(_resolve(str(prior["reference_graph_path"])))
    return record, report, reference_graph


def apply_explosion_core_prior(graph: dict[str, Any], reference_graph: dict[str, Any], rule_id: str) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(graph)
    if str((result.get("condition") or {}).get("effect_family")) != "explosion":
        raise ValueError("explosion Teacher prior requires an explosion PrefabGraph")
    target_core = _single_role_component(result, "particle_systems", "core")
    reference_core = _single_role_component(reference_graph, "particle_systems", "core")
    target_parameters = target_core.setdefault("parameters", {})
    reference_parameters = reference_core.get("parameters") or {}
    changed_fields: list[str] = []
    for field in CORE_PRIOR_FIELDS:
        if field not in reference_parameters:
            continue
        value = copy.deepcopy(reference_parameters[field])
        if target_parameters.get(field) != value:
            target_parameters[field] = value
            changed_fields.append(f"core.parameters.{field}")
    modules = dict(target_parameters.get("serialized_modules") or {})
    modules.update({
        "professional_teacher_rule_id": rule_id,
        "professional_teacher_rule_scope": "explosion_core_readability",
    })
    target_parameters["serialized_modules"] = modules

    target_renderer = _single_role_component(result, "renderers", "core")
    reference_renderer = _single_role_component(reference_graph, "renderers", "core")
    reference_sort = (reference_renderer.get("parameters") or {}).get("sorting_order")
    if reference_sort is not None:
        target_renderer.setdefault("parameters", {})["sorting_order"] = reference_sort
        changed_fields.append("core.renderer.sorting_order")

    material_path = target_parameters.get("material_template_path")
    bindings = result.setdefault("asset_bindings", {}).setdefault("materials", [])
    if material_path and material_path not in bindings:
        bindings.append(material_path)
        bindings.sort()
        changed_fields.append("asset_bindings.materials")
    result.setdefault("training", {})["aesthetic_label_source"] = "ai_hypothesis"
    result.setdefault("provenance", {}).setdefault("assumptions", []).append(
        f"Verified professional Teacher rule applied as a narrow Controller prior: {rule_id}."
    )
    result.pop("graph_id", None)
    result = assign_graph_id(result)
    _validate_graph(result)
    return result, sorted(set(changed_fields))


def prepare_guided_batch(
    source_manifest_path: Path,
    teacher_ready_path: Path,
    output_root: Path,
    asset_root: str,
    rule_id: str = SUPPORTED_RULE_ID,
) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"guided generation output already exists and is not empty: {output_root}")
    source_manifest = _read_json(source_manifest_path.resolve())
    record, report, reference_graph = _load_teacher_rule(teacher_ready_path, rule_id)
    family = str((source_manifest.get("prompt_condition") or {}).get("effect_type") or ((source_manifest.get("prompt_condition") or {}).get("effect_families") or [""])[0])
    if family != "explosion":
        raise ValueError(f"Teacher rule {rule_id} requires explosion candidates, got {family}")

    candidates = []
    compile_requests = []
    for index, source_candidate in enumerate(source_manifest.get("candidates") or []):
        source_graph_path = _resolve(str(source_candidate["graph_path"]))
        source_graph = _read_json(source_graph_path)
        guided_graph, changed_fields = apply_explosion_core_prior(source_graph, reference_graph, rule_id)
        candidate_id = f"teacher_guided_{index:03d}_{guided_graph['graph_id']}"
        candidate_root = output_root / "candidates" / candidate_id
        graph_path = _write_json(candidate_root / "graph.json", guided_graph)
        prior_path = _write_json(candidate_root / "teacher_prior.json", {
            "schema_version": "vfx_professional_teacher_prior_application.v1",
            "rule_id": rule_id,
            "effect_family": family,
            "judgment_axes": record.get("judgment_axes") or [],
            "expert_judgment": record.get("expert_judgment"),
            "unity_reproduction_report": record.get("unity_reproduction_report"),
            "source_candidate_id": source_candidate["candidate_id"],
            "source_graph_id": source_candidate["graph_id"],
            "guided_graph_id": guided_graph["graph_id"],
            "changed_fields": changed_fields,
            "training_scope": "verified_professional_rule_prior_only_not_aesthetic_quality_label",
        })
        output_prefab = f"{asset_root.rstrip('/')}/{candidate_id}/GeneratedRoot.prefab"
        compile_result = output_root / "compile_results" / f"{candidate_id}.json"
        readback_graph = output_root / "readback" / f"{candidate_id}.json"
        readback_result = output_root / "readback_results" / f"{candidate_id}.json"
        candidates.append({
            "candidate_id": candidate_id,
            "source_candidate_id": source_candidate["candidate_id"],
            "source_graph_id": source_candidate["graph_id"],
            "source_graph_path": _portable(source_graph_path),
            "baseline_capture_manifest_path": source_candidate.get("capture_manifest_path"),
            "guided_graph_id": guided_graph["graph_id"],
            "guided_graph_path": _portable(graph_path),
            "teacher_prior_path": _portable(prior_path),
            "output_prefab_path": output_prefab,
            "compile_result_path": _portable(compile_result),
            "readback_graph_path": _portable(readback_graph),
            "readback_result_path": _portable(readback_result),
            "capture_manifest_path": _portable(output_root / "runtime_captures" / candidate_id / "capture_manifest.json"),
            "changed_fields": changed_fields,
        })
        compile_requests.append({
            "graph_path": graph_path.as_posix(),
            "output_prefab_path": output_prefab,
            "result_path": compile_result.as_posix(),
        })

    manifest_path = _write_json(output_root / "guided_generation_manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": output_root.name,
        "source_manifest_path": _portable(source_manifest_path.resolve()),
        "teacher_ready_path": _portable(teacher_ready_path.resolve()),
        "teacher_rule": {
            "record_id": rule_id,
            "effect_family": family,
            "judgment_axes": record.get("judgment_axes") or [],
            "expert_judgment": record.get("expert_judgment"),
            "reproduction_report": record.get("unity_reproduction_report"),
            "controller_prior": report["validated_controller_prior"],
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "status": "prepared_pending_unity",
    })
    compile_path = _write_json(output_root / "compile_request.json", {
        "schema_version": "vfx_prefab_graph_batch_compile_request.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requests": compile_requests,
    })
    return {"manifest": manifest_path, "compile_request": compile_path}


def prepare_runtime(manifest_path: Path, output_path: Path) -> Path:
    manifest = _read_json(manifest_path.resolve())
    source_manifest = _read_json(_resolve(manifest["source_manifest_path"]))
    source_candidates = {row["candidate_id"]: row for row in source_manifest["candidates"]}
    requests = []
    for candidate in manifest["candidates"]:
        compile_result = _read_json(_resolve(candidate["compile_result_path"]))
        if compile_result.get("status") != "pass":
            raise ValueError(f"passing compile result required: {candidate['candidate_id']}")
        source_candidate = source_candidates[candidate["source_candidate_id"]]
        source_compile_result = _read_json(_resolve(source_candidate["compile_result_path"]))
        if source_compile_result.get("status") != "pass":
            raise ValueError(f"passing baseline compile result required: {candidate['source_candidate_id']}")
        baseline_root = output_path.resolve().parent / "runtime_baselines" / candidate["candidate_id"]
        case_root = output_path.resolve().parent / "runtime_captures" / candidate["candidate_id"]
        requests.append({
            "candidate_id": candidate["source_candidate_id"],
            "prefab_path": source_compile_result["output_prefab_path"],
            "capture_dir": (baseline_root / "captures").as_posix(),
            "capture_manifest_path": (baseline_root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (baseline_root / "material_timeline.json").as_posix(),
            "source_script_fidelity": "generated_graph_no_source_scripts",
            "ignored_script_dependency_count": 0,
            "missing_script_count": 0,
            "capture_category": "explosion",
        })
        requests.append({
            "candidate_id": candidate["source_candidate_id"],
            "prefab_path": compile_result["output_prefab_path"],
            "capture_dir": (case_root / "captures").as_posix(),
            "capture_manifest_path": (case_root / "capture_manifest.json").as_posix(),
            "material_timeline_path": (case_root / "material_timeline.json").as_posix(),
            "source_script_fidelity": "generated_graph_no_source_scripts",
            "ignored_script_dependency_count": 0,
            "missing_script_count": 0,
            "capture_category": "explosion",
        })
    return _write_json(output_path.resolve(), {
        "schema_version": "effectdemo_source_render_requests.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "scene": "ProfessionalTeacherGuidedExplosion",
        "camera": "ProfessionalTeacherGuidedExplosionCamera",
        "width": 512,
        "height": 512,
        "sampling_mode": "adaptive_runtime",
        "sampling": {"target_intervals": 20, "short_effect_target_intervals": 20, "min_interval_seconds": 0.01, "max_interval_seconds": 0.05, "max_duration_seconds": 2.0, "include_zero": True, "duration_sources": ["particle_system"]},
        "capture_material_timeline": True,
        "requests": requests,
    })


def finalize(manifest_path: Path, output_path: Path) -> dict[str, Path]:
    manifest = _read_json(manifest_path.resolve())
    prior = manifest["teacher_rule"]["controller_prior"]
    records = []
    for candidate in manifest["candidates"]:
        compile_result = _read_json(_resolve(candidate["compile_result_path"]))
        readback_result = _read_json(_resolve(candidate["readback_result_path"]))
        recaptured_baseline_path = manifest_path.resolve().parent / "runtime_baselines" / candidate["candidate_id"] / "capture_manifest.json"
        baseline_path = recaptured_baseline_path if recaptured_baseline_path.is_file() else _resolve(candidate["baseline_capture_manifest_path"])
        baseline = _capture_summary(baseline_path)
        guided = _capture_summary(_resolve(candidate["capture_manifest_path"]))
        comparison = _paired_frame_comparison(baseline, guided)
        technical_gates = {
            "compile_pass": compile_result.get("status") == "pass",
            "texture_readback_matches_plan": bool(compile_result.get("planned_texture_readback_match")),
            "prefab_api_readback_pass": readback_result.get("status") == "pass",
            "baseline_runtime_eligible": baseline["image_sequence_training_eligible"],
            "guided_runtime_eligible": guided["image_sequence_training_eligible"],
            "no_guided_material_render_errors": guided["material_render_error_frame_count"] == 0,
            "same_camera_view": bool(baseline["selected_camera_view"]) and baseline["selected_camera_view"] == guided["selected_camera_view"],
            "equal_nonzero_frame_count": baseline["valid_frame_count"] > 0 and baseline["valid_frame_count"] == guided["valid_frame_count"],
            "all_frames_matched_by_time": comparison["matched_frame_count"] == baseline["valid_frame_count"] == guided["valid_frame_count"],
        }
        technical_pass = all(technical_gates.values())
        rule_pass = (
            technical_pass
            and comparison["peak_center_luminance_gain"] >= float(prior["minimum_center_luminance_gain"])
            and comparison["peak_center_local_contrast_gain"] >= float(prior["minimum_center_local_contrast_gain"])
        )
        records.append({
            "candidate_id": candidate["candidate_id"],
            "source_candidate_id": candidate["source_candidate_id"],
            "guided_graph_id": candidate["guided_graph_id"],
            "output_prefab_path": candidate["output_prefab_path"],
            "compile_status": compile_result.get("status"),
            "texture_readback_match": bool(compile_result.get("planned_texture_readback_match")),
            "prefab_api_readback_status": readback_result.get("status"),
            "runtime_visual_status": guided["visual_evidence_status"],
            "valid_frame_count": guided["valid_frame_count"],
            "technical_gates": technical_gates,
            "technical_pass": technical_pass,
            "professional_rule_transfer_pass": rule_pass,
            "peak_center_luminance_gain": comparison["peak_center_luminance_gain"],
            "peak_center_local_contrast_gain": comparison["peak_center_local_contrast_gain"],
            "best_time_seconds": comparison["best_time_seconds"],
            "best_baseline_frame_path": comparison["best_empty_frame_path"],
            "best_guided_frame_path": comparison["best_reinforced_frame_path"],
            "training_eligibility": {
                "eligible_tasks": ["explosion_core_rule_controller"] if rule_pass else [],
                "excluded_tasks": ["full_aesthetic_judge", "positive_generation_supervision", "general_quality_head"],
                "label_scope": "professional_rule_transfer_evidence_not_global_quality",
            },
        })
    ranking = sorted(records, key=lambda row: (-float(row["peak_center_local_contrast_gain"]), -float(row["peak_center_luminance_gain"]), row["candidate_id"]))
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": manifest["run_id"],
        "teacher_rule": manifest["teacher_rule"],
        "candidate_count": len(records),
        "technical_pass_count": sum(row["technical_pass"] for row in records),
        "professional_rule_transfer_pass_count": sum(row["professional_rule_transfer_pass"] for row in records),
        "records": records,
        "status": "pass" if records and all(row["technical_pass"] for row in records) and any(row["professional_rule_transfer_pass"] for row in records) else "blocked",
        "training_scope": "narrow explosion core-readability Controller evidence only",
    }
    report_path = _write_json(output_path.resolve(), report)
    ranking_path = _write_jsonl(output_path.resolve().parent / "teacher_rule_ranking.jsonl", ranking)
    return {"report": report_path, "ranking": ranking_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply a verified professional Teacher rule to generated PrefabGraphs.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("--source-manifest", type=Path, required=True)
    prepare_command.add_argument("--teacher-ready", type=Path, required=True)
    prepare_command.add_argument("--output-root", type=Path, required=True)
    prepare_command.add_argument("--asset-root", required=True)
    prepare_command.add_argument("--rule-id", default=SUPPORTED_RULE_ID)
    runtime_command = commands.add_parser("prepare-runtime")
    runtime_command.add_argument("--manifest", type=Path, required=True)
    runtime_command.add_argument("--output", type=Path, required=True)
    finalize_command = commands.add_parser("finalize")
    finalize_command.add_argument("--manifest", type=Path, required=True)
    finalize_command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            paths = prepare_guided_batch(args.source_manifest, args.teacher_ready, args.output_root, args.asset_root, args.rule_id)
        elif args.command == "prepare-runtime":
            paths = {"runtime_request": prepare_runtime(args.manifest, args.output)}
        else:
            paths = finalize(args.manifest, args.output)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
