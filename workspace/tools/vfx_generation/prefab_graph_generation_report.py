"""Finalize a generated PrefabGraph run without turning technical failures into labels."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .capture_visual_integrity import analyze_capture_manifest


REPORT_SCHEMA = "vfx_prefab_graph_generation_report.v1"
PIPELINE_VERSION = "play_mode_runtime_isolated_multiview.v2"


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _validate(value: dict[str, Any], schema_name: str, label: str) -> None:
    schema = _read(_repo_root() / "workspace/data/vfx_generation/schemas" / schema_name)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _max_visible(capture: dict[str, Any]) -> float:
    return max((float((frame.get("pixel_metrics") or {}).get("visible_area_ratio") or 0.0) for frame in capture.get("frames") or []), default=0.0)


def _training_eligibility(capture: dict[str, Any], integrity: dict[str, Any], compile_result: dict[str, Any], readback: dict[str, Any]) -> tuple[bool, str | None]:
    if compile_result.get("status") != "pass":
        return False, "unity_compile_failed"
    if readback.get("status") != "pass" or readback.get("differences"):
        return False, "unity_api_readback_mismatch"
    if capture.get("capture_pipeline_version") != PIPELINE_VERSION:
        return False, "capture_pipeline_mismatch"
    if int(capture.get("invalid_frame_count") or 0) > 0 or not capture.get("technical_frame_eligible"):
        return False, "invalid_runtime_capture"
    if integrity.get("material_render_error"):
        return False, "material_render_error"
    if not capture.get("image_sequence_training_eligible"):
        if capture.get("visual_evidence_status") == "near_blank":
            return False, "near_blank"
        return False, "image_sequence_not_eligible"
    return True, None


def finalize_generation_run(
    decode_path: Path,
    upgrade_manifest_path: Path,
    compile_results_root: Path,
    readback_root: Path,
    capture_root: Path,
    output_root: Path,
) -> dict[str, Path]:
    decode_path = decode_path.resolve()
    upgrade_manifest_path = upgrade_manifest_path.resolve()
    compile_results_root = compile_results_root.resolve()
    readback_root = readback_root.resolve()
    capture_root = capture_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"generation report output already exists and is not empty: {output_root}")

    decode = _read(decode_path)
    upgrade = _read(upgrade_manifest_path)
    if decode.get("status") != "pass" or decode.get("schema_version") != "vfx_prefab_graph_constrained_decode.v1":
        raise ValueError(f"verified constrained decode expected: {decode_path}")
    if upgrade.get("status") != "pass" or upgrade.get("schema_version") != "vfx_prefab_graph_asset_upgrade.v1":
        raise ValueError(f"verified asset upgrade expected: {upgrade_manifest_path}")

    decode_candidates = list(decode.get("candidates") or [])
    upgrade_candidates = list(upgrade.get("candidates") or [])
    if not decode_candidates or len(decode_candidates) != len(upgrade_candidates):
        raise ValueError("decode and asset upgrade candidate counts do not match")
    if [row.get("profile") for row in decode_candidates] != [row.get("profile") for row in upgrade_candidates]:
        raise ValueError("decode and asset upgrade candidate profiles do not match")
    records: list[dict[str, Any]] = []
    limitations: set[str] = set()
    for decode_candidate, upgrade_candidate in zip(decode_candidates, upgrade_candidates):
        candidate_id = str(upgrade_candidate.get("candidate_id") or "")
        if not candidate_id:
            raise ValueError("asset upgrade candidate_id is missing")
        compile_path = compile_results_root / f"{candidate_id}.json"
        readback_path = readback_root / f"{candidate_id}.result.json"
        capture_path = capture_root / "cases" / candidate_id / "capture_manifest.json"
        timeline_path = capture_root / "cases" / candidate_id / "material_timeline.json"
        for required in (compile_path, readback_path, capture_path, timeline_path):
            if not required.is_file():
                raise FileNotFoundError(f"generated candidate output is missing: {required}")
        compile_result = _read(compile_path)
        readback = _read(readback_path)
        capture = _read(capture_path)
        integrity = analyze_capture_manifest(capture_path, capture)
        generated_textures = set(str(value) for value in compile_result.get("generated_texture_paths") or [])
        bound_textures = set(str(value) for value in compile_result.get("bound_texture_paths") or [])
        readback_textures = {str(value.get("texture_path")) for value in compile_result.get("material_texture_readbacks") or [] if value.get("texture_path")}
        texture_binding_match = bool(compile_result.get("planned_texture_readback_match")) and generated_textures <= bound_textures and generated_textures <= readback_textures
        eligible, exclusion_reason = _training_eligibility(capture, integrity, compile_result, readback)
        if not texture_binding_match:
            eligible = False
            exclusion_reason = "texture_binding_readback_mismatch"
        max_visible = _max_visible(capture)
        if exclusion_reason:
            limitations.add(exclusion_reason)
        records.append({
            "candidate_id": candidate_id,
            "source_decode_candidate_id": decode_candidate.get("candidate_id"),
            "profile": upgrade_candidate.get("profile"),
            "graph_path": upgrade_candidate.get("graph_path"),
            "asset_plan_path": upgrade_candidate.get("asset_plan_path"),
            "compile_result_path": _portable(compile_path),
            "readback_result_path": _portable(readback_path),
            "capture_manifest_path": _portable(capture_path),
            "material_timeline_path": _portable(timeline_path),
            "compile_status": compile_result.get("status"),
            "readback_status": readback.get("status"),
            "unity_api_readback": readback.get("unity_api_readback") is True and not readback.get("differences"),
            "parent_prefab_path": upgrade_candidate.get("parent_prefab_path"),
            "generated_texture_count": len(generated_textures),
            "bound_texture_count": len(bound_textures),
            "texture_readback_count": len(readback_textures),
            "texture_binding_readback_match": texture_binding_match,
            "capture_pipeline_version": capture.get("capture_pipeline_version"),
            "frame_count": len(capture.get("frames") or []),
            "valid_frame_count": int(capture.get("valid_frame_count") or 0),
            "duration_seconds": capture.get("duration_seconds"),
            "sample_interval_seconds": capture.get("sample_interval_seconds"),
            "max_visible_area_ratio": max_visible,
            "material_render_error": integrity.get("material_render_error") is True,
            "material_render_error_frame_count": integrity.get("error_magenta_frame_count", 0),
            "visual_evidence_status": capture.get("visual_evidence_status"),
            "camera_selection_status": (capture.get("camera_selection") or {}).get("status"),
            "context_status": (capture.get("context") or {}).get("status"),
            "image_sequence_training_eligible": capture.get("image_sequence_training_eligible") is True,
            "full_visual_training_eligible": capture.get("full_visual_training_eligible") is True,
            "eligible_for_visual_training": eligible,
            "exclusion_reason": exclusion_reason,
            "aesthetic_label_source": "none",
            "training_scope": "technical_generation_and_runtime_visual_self_supervision; no human aesthetic or preference supervision",
        })

    all_parentless = all(row["parent_prefab_path"] is None for row in records)
    all_compile_pass = all(row["compile_status"] == "pass" for row in records)
    all_readback_pass = all(row["unity_api_readback"] for row in records)
    all_texture_bindings = all(row["texture_binding_readback_match"] for row in records)
    all_capture_manifests = all(row["frame_count"] > 0 for row in records)
    all_pipeline_v2 = all(row["capture_pipeline_version"] == PIPELINE_VERSION for row in records)
    all_frames_valid = all(row["frame_count"] == row["valid_frame_count"] for row in records)
    no_material_errors = all(not row["material_render_error"] for row in records)
    gates = {
        "decode_asset_candidate_alignment": True,
        "all_parent_prefab_paths_null": all_parentless,
        "all_compile_pass": all_compile_pass,
        "all_texture_bindings_verified": all_texture_bindings,
        "all_unity_api_readbacks_pass": all_readback_pass,
        "all_capture_manifests_present": all_capture_manifests,
        "all_capture_pipeline_v2": all_pipeline_v2,
        "all_runtime_frames_valid": all_frames_valid,
        "no_material_render_errors": no_material_errors,
        "aesthetic_labels_consumed": False,
        "visual_training_candidates_present": any(row["eligible_for_visual_training"] for row in records),
    }
    if not all(value for key, value in gates.items() if key != "aesthetic_labels_consumed") or gates["aesthetic_labels_consumed"]:
        raise ValueError(f"generated PrefabGraph report quality gate failed: {gates}")

    training_ready = [row for row in records if row["eligible_for_visual_training"]]
    technical_only = [row for row in records if not row["eligible_for_visual_training"]]
    records_path = _write_jsonl(output_root / "records.jsonl", records)
    training_path = _write_jsonl(output_root / "training_ready.jsonl", training_ready)
    technical_path = _write_jsonl(output_root / "technical_exclusions.jsonl", technical_only)
    report = {
        "schema_version": REPORT_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": capture_root.name,
        "decode_path": _portable(decode_path),
        "asset_upgrade_manifest_path": _portable(upgrade_manifest_path),
        "candidate_count": len(records),
        "compiled_count": sum(row["compile_status"] == "pass" for row in records),
        "unity_api_readback_pass_count": sum(row["unity_api_readback"] for row in records),
        "runtime_capture_count": sum(row["frame_count"] > 0 for row in records),
        "visual_training_candidate_count": len(training_ready),
        "technical_exclusion_count": len(technical_only),
        "full_visual_candidate_count": sum(row["full_visual_training_eligible"] for row in records),
        "valid_frame_count": sum(row["valid_frame_count"] for row in records),
        "candidates": records,
        "files": {"records": _portable(records_path), "training_ready": _portable(training_path), "technical_exclusions": _portable(technical_path)},
        "quality_gates": gates,
        "limitations": sorted(limitations),
        "status": "pass",
    }
    _validate(report, "prefab_graph_generation_report.schema.json", "generated PrefabGraph report")
    report_path = _write(output_root / "generation_report.json", report)
    return {"report": report_path, "records": records_path, "training_ready": training_path, "technical_exclusions": technical_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize a generated PrefabGraph run.")
    parser.add_argument("--decode", type=Path, required=True)
    parser.add_argument("--asset-upgrade", type=Path, required=True)
    parser.add_argument("--compile-results", type=Path, required=True)
    parser.add_argument("--readback-results", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = finalize_generation_run(args.decode, args.asset_upgrade, args.compile_results, args.readback_results, args.capture_root, args.output_root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
