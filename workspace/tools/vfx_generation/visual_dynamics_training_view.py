"""Assemble technical visual-dynamics features without inventing aesthetic labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from workspace.tools.vfx_training_features import aggregate_image_features


SCHEMA_VERSION = "vfx_visual_dynamics_training_view.v1"
PIPELINE_VERSION = "play_mode_runtime_isolated_multiview.v2"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _resolve(value: str, base: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _split(group_id: str) -> str:
    bucket = int(hashlib.sha256(f"visual_dynamics_split.v1|{group_id}".encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def _timeline_features(path: Path) -> dict[str, Any]:
    timeline = _read(path)
    summary = timeline.get("summary") if isinstance(timeline.get("summary"), dict) else {}
    return {
        "frame_count": int(summary.get("frame_count") or len(timeline.get("frames") or [])),
        "delta_count": int(summary.get("delta_count") or 0),
        "changed_frame_count": int(summary.get("changed_frame_count") or 0),
        "has_dynamic_material_state": bool(summary.get("has_dynamic_material_state")),
        "has_unenumerated_property_block_values": bool(summary.get("has_unenumerated_property_block_values")),
        "global_shader_state_status": str(summary.get("global_shader_state_status") or "not_available"),
        "global_shader_value_count": int(summary.get("global_shader_value_count") or 0),
        "global_shader_delta_count": int(summary.get("global_shader_delta_count") or 0),
        "signal_counts": list(summary.get("signal_counts") or []),
        "capture_error": timeline.get("capture_error") or None,
    }


def _image_features(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    capture_root = _resolve(str(manifest.get("capture_root") or "captures"), manifest_path.parent)
    frames = [frame for frame in manifest.get("frames") or [] if frame.get("valid") is True and frame.get("path")]
    frame_paths = [_resolve(str(frame["path"]), capture_root) for frame in frames]
    missing = [path.as_posix() for path in frame_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"valid visual frame is missing: {missing[0]}")
    return {
        "features": aggregate_image_features(frame_paths, [float(frame.get("requested_time_seconds") or 0.0) for frame in frames]),
        "frame_count": len(frames),
        "missing_frame_count": len(missing),
        "frame_paths": [path.as_posix() for path in frame_paths],
    }


def _generated_rows(manifest_paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for manifest_path in manifest_paths:
        manifest = _read(manifest_path)
        for candidate in manifest.get("candidates") or []:
            capture_path = _resolve(str(candidate.get("capture_manifest_path") or ""), manifest_path.parent)
            timeline_path = capture_path.parent / "material_timeline.json"
            if not capture_path.is_file() or not timeline_path.is_file():
                continue
            capture = _read(capture_path)
            integrity_error = int(capture.get("material_render_error_frame_count") or 0) > 0 or capture.get("visual_evidence_status") == "material_render_error"
            image = _image_features(capture_path, capture)
            if not capture.get("image_sequence_training_eligible") or integrity_error or max((float((frame.get("pixel_metrics") or {}).get("visible_area_ratio") or 0.0) for frame in capture.get("frames") or []), default=0.0) < 0.001:
                continue
            timeline = _timeline_features(timeline_path)
            condition = manifest.get("prompt_condition") or {}
            effect_type = str(condition.get("effect_type") or (condition.get("effect_families") or ["unknown"])[0])
            rows.append({
                "record_id": f"generated_{candidate['candidate_id']}",
                "sample_kind": "generated_prefab",
                "candidate_id": candidate["candidate_id"],
                "run_id": manifest.get("run_id"),
                "prompt": condition.get("text"),
                "effect_element_tags": list(condition.get("effect_element_tags") or []),
                "effect_type": effect_type,
                "style_family": condition.get("style_family") or "unknown",
                "color_tags": list(condition.get("color_keywords") or []),
                "layer_roles": ["core", "support", "hit"],
                "group_id": f"prompt:{manifest.get('run_id')}|type:{effect_type}",
                "split": _split(f"prompt:{manifest.get('run_id')}|type:{effect_type}"),
                "image_features": image["features"],
                "image_frame_count": image["frame_count"],
                "material_timeline": timeline,
                "evidence": {"capture_manifest_path": capture_path.as_posix(), "material_timeline_path": timeline_path.as_posix(), "graph_path": candidate.get("graph_path"), "asset_plan_path": candidate.get("asset_plan_path"), "capture_pipeline_version": capture.get("capture_pipeline_version")},
                "quality_label": None,
                "quality_label_source": "blocked_no_professional_teacher",
                "technical_dynamic_targets": {"has_dynamic_material_state": timeline["has_dynamic_material_state"], "delta_count": timeline["delta_count"], "global_shader_state_status": timeline["global_shader_state_status"]},
            })
    return rows


def _material_rows(dataset_root: Path) -> list[dict[str, Any]]:
    rows = []
    examples_path = dataset_root / "image_conditioned_examples.jsonl"
    for example in _read_jsonl(examples_path):
        outputs = example.get("outputs") or {}
        render_paths = [str(value) for value in outputs.get("render_paths") or []]
        timeline_path = _repo_root() / str(example.get("inputs", {}).get("material_timeline_path") or "")
        if not render_paths or not timeline_path.is_file():
            continue
        frame_paths = [_repo_root() / path for path in render_paths]
        if any(not path.is_file() for path in frame_paths):
            continue
        timeline = _timeline_features(timeline_path)
        inputs = example.get("inputs") or {}
        source = inputs.get("source_asset") or {}
        type_candidates = list(source.get("effect_families") or [])
        effect_type = next((value for value in type_candidates if value != "unclassified"), "unknown")
        group_id = str((example.get("split") or {}).get("shader_group") or example.get("candidate_id"))
        rows.append({
            "record_id": f"trajectory_{example['example_id']}",
            "sample_kind": "material_trajectory",
            "candidate_id": example.get("candidate_id"),
            "run_id": example.get("run_id"),
            "prompt": "",
            "effect_element_tags": [],
            "effect_type": effect_type,
            "style_family": (inputs.get("target_style_profile") or {}).get("family") or "unknown",
            "color_tags": [],
            "layer_roles": [],
            "group_id": group_id,
            "split": (example.get("split") or {}).get("name") or _split(group_id),
            "image_features": aggregate_image_features(frame_paths, [float(index) for index in range(len(frame_paths))]),
            "image_frame_count": len(frame_paths),
            "material_timeline": timeline,
            "evidence": {"material_timeline_path": timeline_path.as_posix(), "trajectory_category": example.get("inputs", {}).get("trajectory_category"), "execution_result_path": example.get("inputs", {}).get("execution_result_path")},
            "quality_label": None,
            "quality_label_source": "blocked_no_professional_teacher",
            "technical_dynamic_targets": {"has_dynamic_material_state": timeline["has_dynamic_material_state"], "delta_count": timeline["delta_count"], "actual_signals": list(example.get("outputs", {}).get("actual_signals") or [])},
        })
    return rows


def _capture_rows(capture_roots: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for root in capture_roots:
        for capture_path in root.resolve().rglob("capture_manifest.json"):
            capture = _read(capture_path)
            timeline_path = capture_path.parent / "material_timeline.json"
            if not timeline_path.is_file() or capture.get("capture_pipeline_version") != PIPELINE_VERSION:
                continue
            if not capture.get("image_sequence_training_eligible") or capture.get("render_error") or int(capture.get("material_render_error_frame_count") or 0) > 0:
                continue
            image = _image_features(capture_path, capture)
            timeline = _timeline_features(timeline_path)
            effect = str(capture.get("effect") or capture_path.parent.name)
            category = str(capture.get("capture_category") or "unknown")
            group_id = f"capture:{effect.casefold()}|category:{category}"
            rows.append({
                "record_id": "capture_" + hashlib.sha256(f"{root.resolve()}|{effect}|{category}".encode("utf-8")).hexdigest()[:20],
                "sample_kind": "runtime_capture_probe" if effect.startswith("__effectdemo_") else "source_prefab_capture",
                "candidate_id": capture_path.parent.name,
                "run_id": root.name,
                "prompt": "",
                "effect_element_tags": [],
                "effect_type": "impact" if category in {"instant", "script_material"} else "unknown",
                "style_family": "unknown",
                "color_tags": [],
                "layer_roles": [],
                "group_id": group_id,
                "split": _split(group_id),
                "image_features": image["features"],
                "image_frame_count": image["frame_count"],
                "material_timeline": timeline,
                "evidence": {"capture_manifest_path": capture_path.as_posix(), "material_timeline_path": timeline_path.as_posix(), "capture_pipeline_version": capture.get("capture_pipeline_version"), "visual_evidence_status": capture.get("visual_evidence_status"), "full_visual_training_eligible": bool(capture.get("full_visual_training_eligible"))},
                "quality_label": None,
                "quality_label_source": "blocked_no_professional_teacher",
                "technical_dynamic_targets": {"has_dynamic_material_state": timeline["has_dynamic_material_state"], "delta_count": timeline["delta_count"], "global_shader_state_status": timeline["global_shader_state_status"], "global_shader_delta_count": timeline["global_shader_delta_count"], "full_visual_training_eligible": bool(capture.get("full_visual_training_eligible"))},
            })
    return rows


def build_view(material_dataset_root: Path, generated_manifests: list[Path], teacher_readiness_manifest: Path, output_root: Path, view_id: str = "visual_dynamics_training_view_r001", capture_roots: list[Path] | None = None) -> dict[str, Path]:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"visual dynamics output already exists and is not empty: {output_root}")
    readiness = _read(teacher_readiness_manifest.resolve())
    teacher_ready_count = int(readiness.get("teacher_ready_count") or 0)
    rows = [*_material_rows(material_dataset_root.resolve()), *_generated_rows([path.resolve() for path in generated_manifests]), *_capture_rows(capture_roots or [])]
    if not rows:
        raise ValueError("visual dynamics view has no eligible technical rows")
    group_splits: dict[str, str] = {}
    for row in rows:
        previous = group_splits.setdefault(str(row["group_id"]), str(row["split"]))
        if previous != row["split"]:
            raise ValueError(f"visual dynamics group crosses splits: {row['group_id']}")
    split_overlap = sum(bool({row["group_id"] for row in rows if row["split"] == left} & {row["group_id"] for row in rows if row["split"] == right}) for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")))
    technical_exclusions = sum(int(row["image_frame_count"] <= 0 or bool(row["material_timeline"].get("capture_error"))) for row in rows)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "view_id": view_id,
        "source_material_dataset_id": _read(material_dataset_root / "dataset_manifest.json").get("dataset_id"),
        "source_generated_manifest_ids": [_read(path.resolve()).get("run_id") for path in generated_manifests],
        "source_capture_roots": [path.resolve().as_posix() for path in (capture_roots or [])],
        "teacher_readiness_manifest": teacher_readiness_manifest.resolve().as_posix(),
        "record_count": len(rows),
        "split_counts": {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")},
        "sample_kind_counts": dict(sorted(Counter(row["sample_kind"] for row in rows).items())),
        "effect_type_counts": dict(sorted(Counter(row["effect_type"] for row in rows).items())),
        "style_family_counts": dict(sorted(Counter(row["style_family"] for row in rows).items())),
        "teacher_ready_count": teacher_ready_count,
        "files": {"records": "records.jsonl"},
        "quality_gates": {"missing_frame_count": 0, "technical_exclusion_count": technical_exclusions, "group_split_overlap_count": split_overlap, "professional_quality_labels_consumed": 0, "aesthetic_quality_training_status_blocked": teacher_ready_count == 0, "all_capture_v2_generated_rows": all(row["sample_kind"] != "generated_prefab" or row["evidence"].get("capture_pipeline_version") == PIPELINE_VERSION for row in rows)},
        "training_policy": {"technical_dynamic_self_supervision": True, "image_feature_self_supervision": True, "professional_teacher_required_for_quality_head": True, "nonexpert_aesthetic_feedback_consumed": False, "visible_is_not_quality": True},
        "status": "pass_technical_self_supervision_quality_head_blocked" if teacher_ready_count == 0 else "pass",
    }
    if technical_exclusions or split_overlap or not manifest["quality_gates"]["all_capture_v2_generated_rows"]:
        raise ValueError(f"visual dynamics quality gate failed: {manifest['quality_gates']}")
    schema = _read(_repo_root() / "workspace/data/vfx_generation/schemas/visual_dynamics_training_view.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"visual dynamics manifest schema error: {errors[0].message}")
    records_path = _write_jsonl(output_root / "records.jsonl", rows)
    manifest_path = _write(output_root / "dataset_manifest.json", manifest)
    card_path = output_root / "TRAINING_VIEW.md"
    card_path.write_text(f"""# {view_id}\n\nThis view contains continuous-frame image features and runtime material-state evidence for technical self-supervision. It has `{teacher_ready_count}` professional Teacher-ready records, so the aesthetic quality head is blocked and no quality label is emitted.\n\nUse it to pretrain temporal/material-state representations only. Do not promote technical visibility, dynamic state or rule scores to an aesthetic quality label.\n""", encoding="utf-8")
    return {"manifest": manifest_path, "records": records_path, "training_view": card_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a technical visual-dynamics training view.")
    parser.add_argument("--material-dataset-root", type=Path, required=True)
    parser.add_argument("--generated-manifest", type=Path, action="append", default=[])
    parser.add_argument("--capture-root", type=Path, action="append", default=[])
    parser.add_argument("--teacher-readiness-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--view-id", default="visual_dynamics_training_view_r001")
    args = parser.parse_args(argv)
    try:
        paths = build_view(args.material_dataset_root, args.generated_manifest, args.teacher_readiness_manifest, args.output_root, args.view_id, args.capture_root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
