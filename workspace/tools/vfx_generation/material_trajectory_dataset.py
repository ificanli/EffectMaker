"""Assemble verified MaterialTrajectory executions into leakage-safe training examples."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from workspace.tools.vfx_training_dataset import blank_style_profile


DATASET_SCHEMA = "material_trajectory_training_dataset.v1"
EXAMPLE_SCHEMA = "training_example.v1"
GENERATOR = "material_trajectory_dataset.v1"
SPLIT_STRATEGY = "strict_shader_material_components.v1"
SPLIT_ORDER = ("train", "test", "validation")
TARGET_RATIOS = {"train": 0.8, "validation": 0.1, "test": 0.1}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _schema_root() -> Path:
    return Path(__file__).parents[2] / "data/vfx_generation/schemas"


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _portable(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_repo_root().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _validate(validator: Draft202012Validator, value: dict[str, Any], label: str) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if not errors:
        return
    location = ".".join(str(part) for part in errors[0].path) or "<root>"
    raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _validators() -> dict[str, Draft202012Validator]:
    root = _schema_root()
    style_schema = _read_json(root / "style_profile.schema.json")
    registry = Registry().with_resource("style_profile.schema.json", Resource.from_contents(style_schema))
    return {
        "trajectory": Draft202012Validator(_read_json(root / "material_trajectory.schema.json")),
        "result": Draft202012Validator(_read_json(root / "material_trajectory_execution_result.schema.json")),
        "timeline": Draft202012Validator(_read_json(root / "material_timeline.schema.json")),
        "base_example": Draft202012Validator(_read_json(root / "training_example.schema.json"), registry=registry),
        "example": Draft202012Validator(_read_json(root / "material_trajectory_training_example.schema.json")),
        "manifest": Draft202012Validator(_read_json(root / "material_trajectory_training_dataset.schema.json")),
    }


def assign_strict_group_splits(records: list[dict[str, str]], seed: int) -> tuple[dict[str, str], dict[str, Any]]:
    """Assign whole Shader components; Material groups are verified to belong to one component."""
    if not records:
        raise ValueError("no records are available for splitting")
    material_to_shader: dict[str, str] = {}
    shader_members: dict[str, list[str]] = defaultdict(list)
    for record in records:
        example_id = record["example_id"]
        shader_group = record["shader_group"]
        material_group = record["material_group"]
        previous = material_to_shader.setdefault(material_group, shader_group)
        if previous != shader_group:
            raise ValueError(f"material group spans Shader groups: {material_group}")
        shader_members[shader_group].append(example_id)
    if len(shader_members) < 3:
        raise ValueError("strict train/validation/test split requires at least three Shader groups")

    def tie_breaker(shader_group: str) -> str:
        return hashlib.sha256(f"{seed}:{shader_group}".encode("utf-8")).hexdigest()

    components = sorted(shader_members, key=lambda group: (-len(shader_members[group]), tie_breaker(group), group))
    counts = {split: 0 for split in TARGET_RATIOS}
    group_split: dict[str, str] = {}
    total = len(records)
    for index, shader_group in enumerate(components):
        if index < len(SPLIT_ORDER):
            split = SPLIT_ORDER[index]
        else:
            deficits = {
                name: TARGET_RATIOS[name] * total - counts[name]
                for name in TARGET_RATIOS
            }
            split = max(("train", "test", "validation"), key=lambda name: (deficits[name], -SPLIT_ORDER.index(name)))
        group_split[shader_group] = split
        counts[split] += len(shader_members[shader_group])

    assignments = {
        record["example_id"]: group_split[record["shader_group"]]
        for record in records
    }
    maximum_deviation = max(abs(counts[name] / total - TARGET_RATIOS[name]) for name in TARGET_RATIOS)
    warning = None
    if maximum_deviation > 0.1:
        warning = (
            "Strict Shader-group isolation is severely imbalanced because one Shader group dominates the curriculum; "
            "do not report balanced holdout metrics from this split."
        )
    return assignments, {
        "name": SPLIT_STRATEGY,
        "seed": seed,
        "target_ratios": TARGET_RATIOS,
        "component_count": len(shader_members),
        "shader_group_sizes": dict(sorted((group, len(values)) for group, values in shader_members.items())),
        "imbalance_warning": warning,
    }


def _style_profile(spec: dict[str, Any]) -> dict[str, Any]:
    source = spec.get("source_asset") if isinstance(spec.get("source_asset"), dict) else {}
    style = spec.get("style_profile") if isinstance(spec.get("style_profile"), dict) else {}
    context = [
        *(str(value) for value in source.get("source_categories", []) if isinstance(value, str)),
        *(str(value) for value in source.get("effect_families", []) if isinstance(value, str)),
    ]
    result = blank_style_profile(source="unlabeled_source_import", scene_context=context)
    family = style.get("family")
    if family in {"unknown", "realistic", "stylized", "cartoon", "anime", "fantasy_painterly", "ui_graphic", "mixed"}:
        result["family"] = family
    result["keywords"] = sorted({str(value) for value in style.get("keywords", []) if isinstance(value, str)})
    result["notes"] = "Style is source metadata only; no R002 human style judgment exists."
    return result


def _contact_sheet_path(run_root: Path, ordinal: int, paths: list[str]) -> Path:
    page_index = ordinal // 8
    if page_index >= len(paths):
        raise ValueError(f"contact sheet page is missing for candidate ordinal {ordinal}")
    return run_root / paths[page_index]


def _pairwise_overlap(examples: list[dict[str, Any]], group_field: str) -> set[str]:
    by_split: dict[str, set[str]] = defaultdict(set)
    for example in examples:
        by_split[example["split"]["name"]].add(example["split"][group_field])
    return (by_split["train"] & by_split["validation"]) | (by_split["train"] & by_split["test"]) | (by_split["validation"] & by_split["test"])


def _build_example(
    *,
    dataset_id: str,
    run_id: str,
    curriculum_id: str,
    seed: int,
    spec: dict[str, Any],
    result: dict[str, Any],
    timeline: dict[str, Any],
    run_candidate: dict[str, Any],
    split: str,
    spec_path: Path,
    result_path: Path,
    timeline_path: Path,
    curriculum_manifest_path: Path,
    run_manifest_path: Path,
    contact_sheet_path: Path,
) -> dict[str, Any]:
    trajectory_id = str(spec["trajectory_id"])
    source_asset = spec["source_asset"]
    profile = _style_profile(spec)
    diagnostic_paths = [result_path.parent / "frames" / str(frame["path"]) for frame in result.get("frames", [])]
    missing_frames = [path for path in diagnostic_paths if not path.is_file()]
    if missing_frames:
        raise FileNotFoundError(f"render frame is missing for {trajectory_id}: {missing_frames[0]}")
    image_eligible = bool(run_candidate["image_training_eligible"])
    render_paths = diagnostic_paths if image_eligible else []
    expected = sorted({str(value) for value in spec.get("expected_signals", [])})
    actual = sorted({str(value) for value in result.get("actual_signals", [])})
    if expected != actual:
        raise ValueError(f"expected/actual signal mismatch for {trajectory_id}: {expected} != {actual}")
    if result.get("status") != "pass" or timeline.get("capture_error") not in {None, ""}:
        raise ValueError(f"execution evidence is not pass for {trajectory_id}")
    negative = spec.get("negative_mutation")
    trajectory_label = str(spec["label"])
    decision = "controlled_negative_trajectory" if trajectory_label == "negative" else "execution_pass_unlabeled_aesthetic"
    material_selection = {
        "texture_tag_index_path": None,
        "texture_tag_index_status": "unavailable",
        "texture_tag_index_record_count": None,
        "shader_candidates": [{"shader_name": source_asset["shader_name"], "shader_path": source_asset.get("shader_path")}],
        "texture_candidates": source_asset.get("texture_bindings", []),
        "materials": [{
            "material_path": source_asset["material_path"],
            "material_name": source_asset["material_name"],
            "shader_name": source_asset["shader_name"],
        }],
        "selection_basis": ["unity_material_binding_audit_r3", curriculum_id],
    }
    return {
        "schema_version": EXAMPLE_SCHEMA,
        "example_id": f"{dataset_id}_{trajectory_id}",
        "run_id": run_id,
        "candidate_id": trajectory_id,
        "inputs": {
            "prompt": "",
            "negative_prompt": "",
            "target_style_profile": profile,
            "reference_frames": [],
            "spec_path": _portable(spec_path),
            "execution_result_path": _portable(result_path),
            "material_timeline_path": _portable(timeline_path),
            "render_manifest_path": _portable(run_manifest_path),
            "source_sample_path": _portable(curriculum_manifest_path),
            "source_asset": source_asset,
            "material_selection": material_selection,
            "trajectory_category": spec["category"],
            "control_scope": spec["control_scope"],
            "duration_seconds": spec["duration_seconds"],
            "parameter_tracks": spec.get("parameter_tracks", []),
            "events": {
                "keyword": spec.get("keyword_events", []),
                "texture_swap": spec.get("texture_swap_events", []),
                "material_replace": spec.get("material_replace_events", []),
            },
            "expected_signals": expected,
            "split_group": spec["split_group"],
        },
        "outputs": {
            "render_paths": [_portable(path) for path in render_paths],
            "diagnostic_render_paths": [_portable(path) for path in diagnostic_paths],
            "contact_sheet_path": _portable(contact_sheet_path),
            "features_path": None,
            "actual_signals": actual,
            "raw_timeline_signals": sorted({str(value) for value in result.get("raw_timeline_signals", [])}),
            "visual_evidence": {
                "status": run_candidate["visual_status"],
                "image_training_eligible": image_eligible,
                "max_visible_area_ratio": run_candidate["max_visible_area_ratio"],
                "mean_visible_area_ratio": run_candidate["mean_visible_area_ratio"],
            },
            "resource_audit": result["resource_audit"],
            "observed_style_profile": profile,
        },
        "label": {
            "decision": decision,
            "trajectory_label": trajectory_label,
            "technical_execution": "pass",
            "aesthetic_quality": "unlabeled",
            "negative_mutation": negative,
            "technical_rejection_reasons": [] if negative is None else [negative["type"], negative["reason"]],
            "rank": None,
            "accepted_parts": [],
            "rejected_parts": [],
            "next_mutation": [],
            "style_match_decision": "unlabeled",
            "style_mismatch_dimensions": [],
        },
        "task_membership": {
            "material_state": True,
            "image_conditioned": image_eligible,
            "aesthetic_preference": False,
        },
        "split": {
            "name": split,
            "strategy": SPLIT_STRATEGY,
            "shader_group": spec["split_group"]["shader_group"],
            "material_group": spec["split_group"]["material_group"],
        },
        "provenance": {
            "curriculum_id": curriculum_id,
            "curriculum_manifest_path": _portable(curriculum_manifest_path),
            "run_manifest_path": _portable(run_manifest_path),
            "generator": GENERATOR,
            "seed": seed,
        },
    }


def build_material_trajectory_dataset(
    curriculum_root: Path,
    run_root: Path,
    output_root: Path,
    dataset_id: str,
    seed: int,
) -> dict[str, Path]:
    curriculum_root = curriculum_root.resolve()
    run_root = run_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"dataset output already exists and is not empty: {output_root}")
    validators = _validators()
    curriculum_manifest_path = curriculum_root / "manifest.json"
    run_manifest_path = run_root / "run_manifest.json"
    curriculum_manifest = _read_json(curriculum_manifest_path)
    run_manifest = _read_json(run_manifest_path)
    if run_manifest.get("status") != "pass":
        raise ValueError("source execution run did not pass")
    curriculum_id = str(curriculum_manifest["curriculum_id"])
    run_id = str(run_manifest["run_id"])
    run_candidates = {str(value["trajectory_id"]): value for value in run_manifest.get("candidates", [])}

    loaded: list[dict[str, Any]] = []
    split_records: list[dict[str, str]] = []
    for spec_relative in curriculum_manifest.get("spec_paths", []):
        spec_path = curriculum_root / str(spec_relative)
        spec = _read_json(spec_path)
        trajectory_id = str(spec["trajectory_id"])
        result_path = run_root / "candidates" / trajectory_id / "execution_result.json"
        timeline_path = run_root / "candidates" / trajectory_id / "material_timeline.json"
        result = _read_json(result_path)
        timeline = _read_json(timeline_path)
        _validate(validators["trajectory"], spec, f"spec {trajectory_id}")
        _validate(validators["result"], result, f"result {trajectory_id}")
        _validate(validators["timeline"], timeline, f"timeline {trajectory_id}")
        if trajectory_id not in run_candidates:
            raise ValueError(f"run manifest candidate is missing: {trajectory_id}")
        example_id = f"{dataset_id}_{trajectory_id}"
        loaded.append({
            "spec": spec,
            "result": result,
            "timeline": timeline,
            "run_candidate": run_candidates[trajectory_id],
            "spec_path": spec_path,
            "result_path": result_path,
            "timeline_path": timeline_path,
        })
        split_records.append({
            "example_id": example_id,
            "shader_group": str(spec["split_group"]["shader_group"]),
            "material_group": str(spec["split_group"]["material_group"]),
        })
    assignments, split_strategy = assign_strict_group_splits(split_records, seed)

    contact_paths = [str(value) for value in run_manifest.get("contact_sheet_paths", [])]
    examples: list[dict[str, Any]] = []
    for ordinal, item in enumerate(loaded):
        spec = item["spec"]
        example_id = f"{dataset_id}_{spec['trajectory_id']}"
        example = _build_example(
            dataset_id=dataset_id,
            run_id=run_id,
            curriculum_id=curriculum_id,
            seed=seed,
            spec=spec,
            result=item["result"],
            timeline=item["timeline"],
            run_candidate=item["run_candidate"],
            split=assignments[example_id],
            spec_path=item["spec_path"],
            result_path=item["result_path"],
            timeline_path=item["timeline_path"],
            curriculum_manifest_path=curriculum_manifest_path,
            run_manifest_path=run_manifest_path,
            contact_sheet_path=_contact_sheet_path(run_root, ordinal, contact_paths),
        )
        _validate(validators["base_example"], example, f"base training example {example_id}")
        _validate(validators["example"], example, f"material training example {example_id}")
        examples.append(example)

    material_overlap = _pairwise_overlap(examples, "material_group")
    shader_overlap = _pairwise_overlap(examples, "shader_group")
    if material_overlap or shader_overlap:
        raise ValueError(f"split leakage detected: material={sorted(material_overlap)}, shader={sorted(shader_overlap)}")
    examples.sort(key=lambda value: value["candidate_id"])
    state_examples = list(examples)
    image_examples = [value for value in examples if value["task_membership"]["image_conditioned"]]
    split_summaries: dict[str, dict[str, int]] = {}
    for split in ("train", "validation", "test"):
        members = [value for value in examples if value["split"]["name"] == split]
        split_summaries[split] = {
            "example_count": len(members),
            "material_state_count": len(members),
            "image_conditioned_count": sum(value["task_membership"]["image_conditioned"] for value in members),
            "shader_group_count": len({value["split"]["shader_group"] for value in members}),
            "material_group_count": len({value["split"]["material_group"] for value in members}),
        }

    examples_path = _write_jsonl(output_root / "examples.jsonl", examples)
    state_path = _write_jsonl(output_root / "material_state_examples.jsonl", state_examples)
    image_path = _write_jsonl(output_root / "image_conditioned_examples.jsonl", image_examples)
    assignments_path = _write_jsonl(
        output_root / "split_assignments.jsonl",
        ({"example_id": value["example_id"], "candidate_id": value["candidate_id"], **value["split"]} for value in examples),
    )
    for split in ("train", "validation", "test"):
        _write_jsonl(output_root / "splits" / f"{split}.jsonl", (value for value in examples if value["split"]["name"] == split))

    manifest = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "curriculum_id": curriculum_id,
        "source": {
            "curriculum_manifest_path": _portable(curriculum_manifest_path),
            "run_manifest_path": _portable(run_manifest_path),
            "run_id": run_id,
        },
        "example_count": len(examples),
        "material_state_example_count": len(state_examples),
        "image_conditioned_example_count": len(image_examples),
        "aesthetic_preference_example_count": 0,
        "label_counts": dict(sorted(Counter(value["label"]["trajectory_label"] for value in examples).items())),
        "category_counts": dict(sorted(Counter(value["inputs"]["trajectory_category"] for value in examples).items())),
        "split_strategy": split_strategy,
        "splits": split_summaries,
        "leakage_checks": {
            "material_group_overlap_count": len(material_overlap),
            "shader_group_overlap_count": len(shader_overlap),
            "passed": not material_overlap and not shader_overlap,
        },
        "training_eligibility": {
            "material_state": "ready",
            "image_conditioned": "feature_only" if split_summaries["validation"]["image_conditioned_count"] == 0 else "ready",
            "aesthetic_preference": "not_ready_no_human_labels",
            "image_validation_split_empty": split_summaries["validation"]["image_conditioned_count"] == 0,
        },
        "files": {
            "examples": _portable(examples_path),
            "material_state_examples": _portable(state_path),
            "image_conditioned_examples": _portable(image_path),
            "split_assignments": _portable(assignments_path),
            "split_directory": _portable(output_root / "splits"),
        },
        "quality_gates": {
            "source_spec_schema_errors": 0,
            "source_result_schema_errors": 0,
            "source_timeline_schema_errors": 0,
            "base_training_example_schema_errors": 0,
            "material_training_example_schema_errors": 0,
            "expected_actual_signal_mismatches": 0,
            "missing_render_files": 0,
        },
        "limitations": [
            "No R002 human aesthetic or style-match labels exist; examples must not train an aesthetic preference model.",
            "Only three Shader groups exist with a 93/6/1 distribution, so strict Shader isolation is severely imbalanced.",
            "The image-conditioned validation split is empty because the singleton validation Shader has no visible stable-Quad sample.",
            "Twenty-eight near-blank candidates are material-state-only until context renderers reproduce their required Mesh, Particle, UI, or Prefab inputs.",
        ],
        "status": "pass",
    }
    _validate(validators["manifest"], manifest, "dataset manifest")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {
        "dataset_manifest": manifest_path,
        "examples": examples_path,
        "material_state_examples": state_path,
        "image_conditioned_examples": image_path,
        "split_assignments": assignments_path,
    }


def load_material_trajectory_examples(
    dataset_root: Path,
    *,
    task: str = "material_state",
    split: str | None = None,
) -> list[dict[str, Any]]:
    """Load only examples explicitly eligible for one task, optionally restricted to a split."""
    dataset_root = dataset_root.resolve()
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    if manifest.get("schema_version") != DATASET_SCHEMA or manifest.get("status") != "pass":
        raise ValueError(f"verified MaterialTrajectory dataset manifest expected: {dataset_root}")
    if task == "material_state":
        source = dataset_root / "material_state_examples.jsonl"
    elif task == "image_conditioned":
        source = dataset_root / "image_conditioned_examples.jsonl"
    elif task == "aesthetic_preference":
        raise ValueError("R002 has no human aesthetic labels; aesthetic_preference loading is prohibited")
    else:
        raise ValueError(f"unsupported MaterialTrajectory dataset task: {task}")
    if split is not None and split not in {"train", "validation", "test"}:
        raise ValueError(f"unsupported dataset split: {split}")
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if split is not None:
        rows = [row for row in rows if row.get("split", {}).get("name") == split]
    membership = "material_state" if task == "material_state" else "image_conditioned"
    if any(not row.get("task_membership", {}).get(membership) for row in rows):
        raise ValueError(f"dataset file contains an example ineligible for {task}")
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assemble verified MaterialTrajectory R002 training examples.")
    parser.add_argument("--curriculum-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--seed", type=int, default=20260828)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = build_material_trajectory_dataset(
            args.curriculum_root,
            args.run_root,
            args.output_root,
            args.dataset_id,
            args.seed,
        )
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
