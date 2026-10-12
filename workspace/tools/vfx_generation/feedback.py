"""Non-interactive creation and validation of structured VFX feedback."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DECISIONS = frozenset({"accept_direction", "partial", "reject", "needs_comparison", "not_visible"})
PAIRWISE_PREFERENCES = frozenset({"candidate", "compared", "tie"})
SCORE_SECTIONS = ("scores", "common_scores", "specialized_scores")
STYLE_FAMILIES = frozenset({"unknown", "realistic", "stylized", "cartoon", "anime", "fantasy_painterly", "ui_graphic", "mixed"})
STYLE_SOURCES = frozenset({"prompt", "human_annotation", "render_human_review", "rule_inference", "model_inference", "unlabeled_source_import"})
STYLE_MATCH_DECISIONS = frozenset({"match", "partial", "mismatch", "unlabeled"})
STYLE_AXES = frozenset({"realism", "graphic_stylization", "texture_detail", "color_saturation", "edge_definition", "glow_exaggeration", "motion_exaggeration"})


class FeedbackValidationError(ValueError):
    """Raised when a feedback record cannot be safely appended."""


def _resolve_inside(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    resolved = candidate if candidate.is_absolute() else root / candidate
    resolved = resolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FeedbackValidationError(f"path escapes run root: {resolved}") from exc
    return resolved


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedbackValidationError(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FeedbackValidationError(f"JSON object expected: {path}")
    return payload


def discover_candidate_ids(run_root: Path) -> set[str]:
    candidates_root = run_root / "candidates"
    if not candidates_root.is_dir():
        return set()
    candidate_ids: set[str] = set()
    for candidate_dir in candidates_root.iterdir():
        if candidate_dir.is_dir() and (candidate_dir / "spec.json").is_file():
            spec = _load_json(candidate_dir / "spec.json")
            generation = spec.get("generation")
            candidate_id = generation.get("candidate_id") if isinstance(generation, dict) else None
            candidate_ids.add(str(candidate_id or candidate_dir.name))
    return candidate_ids


def _relative_path(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _find_candidate_spec(run_root: Path, candidate_id: str) -> tuple[Path | None, dict[str, Any] | None]:
    candidates_root = run_root / "candidates"
    if not candidates_root.is_dir():
        return None, None
    for candidate_dir in candidates_root.iterdir():
        spec_path = candidate_dir / "spec.json"
        if not candidate_dir.is_dir() or not spec_path.is_file():
            continue
        spec = _load_json(spec_path)
        generation = spec.get("generation")
        discovered_id = generation.get("candidate_id") if isinstance(generation, dict) else None
        if str(discovered_id or candidate_dir.name) == candidate_id:
            return spec_path, spec
    return None, None


def _candidate_trace(run_root: Path, candidate_id: str) -> tuple[str | None, dict[str, Any]]:
    spec_path, spec = _find_candidate_spec(run_root, candidate_id)
    generation = spec.get("generation") if isinstance(spec, dict) else {}
    generation = generation if isinstance(generation, dict) else {}
    render_manifest_path: Path | None = None
    candidate_dir = spec_path.parent if spec_path is not None else None
    if candidate_dir is not None:
        for name in ("render_manifest.json", "capture_manifest.json"):
            possible = candidate_dir / name
            if possible.is_file():
                render_manifest_path = possible
                break
    render_manifest = _load_json(render_manifest_path) if render_manifest_path is not None else None
    render_paths: list[str] = []
    render_status = "missing_manifest"
    if render_manifest is not None:
        frames = render_manifest.get("frames")
        render_status = "blocked" if not isinstance(frames, list) else "ready"
        capture_root_value = render_manifest.get("capture_root") or render_manifest.get("root")
        if capture_root_value is None:
            capture_root = render_manifest_path.parent
        else:
            capture_root = Path(str(capture_root_value))
            if not capture_root.is_absolute():
                capture_root = render_manifest_path.parent / capture_root
        for frame in frames if isinstance(frames, list) else []:
            if not isinstance(frame, dict) or frame.get("path") is None:
                continue
            frame_path = Path(str(frame["path"]))
            if not frame_path.is_absolute():
                frame_path = capture_root / frame_path
            render_paths.append(_relative_path(run_root, frame_path) or str(frame["path"]))
    trace = {
        "spec_path": _relative_path(run_root, spec_path),
        "render_manifest_path": _relative_path(run_root, render_manifest_path),
        "render_paths": render_paths,
        "seed": generation.get("seed"),
        "generator": generation.get("generator"),
        "generator_version": generation.get("generator_version"),
        "render_status": render_status,
    }
    return str(spec.get("effect_family")) if isinstance(spec, dict) and spec.get("effect_family") is not None else None, trace


def _validate_score_section(record: dict[str, Any], section: str, errors: list[str]) -> None:
    values = record.get(section)
    if values is None:
        return
    if not isinstance(values, dict):
        errors.append(f"{section} must be an object")
        return
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
            errors.append(f"{section}.{key} must be an integer from 0 to 5")


def _validate_style_profile(value: Any, field: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return
    required = ("schema_version", "family", "keywords", "axes", "scene_context", "source", "confidence")
    for name in required:
        if name not in value:
            errors.append(f"missing {field}.{name}")
    if value.get("schema_version") != "vfx_style_profile.v1":
        errors.append(f"{field}.schema_version must be vfx_style_profile.v1")
    if value.get("family") not in STYLE_FAMILIES:
        errors.append(f"{field}.family is invalid")
    if not isinstance(value.get("keywords"), list) or not all(isinstance(item, str) for item in value.get("keywords", [])):
        errors.append(f"{field}.keywords must be an array of strings")
    if not isinstance(value.get("scene_context"), list) or not all(isinstance(item, str) for item in value.get("scene_context", [])):
        errors.append(f"{field}.scene_context must be an array of strings")
    axes = value.get("axes")
    if not isinstance(axes, dict):
        errors.append(f"{field}.axes must be an object")
    else:
        for name in STYLE_AXES:
            if name not in axes:
                errors.append(f"missing {field}.axes.{name}")
                continue
            axis = axes.get(name)
            if axis is not None and (isinstance(axis, bool) or not isinstance(axis, (int, float)) or not 0 <= float(axis) <= 1):
                errors.append(f"{field}.axes.{name} must be null or a number from 0 to 1")
    if value.get("source") not in STYLE_SOURCES:
        errors.append(f"{field}.source is invalid")
    confidence = value.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        errors.append(f"{field}.confidence must be a number from 0 to 1")


def validate_feedback_record(
    record: dict[str, Any],
    *,
    expected_run_id: str | None = None,
    candidate_ids: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    required = ("schema_version", "run_id", "candidate_id", "decision", "reviewer", "feedback")
    for field in required:
        if field not in record:
            errors.append(f"missing {field}")
    if record.get("schema_version") != "human_feedback.v1":
        errors.append("schema_version must be human_feedback.v1")
    if expected_run_id is not None and record.get("run_id") != expected_run_id:
        errors.append(f"run_id must be {expected_run_id}")
    candidate_id = record.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        errors.append("candidate_id must be a non-empty string")
    elif candidate_ids is not None and candidate_id not in candidate_ids:
        errors.append(f"unknown candidate_id: {candidate_id}")
    reviewer = record.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        errors.append("reviewer must be a non-empty string")
    if record.get("decision") not in DECISIONS:
        errors.append(f"decision must be one of: {', '.join(sorted(DECISIONS))}")
    rank = record.get("rank")
    if rank is not None and (isinstance(rank, bool) or not isinstance(rank, int) or rank < 1):
        errors.append("rank must be null or an integer >= 1")
    mutation_allowed = record.get("mutation_allowed")
    if mutation_allowed is not None and not isinstance(mutation_allowed, bool):
        errors.append("mutation_allowed must be boolean")
    effect_family = record.get("effect_family")
    if effect_family is not None and (not isinstance(effect_family, str) or not effect_family.strip()):
        errors.append("effect_family must be a non-empty string when present")
    _validate_style_profile(record.get("target_style_profile"), "target_style_profile", errors)
    _validate_style_profile(record.get("observed_style_profile"), "observed_style_profile", errors)
    style_match = record.get("style_match_decision")
    if style_match is not None and style_match not in STYLE_MATCH_DECISIONS:
        errors.append("style_match_decision must be match, partial, mismatch, unlabeled, or null")
    mismatch_dimensions = record.get("style_mismatch_dimensions")
    if mismatch_dimensions is not None and (not isinstance(mismatch_dimensions, list) or not all(isinstance(item, str) for item in mismatch_dimensions)):
        errors.append("style_mismatch_dimensions must be an array of strings")

    trace = record.get("trace")
    if trace is not None:
        if not isinstance(trace, dict):
            errors.append("trace must be an object")
        else:
            for field in ("spec_path", "render_manifest_path", "render_paths", "seed", "generator", "generator_version", "render_status"):
                if field not in trace:
                    errors.append(f"missing trace.{field}")
            for field in ("spec_path", "render_manifest_path", "generator", "generator_version", "render_status"):
                value = trace.get(field)
                if value is not None and not isinstance(value, str):
                    errors.append(f"trace.{field} must be a string or null")
            for field in ("render_paths",):
                value = trace.get(field)
                if value is not None and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)):
                    errors.append(f"trace.{field} must be an array of strings")
            seed = trace.get("seed")
            if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
                errors.append("trace.seed must be an integer or null")

    feedback = record.get("feedback")
    if not isinstance(feedback, dict):
        errors.append("feedback must be an object")
    elif not isinstance(feedback.get("summary"), str) or not feedback.get("summary", "").strip():
        errors.append("feedback.summary must be a non-empty string")
    else:
        for field in ("accepted_parts", "rejected_parts", "reject_reasons", "next_mutation"):
            value = feedback.get(field)
            if value is not None and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)):
                errors.append(f"feedback.{field} must be an array of strings")

    for section in SCORE_SECTIONS:
        _validate_score_section(record, section, errors)

    pairwise = record.get("pairwise")
    if pairwise is not None:
        if not isinstance(pairwise, dict):
            errors.append("pairwise must be an object")
        else:
            compared = pairwise.get("compared_candidate_id")
            if not isinstance(compared, str) or not compared.strip():
                errors.append("pairwise.compared_candidate_id must be a non-empty string")
            elif compared == candidate_id:
                errors.append("pairwise candidate cannot compare with itself")
            elif candidate_ids is not None and compared not in candidate_ids:
                errors.append(f"unknown pairwise candidate_id: {compared}")
            if pairwise.get("preference") not in PAIRWISE_PREFERENCES:
                errors.append("pairwise.preference must be candidate, compared, or tie")
            if not isinstance(pairwise.get("reason"), str) or not pairwise.get("reason", "").strip():
                errors.append("pairwise.reason must be a non-empty string")
    return errors


def _ensure_list(values: Iterable[str] | None) -> list[str]:
    return [str(value) for value in (values or ())]


def make_feedback_record(
    run_root: Path,
    *,
    candidate_id: str,
    reviewer: str,
    decision: str,
    summary: str,
    rank: int | None = None,
    scores: dict[str, int] | None = None,
    common_scores: dict[str, int] | None = None,
    specialized_scores: dict[str, int] | None = None,
    accepted_parts: Iterable[str] | None = None,
    rejected_parts: Iterable[str] | None = None,
    reject_reasons: Iterable[str] | None = None,
    next_mutation: Iterable[str] | None = None,
    mutation_allowed: bool | None = None,
    pairwise: dict[str, str] | None = None,
    target_style_profile: dict[str, Any] | None = None,
    observed_style_profile: dict[str, Any] | None = None,
    style_match_decision: str | None = None,
    style_mismatch_dimensions: Iterable[str] | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    run_manifest_path = run_root / "run_manifest.json"
    run_manifest = _load_json(run_manifest_path) if run_manifest_path.is_file() else {}
    run_id = str(run_manifest.get("run_id") or run_root.name)
    effect_family, trace = _candidate_trace(run_root, candidate_id)
    if target_style_profile is None:
        _spec_path, candidate_spec = _find_candidate_spec(run_root, candidate_id)
        candidate_target_style = candidate_spec.get("target_style_profile") if isinstance(candidate_spec, dict) else None
        if isinstance(candidate_target_style, dict):
            target_style_profile = candidate_target_style
    record: dict[str, Any] = {
        "schema_version": "human_feedback.v1",
        "run_id": run_id,
        "candidate_id": candidate_id,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at or datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "rank": rank,
        "mutation_allowed": mutation_allowed,
        "trace": trace,
        "feedback": {
            "summary": summary,
            "accepted_parts": _ensure_list(accepted_parts),
            "rejected_parts": _ensure_list(rejected_parts),
            "reject_reasons": _ensure_list(reject_reasons),
            "next_mutation": _ensure_list(next_mutation),
        },
    }
    if effect_family is not None:
        record["effect_family"] = effect_family
    if scores is not None:
        record["scores"] = dict(scores)
    if common_scores is not None:
        record["common_scores"] = dict(common_scores)
    if specialized_scores is not None:
        record["specialized_scores"] = dict(specialized_scores)
    if pairwise is not None:
        record["pairwise"] = dict(pairwise)
    if target_style_profile is not None:
        record["target_style_profile"] = dict(target_style_profile)
    if observed_style_profile is not None:
        record["observed_style_profile"] = dict(observed_style_profile)
    if style_match_decision is not None:
        record["style_match_decision"] = style_match_decision
    if style_mismatch_dimensions is not None:
        record["style_mismatch_dimensions"] = _ensure_list(style_mismatch_dimensions)
    errors = validate_feedback_record(record, expected_run_id=run_id, candidate_ids=discover_candidate_ids(run_root))
    if errors:
        raise FeedbackValidationError("; ".join(errors))
    return record


def append_feedback(run_root: Path, record: dict[str, Any], feedback_path: Path | None = None) -> Path:
    run_root = Path(run_root).resolve()
    run_manifest_path = run_root / "run_manifest.json"
    run_manifest = _load_json(run_manifest_path) if run_manifest_path.is_file() else {}
    expected_run_id = str(run_manifest.get("run_id") or run_root.name)
    errors = validate_feedback_record(record, expected_run_id=expected_run_id, candidate_ids=discover_candidate_ids(run_root))
    if errors:
        raise FeedbackValidationError("; ".join(errors))
    destination = _resolve_inside(run_root, feedback_path or Path("feedback.jsonl"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return destination


def summarize_feedback_file(run_root: Path, feedback_path: Path | None = None) -> dict[str, Any]:
    validation = validate_feedback_file(run_root, feedback_path)
    if not validation["valid"]:
        return {**validation, "ranked_candidates": [], "pairwise": {}}
    destination = Path(validation["path"])
    rows = [
        json.loads(line)
        for line in destination.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if destination.exists() else []
    rank_rows: dict[str, list[int]] = {}
    decision_counts: dict[str, dict[str, int]] = {}
    pairwise: dict[str, dict[str, int]] = {}
    for row in rows:
        candidate_id = str(row["candidate_id"])
        rank = row.get("rank")
        if isinstance(rank, int):
            rank_rows.setdefault(candidate_id, []).append(rank)
        decisions = decision_counts.setdefault(candidate_id, {})
        decision = str(row["decision"])
        decisions[decision] = decisions.get(decision, 0) + 1
        comparison = row.get("pairwise")
        if isinstance(comparison, dict):
            compared = str(comparison["compared_candidate_id"])
            preference = str(comparison["preference"])
            pairwise.setdefault(candidate_id, {"wins": 0, "losses": 0, "ties": 0})
            pairwise.setdefault(compared, {"wins": 0, "losses": 0, "ties": 0})
            if preference == "candidate":
                pairwise[candidate_id]["wins"] += 1
                pairwise[compared]["losses"] += 1
            elif preference == "compared":
                pairwise[candidate_id]["losses"] += 1
                pairwise[compared]["wins"] += 1
            else:
                pairwise[candidate_id]["ties"] += 1
                pairwise[compared]["ties"] += 1
    ranked = []
    for candidate_id, ranks in rank_rows.items():
        ranked.append(
            {
                "candidate_id": candidate_id,
                "average_rank": round(sum(ranks) / len(ranks), 3),
                "review_count": len(ranks),
                "decisions": decision_counts.get(candidate_id, {}),
            }
        )
    ranked.sort(key=lambda row: (row["average_rank"], row["candidate_id"]))
    return {
        **validation,
        "ranked_candidates": ranked,
        "pairwise": pairwise,
        "decision_counts": decision_counts,
    }


def validate_feedback_file(run_root: Path, feedback_path: Path | None = None) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    destination = _resolve_inside(run_root, feedback_path or Path("feedback.jsonl"))
    if not destination.exists():
        return {"valid": True, "path": destination.as_posix(), "record_count": 0, "errors": []}
    run_manifest = _load_json(run_root / "run_manifest.json") if (run_root / "run_manifest.json").is_file() else {}
    expected_run_id = str(run_manifest.get("run_id") or run_root.name)
    candidate_ids = discover_candidate_ids(run_root)
    errors: list[dict[str, Any]] = []
    record_count = 0
    for line_number, line in enumerate(destination.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record_count += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": line_number, "error": f"invalid JSON: {exc}"})
            continue
        if not isinstance(record, dict):
            errors.append({"line": line_number, "error": "feedback record must be an object"})
            continue
        record_errors = validate_feedback_record(record, expected_run_id=expected_run_id, candidate_ids=candidate_ids)
        for error in record_errors:
            errors.append({"line": line_number, "error": error})
    return {"valid": not errors, "path": destination.as_posix(), "record_count": record_count, "errors": errors}


def _parse_scores(values: list[str] | None) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for item in values or []:
        if "=" not in item:
            raise FeedbackValidationError(f"score must use name=value: {item}")
        name, raw_value = item.split("=", 1)
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise FeedbackValidationError(f"score must be an integer: {item}") from exc
        parsed[name] = value
    return parsed


def _load_optional_profile(path: Path | None) -> dict[str, Any] | None:
    return _load_json(path) if path is not None else None


def _add_common_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--rank", type=int)
    parser.add_argument("--score", action="append", default=[])
    parser.add_argument("--common-score", action="append", default=[])
    parser.add_argument("--specialized-score", action="append", default=[])
    parser.add_argument("--accepted-part", action="append", default=[])
    parser.add_argument("--rejected-part", action="append", default=[])
    parser.add_argument("--reject-reason", action="append", default=[])
    parser.add_argument("--next-mutation", action="append", default=[])
    parser.add_argument("--mutation-allowed", action="store_true")
    parser.add_argument("--compared-candidate-id")
    parser.add_argument("--preference", choices=sorted(PAIRWISE_PREFERENCES))
    parser.add_argument("--comparison-reason")
    parser.add_argument("--target-style-profile", type=Path)
    parser.add_argument("--observed-style-profile", type=Path)
    parser.add_argument("--style-match", choices=sorted(STYLE_MATCH_DECISIONS))
    parser.add_argument("--style-mismatch-dimension", action="append", default=[])
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--output", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and validate structured VFX candidate feedback.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create", help="create one feedback record")
    _add_common_create_arguments(create_parser)
    append_parser = subparsers.add_parser("append", help="append an existing JSON record")
    append_parser.add_argument("--run-root", type=Path, required=True)
    append_parser.add_argument("--record", type=Path, required=True)
    append_parser.add_argument("--feedback-path", type=Path)
    validate_parser = subparsers.add_parser("validate", help="validate feedback.jsonl")
    validate_parser.add_argument("--run-root", type=Path, required=True)
    validate_parser.add_argument("--feedback-path", type=Path)
    summarize_parser = subparsers.add_parser("summarize", help="summarize valid feedback records")
    summarize_parser.add_argument("--run-root", type=Path, required=True)
    summarize_parser.add_argument("--feedback-path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            pairwise = None
            if args.compared_candidate_id or args.preference or args.comparison_reason:
                pairwise = {
                    "compared_candidate_id": args.compared_candidate_id,
                    "preference": args.preference,
                    "reason": args.comparison_reason,
                }
            record = make_feedback_record(
                args.run_root,
                candidate_id=args.candidate_id,
                reviewer=args.reviewer,
                decision=args.decision,
                summary=args.summary,
                rank=args.rank,
                scores=_parse_scores(args.score) or None,
                common_scores=_parse_scores(args.common_score) or None,
                specialized_scores=_parse_scores(args.specialized_score) or None,
                accepted_parts=args.accepted_part,
                rejected_parts=args.rejected_part,
                reject_reasons=args.reject_reason,
                next_mutation=args.next_mutation,
                mutation_allowed=args.mutation_allowed,
                pairwise=pairwise,
                target_style_profile=_load_optional_profile(args.target_style_profile),
                observed_style_profile=_load_optional_profile(args.observed_style_profile),
                style_match_decision=args.style_match,
                style_mismatch_dimensions=args.style_mismatch_dimension or None,
            )
            if args.append:
                append_feedback(args.run_root, record)
            if args.output:
                destination = _resolve_inside(Path(args.run_root).resolve(), args.output)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0
        if args.command == "append":
            record = _load_json(args.record)
            path = append_feedback(args.run_root, record, args.feedback_path)
            print(json.dumps({"path": path.as_posix(), "appended": True}, ensure_ascii=False))
            return 0
        if args.command == "summarize":
            result = summarize_feedback_file(args.run_root, args.feedback_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 1
        result = validate_feedback_file(args.run_root, args.feedback_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1
    except (FeedbackValidationError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
