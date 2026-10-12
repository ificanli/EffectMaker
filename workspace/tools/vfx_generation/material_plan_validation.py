"""Assemble Unity compile/readback/Capture v2 outcomes into MaterialPlan technical supervision."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _schema(name: str) -> dict[str, Any]:
    return _read_json(_repo_root() / "workspace/data/vfx_generation/schemas" / name)


def _capture_counts(root: Path | None) -> tuple[int, int]:
    if root is None:
        return 0, 0
    count = 0
    visible = 0
    for path in root.resolve().rglob("capture_manifest.json"):
        capture = _read_json(path)
        count += 1
        peak = max((float((frame.get("pixel_metrics") or {}).get("visible_area_ratio") or 0.0) for frame in capture.get("frames") or []), default=0.0)
        visible += peak >= 0.001 and capture.get("image_sequence_training_eligible") is True
    return count, int(visible)


def build_validation(manifest_paths: Iterable[Path], output_root: Path, validation_id: str, baseline_capture_root: Path | None = None) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"MaterialPlan validation output already exists and is not empty: {output_root}")
    plan_validator = Draft202012Validator(_schema("material_plan.schema.json"))
    record_validator = Draft202012Validator(_schema("material_plan_validation_record.schema.json"))
    records = []
    plan_errors = []
    for manifest_path in manifest_paths:
        manifest_path = manifest_path.resolve()
        manifest = _read_json(manifest_path)
        family = str((manifest.get("prompt_condition", {}).get("effect_families") or ["unknown"])[0])
        for candidate in manifest.get("candidates") or []:
            plan_path = Path(candidate["asset_plan_path"]).resolve()
            plan = _read_json(plan_path)
            plan_errors.extend(plan_validator.iter_errors(plan))
            compile_path = Path(str(candidate.get("compile_result_path") or ""))
            capture_path = Path(str(candidate.get("capture_manifest_path") or ""))
            compile_result = _read_json(compile_path) if compile_path.is_file() else {}
            capture = _read_json(capture_path) if capture_path.is_file() else {}
            peak = max((float((frame.get("pixel_metrics") or {}).get("visible_area_ratio") or 0.0) for frame in capture.get("frames") or []), default=0.0)
            if compile_result.get("status") != "pass":
                label = "compile_failed"
            elif capture.get("render_error") or int(capture.get("invalid_frame_count") or 0) > 0:
                label = "capture_failed"
            elif peak >= 0.001 and capture.get("image_sequence_training_eligible") is True:
                label = "visible"
            else:
                label = "near_blank"
            selected_pairs = []
            for layer in plan.get("layers") or []:
                selected = next((row for row in layer.get("candidates") or [] if row["candidate_id"] == layer.get("selected_candidate_id")), None)
                if selected:
                    selected_pairs.append({"component_id": layer["component_id"], "layer_role": layer["layer_role"], "material": selected["material"], "shader": selected["shader"], "texture": selected["texture"], "texture_property_name": selected["texture_property_name"], "plan_scores": selected["scores"]})
            record = {
                "schema_version": "vfx_material_plan_validation_record.v1",
                "validation_id": validation_id,
                "candidate_id": candidate["candidate_id"],
                "effect_family": family,
                "plan_path": _portable(plan_path),
                "graph_path": _portable(Path(candidate["graph_path"])),
                "prefab_path": compile_result.get("output_prefab_path"),
                "selected_pairs": selected_pairs,
                "compile": {"status": compile_result.get("status") or "missing", "planned_texture_readback_match": bool(compile_result.get("planned_texture_readback_match")), "bound_texture_paths": list(compile_result.get("bound_texture_paths") or []), "generated_texture_paths": list(compile_result.get("generated_texture_paths") or [])},
                "capture": {"pipeline_version": capture.get("capture_pipeline_version"), "valid_frame_count": int(capture.get("valid_frame_count") or 0), "invalid_frame_count": int(capture.get("invalid_frame_count") or 0), "max_visible_area_ratio": peak, "image_sequence_training_eligible": bool(capture.get("image_sequence_training_eligible")), "manifest_path": _portable(capture_path) if capture_path.is_file() else None},
                "technical_label": label,
                "training": {"eligible_tasks": ["material_pair_visibility", "asset_pairing_rank"] if label in {"visible", "near_blank"} else ["material_pair_failure"], "excluded_tasks": ["aesthetic_judge", "human_gold", "positive_generation_supervision", "preference_training", "regression_evaluation"], "weight": 1.0},
                "aesthetic_label_source": "none",
            }
            errors = list(record_validator.iter_errors(record))
            if errors:
                raise ValueError(f"MaterialPlan validation record schema error for {candidate['candidate_id']}: {errors[0].message}")
            records.append(record)
    candidate_ids = [row["candidate_id"] for row in records]
    baseline_count, baseline_visible = _capture_counts(baseline_capture_root)
    current_visible = sum(row["technical_label"] == "visible" for row in records)
    records_path = _write_jsonl(output_root / "records.jsonl", records)
    visible_path = _write_jsonl(output_root / "visible_pairs.jsonl", (row for row in records if row["technical_label"] == "visible"))
    negative_path = _write_jsonl(output_root / "technical_negatives.jsonl", (row for row in records if row["technical_label"] != "visible"))
    gates = {
        "schema_errors": 0,
        "duplicate_candidate_ids": len(candidate_ids) - len(set(candidate_ids)),
        "plan_schema_errors": len(plan_errors),
        "planned_texture_readback_failures": sum(row["compile"]["status"] == "pass" and not row["compile"]["planned_texture_readback_match"] for row in records),
        "capture_v2_count_mismatch": sum(row["compile"]["status"] == "pass" and row["capture"]["pipeline_version"] != "play_mode_runtime_isolated_multiview.v2" for row in records),
        "aesthetic_labels_consumed": 0,
    }
    if any(gates.values()):
        raise ValueError(f"MaterialPlan validation quality gate failed: {gates}")
    manifest = {
        "schema_version": "vfx_material_plan_validation_manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "validation_id": validation_id,
        "record_count": len(records),
        "effect_family_counts": dict(sorted(Counter(row["effect_family"] for row in records).items())),
        "technical_label_counts": dict(sorted(Counter(row["technical_label"] for row in records).items())),
        "baseline_comparison": {"baseline_capture_count": baseline_count, "baseline_visible_count": baseline_visible, "current_capture_count": len(records), "current_visible_count": current_visible, "visible_count_delta": current_visible - baseline_visible},
        "files": {"records": _portable(records_path), "visible_pairs": _portable(visible_path), "technical_negatives": _portable(negative_path)},
        "quality_gates": gates,
        "status": "pass",
    }
    manifest_errors = list(Draft202012Validator(_schema("material_plan_validation_manifest.schema.json")).iter_errors(manifest))
    if manifest_errors:
        raise ValueError(f"MaterialPlan validation manifest schema error: {manifest_errors[0].message}")
    manifest_path = _write_json(output_root / "validation_manifest.json", manifest)
    return {"manifest": manifest_path, "records": records_path, "visible_pairs": visible_path, "technical_negatives": negative_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build MaterialPlan technical supervision from Unity evidence.")
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--validation-id", required=True)
    parser.add_argument("--baseline-capture-root", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = build_validation(args.manifest, args.output_root, args.validation_id, args.baseline_capture_root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
