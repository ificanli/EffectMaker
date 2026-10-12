"""Build technical PrefabGraph and ParticleSystem training examples from Unity audit evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


DATASET_SCHEMA = "prefab_structure_training_dataset.v1"
EXAMPLE_SCHEMA = "training_example.v1"
GENERATOR = "prefab_structure_dataset.v1"


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


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _schema_root() -> Path:
    return Path(__file__).parents[2] / "data/vfx_generation/schemas"


def _portable(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_repo_root().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _validators() -> dict[str, Draft202012Validator]:
    root = _schema_root()
    style = _read_json(root / "style_profile.schema.json")
    registry = Registry().with_resource("style_profile.schema.json", Resource.from_contents(style))
    return {
        "audit": Draft202012Validator(_read_json(root / "prefab_structure_audit.schema.json")),
        "base": Draft202012Validator(_read_json(root / "training_example.schema.json"), registry=registry),
        "example": Draft202012Validator(_read_json(root / "prefab_structure_training_example.schema.json")),
        "manifest": Draft202012Validator(_read_json(root / "prefab_structure_training_dataset.schema.json")),
    }


def _validate(validator: Draft202012Validator, value: dict[str, Any], label: str) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if not errors:
        return
    location = ".".join(str(part) for part in errors[0].path) or "<root>"
    raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _prefab_group(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:12]


def _summary(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        key: audit.get(key)
        for key in (
            "status", "reasons", "node_count", "particle_system_count", "particle_renderer_count",
            "renderer_count", "material_slot_count", "missing_material_slot_count", "missing_script_count",
            "serialized_empty_material_slot_count", "missing_shader_count",
            "max_particle_count", "estimated_duration_seconds", "looping", "animator_count",
            "legacy_animation_count", "playable_director_count",
        )
    }


def _load_render_evidence(run_root: Path) -> dict[str, dict[str, Any]]:
    manifest = _read_json(run_root / "run_manifest.json")
    if manifest.get("schema_version") != "vfx_run_manifest.v1":
        raise ValueError(f"Prefab render run manifest expected: {run_root}")
    contact_sheets = [run_root / str(path) for path in manifest.get("contact_sheet_paths", [])]
    result: dict[str, dict[str, Any]] = {}
    for candidate in manifest.get("candidates", []):
        spec_path = run_root / str(candidate["spec_path"])
        spec = _read_json(spec_path)
        layers = spec.get("layers") if isinstance(spec.get("layers"), list) else []
        if not layers:
            raise ValueError(f"source Prefab layer is missing: {spec_path}")
        prefab_path = str(layers[0].get("shape_parameters", {}).get("source_prefab_path") or "")
        if not prefab_path:
            raise ValueError(f"source Prefab path is missing: {spec_path}")
        if prefab_path in result:
            raise ValueError(f"render run contains duplicate Prefab: {prefab_path}")
        capture_root = run_root / str(candidate["capture_root"])
        frames = candidate.get("frames") if isinstance(candidate.get("frames"), list) else []
        frame_paths = [capture_root / str(frame["path"]) for frame in frames if frame.get("valid")]
        page = int(candidate.get("contact_sheet_page") or 0)
        if page <= 0 or page > len(contact_sheets):
            raise ValueError(f"contact sheet page is missing for {candidate.get('candidate_id')}")
        auto_eval = candidate.get("auto_eval") if isinstance(candidate.get("auto_eval"), dict) else {}
        summary = candidate.get("material_state_summary") if isinstance(candidate.get("material_state_summary"), dict) else {}
        result[prefab_path] = {
            "candidate_id": str(candidate["candidate_id"]),
            "status": str(auto_eval.get("status") or "unknown"),
            "hard_reject_reasons": list(auto_eval.get("hard_reject_reasons") or []),
            "metrics": auto_eval.get("metrics") or {},
            "frame_paths": frame_paths,
            "material_timeline_path": run_root / str(candidate["material_timeline_path"]),
            "contact_sheet_path": contact_sheets[page - 1],
            "source_script_fidelity": str(summary.get("source_script_fidelity") or "unknown"),
        }
    return result


def _build_example(
    dataset_id: str,
    source_group: str,
    case: dict[str, Any],
    audit: dict[str, Any],
    cases_path: Path,
    audit_path: Path,
    unity_project: Path,
    audit_revision: int,
    render: dict[str, Any] | None,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    prefab_path = str(case["source"]["prefab_path"])
    if not (unity_project / prefab_path).is_file():
        raise FileNotFoundError(f"Prefab asset is missing: {prefab_path}")
    eligible = set(str(value) for value in case.get("training", {}).get("eligible_for", []))
    particle_parameters = "particle_parameter_supervision" in eligible
    technical_status = str(audit["status"])
    # Structural source gaps remain training provenance risks, but cannot overrule
    # the Unity audit that a Prefab has a self-contained ParticleSystem runtime.
    render_candidate = technical_status == "particle_playable"
    diagnostic_paths: list[Path] = []
    render_paths: list[Path] = []
    render_evidence = None
    material_timeline_path = None
    contact_sheet_path = None
    image_conditioned = False
    if render is not None:
        diagnostic_paths = render["frame_paths"]
        missing = [path for path in diagnostic_paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Prefab render frame is missing: {missing[0]}")
        image_conditioned = render["status"] in {"pass", "warn"}
        render_paths = diagnostic_paths if image_conditioned else []
        material_timeline_path = _portable(render["material_timeline_path"])
        contact_sheet_path = _portable(render["contact_sheet_path"])
        render_evidence = {
            "candidate_id": render["candidate_id"],
            "status": render["status"],
            "hard_reject_reasons": render["hard_reject_reasons"],
            "metrics": render["metrics"],
            "frame_count": len(diagnostic_paths),
            "source_script_fidelity": render["source_script_fidelity"],
        }
    outputs = {
        "render_paths": [_portable(path) for path in render_paths],
        "diagnostic_render_paths": [_portable(path) for path in diagnostic_paths],
        "features_path": None,
        "observed_style_profile": case["observations"]["observed_style_profile"],
        "prefab_summary": _summary(audit),
        "prefab_graph": audit["nodes"],
        "particle_systems": audit["particle_systems"],
        "renderers": audit["renderers"],
        "animations": audit["animations"],
    }
    if render is not None:
        outputs.update({
            "material_timeline_path": material_timeline_path,
            "contact_sheet_path": contact_sheet_path,
            "render_evidence": render_evidence,
        })
    return {
        "schema_version": EXAMPLE_SCHEMA,
        "example_id": f"{dataset_id}_{case_id}",
        "run_id": f"effectdemo_prefab_structure_audit_r{audit_revision}",
        "candidate_id": case_id,
        "inputs": {
            "prompt": case["inputs"]["prompt"],
            "negative_prompt": case["inputs"]["negative_prompt"],
            "target_style_profile": case["inputs"]["target_style_profile"],
            "prefab_path": prefab_path,
            "source_category": case["source"]["source_category"],
            "effect_family_hint": case["source"]["effect_family_hint"],
            "dependency_health": case["observations"]["dependency_health"],
            "material_selection": case["inputs"]["material_selection"],
        },
        "outputs": outputs,
        "label": {
            "decision": "structure_observation_unlabeled_aesthetic",
            "technical_status": technical_status,
            "technical_reasons": audit.get("reasons", []),
            "aesthetic_quality": "unlabeled",
            "style_match_decision": "unlabeled",
            "rank": None,
            "accepted_parts": [],
            "rejected_parts": [],
            "next_mutation": [],
        },
        "task_membership": {
            "prefab_structure": True,
            "particle_parameters": particle_parameters,
            "play_mode_render_candidate": render_candidate,
            "image_conditioned": image_conditioned,
            "aesthetic_preference": False,
        },
        "training_status": {
            "supervision_status": case["training"]["supervision_status"],
            "eligible_for": case["training"]["eligible_for"],
            "excluded_from": case["training"]["excluded_from"],
            "blocking_reasons": case["training"]["blocking_reasons"],
        },
        "split_group": {
            "prefab_group": _prefab_group(prefab_path),
            "source_group": source_group,
        },
        "provenance": {
            "case_path": f"{_portable(cases_path)}#{case_id}",
            "audit_path": _portable(audit_path),
            "generator": GENERATOR,
        },
    }


def build_prefab_structure_dataset(
    cases_path: Path,
    audit_path: Path,
    unity_project: Path,
    output_root: Path,
    dataset_id: str,
    render_run_root: Path | None = None,
) -> dict[str, Path]:
    cases_path = cases_path.resolve()
    audit_path = audit_path.resolve()
    unity_project = unity_project.resolve()
    output_root = output_root.resolve()
    render_run_root = render_run_root.resolve() if render_run_root is not None else None
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"dataset output already exists and is not empty: {output_root}")
    validators = _validators()
    audit = _read_json(audit_path)
    _validate(validators["audit"], audit, "Prefab audit")
    cases = _read_jsonl(cases_path)
    audit_by_path = {str(value["prefab_path"]): value for value in audit["prefabs"]}
    if len(cases) != len(audit_by_path):
        raise ValueError(f"case/audit count mismatch: {len(cases)} != {len(audit_by_path)}")
    source_groups = {str(case["source"]["source_id"]) for case in cases}
    if len(source_groups) != 1:
        raise ValueError(f"one source group expected, found: {sorted(source_groups)}")
    source_group = next(iter(source_groups))
    render_by_prefab = _load_render_evidence(render_run_root) if render_run_root is not None else {}
    examples: list[dict[str, Any]] = []
    case_audit_mismatches = 0
    for case in cases:
        prefab_path = str(case["source"]["prefab_path"])
        if prefab_path not in audit_by_path:
            raise ValueError(f"Prefab audit record is missing: {prefab_path}")
        if case["observations"]["runtime_observation"].get("status") != audit_by_path[prefab_path].get("status"):
            # The Unity audit is the current technical truth. Case files are
            # historical observations and may legitimately lag after an audit
            # rule fix (for example, when native empty material slots were
            # previously counted as missing).
            case_audit_mismatches += 1
        example = _build_example(
            dataset_id,
            source_group,
            case,
            audit_by_path[prefab_path],
            cases_path,
            audit_path,
            unity_project,
            int(audit.get("audit_revision", 2)),
            render_by_prefab.get(prefab_path),
        )
        _validate(validators["base"], example, f"base example {example['example_id']}")
        _validate(validators["example"], example, f"Prefab example {example['example_id']}")
        examples.append(example)
    examples.sort(key=lambda value: value["candidate_id"])
    particles = [value for value in examples if value["task_membership"]["particle_parameters"]]
    render_candidates = [value for value in examples if value["task_membership"]["play_mode_render_candidate"]]
    blocked = [value for value in examples if not value["task_membership"]["play_mode_render_candidate"]]
    rendered = [value for value in examples if value["outputs"].get("render_evidence") is not None]
    image_examples = [value for value in examples if value["task_membership"]["image_conditioned"]]
    examples_path = _write_jsonl(output_root / "examples.jsonl", examples)
    particle_path = _write_jsonl(output_root / "particle_parameter_examples.jsonl", particles)
    render_path = _write_jsonl(output_root / "play_mode_render_candidates.jsonl", render_candidates)
    blocked_path = _write_jsonl(output_root / "blocked_or_context_examples.jsonl", blocked)
    rendered_path = _write_jsonl(output_root / "rendered_examples.jsonl", rendered)
    image_path = _write_jsonl(output_root / "image_feature_examples.jsonl", image_examples)
    limitations = [
        "These are technical structure, ParticleSystem, and render-evidence examples, not aesthetic positive examples.",
        "Source dependency health remains blocked for cases whose source manifest contains unresolved edges.",
        "Style family and style-match labels remain human-unlabeled.",
    ]
    if render_run_root is None:
        limitations.append("Play Mode render evidence is still missing for every example in this dataset version.")
    else:
        limitations.append("Auto-eval pass/warn only grants image feature eligibility; it is not a human quality label.")
    manifest = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source": {
            "source_group": source_group,
            "prefab_cases_path": _portable(cases_path),
            "prefab_audit_path": _portable(audit_path),
            "unity_project": _portable(unity_project),
            "render_run_root": _portable(render_run_root) if render_run_root is not None else None,
        },
        "example_count": len(examples),
        "prefab_structure_example_count": len(examples),
        "particle_parameter_example_count": len(particles),
        "play_mode_render_candidate_count": len(render_candidates),
        "image_conditioned_example_count": len(image_examples),
        "aesthetic_preference_example_count": 0,
        "rendered_example_count": len(rendered),
        "render_status_counts": dict(sorted(Counter(value["outputs"]["render_evidence"]["status"] for value in rendered).items())),
        "technical_status_counts": dict(sorted(Counter(value["label"]["technical_status"] for value in examples).items())),
        "supervision_status_counts": dict(sorted(Counter(value["training_status"]["supervision_status"] for value in examples).items())),
        "files": {
            "examples": _portable(examples_path),
            "particle_parameter_examples": _portable(particle_path),
            "play_mode_render_candidates": _portable(render_path),
            "blocked_or_context_examples": _portable(blocked_path),
            "rendered_examples": _portable(rendered_path),
            "image_feature_examples": _portable(image_path),
        },
        "quality_gates": {
            "audit_schema_errors": 0,
            "base_training_example_schema_errors": 0,
            "prefab_training_example_schema_errors": 0,
            "case_audit_mismatches": case_audit_mismatches,
            "missing_prefab_assets": 0,
            "human_aesthetic_labels": 0,
            "missing_render_files": 0,
        },
        "limitations": limitations,
        "status": "pass",
    }
    _validate(validators["manifest"], manifest, "Prefab dataset manifest")
    manifest_path = _write_json(output_root / "dataset_manifest.json", manifest)
    return {
        "dataset_manifest": manifest_path,
        "examples": examples_path,
        "particle_parameter_examples": particle_path,
        "play_mode_render_candidates": render_path,
        "blocked_or_context_examples": blocked_path,
        "rendered_examples": rendered_path,
        "image_feature_examples": image_path,
    }


def load_prefab_structure_examples(dataset_root: Path, task: str = "prefab_structure") -> list[dict[str, Any]]:
    dataset_root = dataset_root.resolve()
    manifest = _read_json(dataset_root / "dataset_manifest.json")
    if manifest.get("schema_version") != DATASET_SCHEMA or manifest.get("status") != "pass":
        raise ValueError(f"verified Prefab structure dataset expected: {dataset_root}")
    files = {
        "prefab_structure": "examples.jsonl",
        "particle_parameters": "particle_parameter_examples.jsonl",
        "play_mode_render_candidate": "play_mode_render_candidates.jsonl",
        "image_conditioned": "image_feature_examples.jsonl",
    }
    if task == "aesthetic_preference":
        raise ValueError("Prefab structure dataset has no human aesthetic labels")
    if task not in files:
        raise ValueError(f"unsupported Prefab structure task: {task}")
    return _read_jsonl(dataset_root / files[task])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build PrefabGraph and ParticleSystem technical training examples.")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--unity-project", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--render-run-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = build_prefab_structure_dataset(args.cases, args.audit, args.unity_project, args.output_root, args.dataset_id, args.render_run_root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: value.as_posix() for key, value in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
