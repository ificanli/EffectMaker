"""Export VFX Controller examples and MiniMind-compatible SFT records safely."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


CONDITION_FIELDS = ("风格", "主色", "特效类别", "节奏", "无长拖尾", "整体")
KNOWN_CHOICES = {"符合", "部分符合", "不符合"}
MINIMUM_SFT_EXAMPLES = 32
MINIMUM_SFT_FAMILIES = 2


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    root = _repo_root().resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _load_overlays(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    overlays: dict[str, dict[str, Any]] = {}
    for path in paths:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"condition overlay does not exist: {path}")
        for row in _read_jsonl(path):
            candidate_id = str(row.get("candidate_id") or "")
            if not candidate_id or candidate_id in overlays:
                raise ValueError(f"duplicate or empty condition overlay candidate: {candidate_id}")
            overlays[candidate_id] = row
    return overlays


def _resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _load_course_adapter_candidates(
    course_adapter_paths: Iterable[Path],
) -> list[tuple[dict[str, Any], dict[str, Any], Path, str]]:
    candidates: list[tuple[dict[str, Any], dict[str, Any], Path, str]] = []
    for raw_path in course_adapter_paths:
        adapter_path = raw_path.resolve()
        adapter = _read_json(adapter_path)
        candidate_filename = str(adapter.get("files", {}).get("controller_candidates") or "")
        if not candidate_filename:
            raise ValueError(f"course adapter manifest has no controller_candidates file: {adapter_path}")
        candidates_path = (adapter_path.parent / candidate_filename).resolve()
        if not candidates_path.is_file():
            raise FileNotFoundError(f"course controller candidates do not exist: {candidates_path}")
        for course_candidate in _read_jsonl(candidates_path):
            candidate_id = str(course_candidate.get("candidate_id") or "")
            if not candidate_id:
                raise ValueError(f"course controller candidate has no candidate_id: {candidates_path}")
            course_input = course_candidate.get("input") if isinstance(course_candidate.get("input"), dict) else {}
            course_target = course_candidate.get("target") if isinstance(course_candidate.get("target"), dict) else {}
            course_provenance = course_candidate.get("provenance") if isinstance(course_candidate.get("provenance"), dict) else {}
            family = str(course_input.get("effect_family") or "unknown")
            candidates.append((
                adapter,
                {
                    "candidate_id": candidate_id,
                    "source_prefab": {},
                    "material_trajectory": {"trajectory_id": candidate_id, "category": "course_prior", "control_scope": "vfxspec"},
                    "execution_status": "not_run",
                    "visual_status": "not_available",
                    "max_visible_area_ratio": None,
                    "resource_clean": False,
                    "prompt_conditions_unscored": ["课程先验不是生成结果，尚无人类Prompt条件评价"],
                    "course_input": course_input,
                    "course_target": course_target,
                    "course_provenance": course_provenance,
                },
                adapter_path,
                "course_prior",
            ))
    return candidates


def _load_candidate_manifests(
    composition_paths: Iterable[Path],
    variation_paths: Iterable[Path],
    course_adapter_paths: Iterable[Path],
) -> list[tuple[dict[str, Any], dict[str, Any], Path, str]]:
    candidates: list[tuple[dict[str, Any], dict[str, Any], Path, str]] = []
    for path in composition_paths:
        path = path.resolve()
        manifest = _read_json(path)
        for candidate in manifest.get("candidates", []):
            candidates.append((manifest, candidate, path, "composition"))
    for path in variation_paths:
        path = path.resolve()
        manifest = _read_json(path)
        proposal_path = _resolve_repo_path(str(manifest["proposal_manifest"]))
        proposal = _read_json(proposal_path)
        result_path = _resolve_repo_path(str(manifest["execution_result_path"]))
        result = _read_json(result_path)
        frame_paths = [result_path.parent / "frames" / str(frame.get("path") or "") for frame in result.get("frames", []) if isinstance(frame, dict)]
        frames_valid = bool(frame_paths) and all(path.is_file() for path in frame_paths) and int(result.get("valid_frame_count") or 0) == len(frame_paths)
        candidate = {
            "candidate_id": manifest["proposal_id"],
            "source_prefab": proposal["source_prefab"],
            "material_trajectory": {"trajectory_id": manifest["proposal_id"], "category": "variation", "control_scope": "material"},
            "execution_status": "technical_pass" if manifest.get("technical_status") == "pass" else "technical_fail",
            "visual_status": "visible" if frames_valid else "near_blank",
            "max_visible_area_ratio": None,
            "resource_clean": all(int(result.get("resource_audit", {}).get(key, -1)) == 0 for key in ("runtime_materials_live", "runtime_textures_live")),
            "prompt_conditions_unscored": [],
            "execution_result_path": str(result_path),
            "proposal_manifest_path": str(proposal_path),
            "render_paths": [path.as_posix() for path in frame_paths if path.is_file()],
        }
        candidates.append((proposal, candidate, path, "variation"))
    candidates.extend(_load_course_adapter_candidates(course_adapter_paths))
    candidate_ids = [str(candidate.get("candidate_id") or "") for _, candidate, _, _ in candidates]
    duplicate_ids = sorted({candidate_id for candidate_id in candidate_ids if candidate_ids.count(candidate_id) > 1})
    if duplicate_ids:
        raise ValueError(f"duplicate Controller candidate ids: {', '.join(duplicate_ids)}")
    return candidates


def _target_for_candidate(parent: dict[str, Any], candidate: dict[str, Any], kind: str) -> dict[str, Any]:
    target: dict[str, Any] = {"kind": "mutation_spec", "payload": {}}
    if kind == "variation":
        proposal_path = Path(str(candidate["proposal_manifest_path"]))
        proposal = _read_json(proposal_path)
        target["payload"] = {
            "proposal_id": proposal.get("proposal_id"),
            "parent_candidate_id": proposal.get("parent_candidate_id"),
            "source_prefab": proposal.get("source_prefab"),
            "material_path": proposal.get("material_path"),
            "mutation_plan": proposal.get("mutation_plan"),
        }
    elif kind == "course_prior":
        target["payload"] = {
            "course_candidate_id": candidate.get("candidate_id"),
            "course_target": candidate.get("course_target"),
            "status": "engineering_prior_only",
            "requires": ["unity_reproduction", "human_prompt_condition_feedback", "human_visual_quality_feedback"],
        }
    else:
        target["payload"] = {
            "source_prefab": candidate.get("source_prefab"),
            "material_trajectory": candidate.get("material_trajectory"),
            "execution_status": candidate.get("execution_status"),
        }
    return target


def _mini_sft_record(example: dict[str, Any]) -> dict[str, Any]:
    input_text = json.dumps(example["input"], ensure_ascii=False, sort_keys=True)
    target_text = json.dumps(example["target"], ensure_ascii=False, sort_keys=True)
    return {
        "conversations": [
            {"role": "system", "content": "你是Unity VFX Controller。只输出符合VFXSpec/MutationSpec契约的JSON，不直接输出未经验证的Unity资产。"},
            {"role": "user", "content": input_text},
            {"role": "assistant", "content": target_text},
        ]
    }


def build_controller_dataset(
    composition_paths: Iterable[Path],
    variation_paths: Iterable[Path],
    condition_overlay_paths: Iterable[Path],
    output_dir: Path,
    dataset_id: str,
    *,
    course_adapter_paths: Iterable[Path] = (),
    minimum_sft_examples: int = MINIMUM_SFT_EXAMPLES,
    minimum_sft_families: int = MINIMUM_SFT_FAMILIES,
) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"controller dataset output already exists and is not empty: {output_dir}")
    composition_paths = list(composition_paths)
    variation_paths = list(variation_paths)
    condition_overlay_paths = list(condition_overlay_paths)
    course_adapter_paths = list(course_adapter_paths)
    overlays = _load_overlays(condition_overlay_paths)
    candidates = _load_candidate_manifests(composition_paths, variation_paths, course_adapter_paths)
    if not candidates:
        raise ValueError("no composition or variation manifests supplied")

    examples: list[dict[str, Any]] = []
    sft_records: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    exclusion_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    sft_family_counts: Counter[str] = Counter()
    source_kind_counts: Counter[str] = Counter()
    for parent, candidate, manifest_path, kind in candidates:
        source_kind_counts[kind] += 1
        candidate_id = str(candidate.get("candidate_id") or "")
        prompt = parent.get("prompt_condition") if isinstance(parent.get("prompt_condition"), dict) else {}
        course_input = candidate.get("course_input") if isinstance(candidate.get("course_input"), dict) else {}
        if not prompt and course_input:
            prompt = {"text": course_input.get("prompt"), "source": "course_evidence", "status": "prior_only"}
        overlay = overlays.get(candidate_id)
        condition_labels = overlay.get("human_conditions", {}) if isinstance(overlay, dict) else {}
        if not isinstance(condition_labels, dict):
            condition_labels = {}
        conditions = {str(key): str(value) for key, value in condition_labels.items() if str(key) in CONDITION_FIELDS and value in KNOWN_CHOICES}
        technical_ready = candidate.get("execution_status") == "technical_pass" and candidate.get("visual_status") == "visible" and candidate.get("resource_clean", True)
        reasons: list[str] = []
        if kind == "course_prior":
            reasons.extend([
                "course_prior_requires_unity_reproduction",
                "course_prior_requires_human_visual_confirmation",
            ])
        elif not technical_ready:
            reasons.append("technical_or_visual_evidence_not_ready")
        if kind != "course_prior":
            if overlay is None:
                reasons.append("missing_human_prompt_condition_feedback")
            elif not overlay.get("training_eligibility", {}).get("prompt_condition_supervision"):
                reasons.append("prompt_condition_supervision_not_eligible")
            if set(conditions) != set(CONDITION_FIELDS):
                reasons.append("prompt_condition_not_fully_judgable")
            if conditions.get("整体") != "符合":
                reasons.append("overall_not_positive")
        source_prefab = candidate.get("source_prefab") or {}
        family = str(source_prefab.get("effect_family_hint") or course_input.get("effect_family") or "unknown")
        course_provenance = candidate.get("course_provenance") if isinstance(candidate.get("course_provenance"), dict) else {}
        family_counts[family] += 1
        input_payload = {
            "prompt": str(prompt.get("text") or course_input.get("prompt") or ""),
            "prompt_condition": prompt,
            "context": {
                "source_prefab": source_prefab,
                "material_trajectory": candidate.get("material_trajectory"),
                "course_evidence": {
                    "record_id": course_input.get("record_id") or course_provenance.get("record_id"),
                    "effect_family": course_input.get("effect_family") or family,
                    "excerpt": course_input.get("course_evidence"),
                    "source_path": course_provenance.get("source_path"),
                    "line_start": course_provenance.get("line_start"),
                    "line_end": course_provenance.get("line_end"),
                    "timecodes": course_provenance.get("timecodes", []),
                    "status": "prior_only" if kind == "course_prior" else None,
                } if kind == "course_prior" else None,
                "course_prior": {
                    "target": candidate.get("course_target"),
                    "status": "engineering_prior_only",
                    "adapter_manifest": _portable(manifest_path),
                } if kind == "course_prior" else None,
                "technical_evidence": {
                    "execution_status": candidate.get("execution_status"),
                    "visual_status": candidate.get("visual_status"),
                    "resource_clean": candidate.get("resource_clean"),
                    "manifest_path": _portable(manifest_path),
                },
            },
        }
        target = _target_for_candidate(parent, candidate, kind)
        eligibility = {
            "controller_sft": not reasons,
            "prompt_condition_supervision": bool(overlay and overlay.get("training_eligibility", {}).get("prompt_condition_supervision") and conditions),
            "positive_generation_supervision": bool(overlay and overlay.get("training_eligibility", {}).get("positive_generation_supervision") and conditions.get("整体") == "符合"),
            "preference_training": False,
            "excluded_reasons": reasons,
        }
        if reasons:
            for reason in set(reasons):
                exclusion_counts[reason] += 1
            exclusions.append({"candidate_id": candidate_id, "source_manifest": _portable(manifest_path), "excluded_reasons": reasons, "condition_labels": conditions})
        example = {
            "schema_version": "vfx_controller_training_example.v1",
            "example_id": f"{dataset_id}_{candidate_id}",
            "input": input_payload,
            "target": target if not reasons else None,
            "labels": {
                "condition_labels": conditions,
                "overall_label": conditions.get("整体", "无法判断"),
                "quality_decision": "未评价",
            },
            "provenance": {
                "source_kind": kind,
                "source_manifest": None,
                "composition_or_variation_manifest": _portable(manifest_path),
                "candidate_id": candidate_id,
                "render_paths": list((overlay or {}).get("trace", {}).get("render_paths", [])) or list(candidate.get("render_paths", [])),
                "seed": parent.get("prompt_condition", {}).get("seed") if isinstance(parent.get("prompt_condition"), dict) else None,
                "parent_candidate_id": parent.get("parent_candidate_id") if kind == "variation" else None,
            },
            "training_eligibility": eligibility,
        }
        schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/vfx_controller_training_example.schema.json")
        errors = list(Draft202012Validator(schema).iter_errors(example))
        if errors:
            raise ValueError(f"controller example schema error for {candidate_id}: {errors[0].message}")
        examples.append(example)
        if eligibility["controller_sft"]:
            sft_records.append(_mini_sft_record(example))
            sft_family_counts[family] += 1

    if len(sft_records) >= minimum_sft_examples and len(sft_family_counts) >= minimum_sft_families:
        gate_status = "ready"
        gate_reason = "minimum human-confirmed positive Controller examples and family coverage are available"
    elif not sft_records:
        gate_status = "no_eligible_examples"
        gate_reason = "no candidate has complete, human-confirmed, positive Prompt-condition supervision"
    else:
        gate_status = "insufficient_labels"
        gate_reason = f"need {minimum_sft_examples} positive SFT examples across {minimum_sft_families} SFT families; found {len(sft_records)} across {len(sft_family_counts)}"

    examples_path = _write_jsonl(output_dir / "controller_examples.jsonl", examples)
    sft_path = _write_jsonl(output_dir / "minimind_sft.jsonl", sft_records)
    exclusions_path = _write_jsonl(output_dir / "controller_exclusions.jsonl", exclusions)
    source_paths = [*composition_paths, *variation_paths, *course_adapter_paths]
    manifest = {
        "schema_version": "vfx_controller_dataset.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_count": len(set(str(path.resolve()) for path in source_paths)),
        "candidate_count": len(candidates),
        "course_prior_count": source_kind_counts.get("course_prior", 0),
        "controller_example_count": len(examples),
        "sft_example_count": len(sft_records),
        "excluded_count": len(exclusions),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "files": {"controller_examples": examples_path.name, "minimind_sft": sft_path.name, "exclusions": exclusions_path.name},
        "training_gate": {"status": gate_status, "reason": gate_reason, "positive_sft_ready": gate_status == "ready", "minimum_sft_examples": minimum_sft_examples},
        "family_counts": dict(sorted(family_counts.items())),
        "sft_family_counts": dict(sorted(sft_family_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "policy": {
            "not_visible_is_not_training_data": True,
            "unknown_prompt_condition_is_not_positive_training": True,
            "technical_pass_is_not_aesthetic_acceptance": True,
            "minimind_role": "controller_planner_only",
            "asset_generation_role": "family_adapters_and_unity_executor",
            "course_prior_is_not_training_example": True,
        },
        "status": "pass",
    }
    manifest_schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/vfx_controller_dataset.schema.json")
    errors = list(Draft202012Validator(manifest_schema).iter_errors(manifest))
    if errors:
        raise ValueError(f"controller dataset manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "controller_dataset_manifest.json", manifest)
    return {"manifest": manifest_path, "examples": examples_path, "sft": sft_path, "exclusions": exclusions_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a safe VFX Controller dataset.")
    parser.add_argument("--composition-manifest", type=Path, action="append", default=[])
    parser.add_argument("--variation-manifest", type=Path, action="append", default=[])
    parser.add_argument("--condition-overlay", type=Path, action="append", default=[])
    parser.add_argument("--course-adapter-manifest", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--minimum-sft-examples", type=int, default=MINIMUM_SFT_EXAMPLES)
    parser.add_argument("--minimum-sft-families", type=int, default=MINIMUM_SFT_FAMILIES)
    args = parser.parse_args(argv)
    try:
        paths = build_controller_dataset(args.composition_manifest, args.variation_manifest, args.condition_overlay, args.output_dir, args.dataset_id, course_adapter_paths=args.course_adapter_manifest, minimum_sft_examples=args.minimum_sft_examples, minimum_sft_families=args.minimum_sft_families)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
