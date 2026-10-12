"""Normalize course evidence and human VFX reviews into the aesthetic record contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


RECORD_SCHEMA = "vfx_aesthetic_record.v1"
DATASET_SCHEMA = "vfx_aesthetic_dataset.v1"
SCORE_NAMES = ("core_readability", "layer_separation", "rhythm", "material", "composition")
STYLE_FAMILIES = ("realistic", "stylized", "cartoon", "anime", "fantasy_painterly", "ui_graphic", "mixed", "unknown")
EFFECT_FAMILIES = ("slash", "fire", "lightning", "shield", "smoke", "explosion", "magic_circle", "water", "ice", "energy", "unknown", "unclassified")


class AestheticExportError(ValueError):
    """Raised when an input cannot be normalized without inventing labels."""


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AestheticExportError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise AestheticExportError(f"invalid JSONL {path}:{line_number}: {error}") from error
        if not isinstance(value, dict):
            raise AestheticExportError(f"JSON object expected: {path}:{line_number}")
        rows.append(value)
    return rows


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


def _resolve_path(value: str, source_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    repo_candidate = (_repo_root() / path).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return (source_path.parent / path).resolve()


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_inputs(inputs: Iterable[Path]) -> list[Path]:
    paths: set[Path] = set()
    for raw in inputs:
        path = raw.resolve()
        if not path.exists():
            raise FileNotFoundError(f"aesthetic input does not exist: {path}")
        if path.is_file():
            paths.add(path)
        else:
            paths.update(candidate.resolve() for candidate in path.rglob("*") if candidate.is_file() and candidate.suffix.lower() in {".md", ".txt", ".srt"})
    return sorted(paths, key=lambda item: item.as_posix().casefold())


def _chunks(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []
    chunks: list[dict[str, Any]] = []
    heading = path.stem
    body: list[str] = []
    start_line = 1

    def flush(end_line: int) -> None:
        nonlocal body, start_line
        text = "\n".join(body).strip()
        if text:
            chunks.append({"heading": heading, "text": text[:4000], "line_start": start_line, "line_end": end_line})
        body = []
        start_line = end_line + 1

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("#"):
            flush(line_number - 1)
            heading = line.lstrip("# ").strip() or path.stem
            start_line = line_number
        else:
            body.append(line)
    flush(len(lines))
    return chunks or [{"heading": path.stem, "text": "\n".join(lines)[:4000], "line_start": 1, "line_end": len(lines)}]


def _source_kind(path: Path) -> str:
    normalized = path.as_posix().casefold()
    if "/knowledge/cards/" in normalized:
        return "knowledge_card"
    if "/knowledge/experiments/" in normalized:
        return "unity_run"
    if path.suffix.lower() == ".srt" or "visual_review" in normalized or "/transcripts/" in normalized:
        return "course_review"
    return "reference_video"


def _effect_family(text: str) -> str:
    lowered = text.casefold()
    terms = {
        "slash": ("刀光", "弧线", "blade", "slash"),
        "fire": ("火焰", "烟花", "火星", "fire", "flame"),
        "lightning": ("雷电", "闪电", "lightning", "thunder"),
        "shield": ("护盾", "屏障", "shield"),
        "smoke": ("烟雾", "烟尘", "smoke"),
        "explosion": ("爆炸", "冲击波", "爆发", "explosion"),
        "magic_circle": ("法阵", "符文", "magic circle"),
        "water": ("水系", "水柱", "浪花", "water"),
        "ice": ("冰冻", "冰晶", "ice"),
        "energy": ("能量", "energy"),
    }
    for family, candidates in terms.items():
        if any(term.casefold() in lowered for term in candidates):
            return family
    return "unknown"


def _timecodes(text: str) -> list[str]:
    return sorted(set(re.findall(r"\b\d{1,3}:\d{2}(?::\d{2})?\s*[–-]\s*\d{1,3}:\d{2}(?::\d{2})?\b", text)))[:20]


def _record_id(dataset_id: str, source_path: Path, suffix: str) -> str:
    raw = f"{dataset_id}|{source_path.resolve().as_posix()}|{suffix}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _eligibility(*, judge: bool = False, preference: bool = False, controller: bool = False, reasons: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "aesthetic_judge": judge,
        "preference_training": preference,
        "controller_sft": controller,
        "positive_generation_supervision": False,
        "excluded_reasons": sorted(set(str(reason) for reason in reasons)),
    }


def _scope(*, family: str, style: str = "unknown", keywords: Iterable[str] = (), prompt_id: str | None = None, candidates: Iterable[str] = (), context: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "effect_family": family if family in EFFECT_FAMILIES else "unknown",
        "style_family": style if style in STYLE_FAMILIES else "unknown",
        "style_keywords": sorted(set(str(value) for value in keywords if str(value))),
        "prompt_id": prompt_id,
        "candidate_ids": sorted(set(str(value) for value in candidates if str(value))),
        "scene_context": sorted(set(str(value) for value in context if str(value))),
    }


def _evidence(*, visibility: str, status: str, technical: str, independent: bool, continuous: bool, channel: str, notes: str = "") -> dict[str, Any]:
    return {
        "visibility_status": visibility,
        "evidence_status": status,
        "technical_status": technical,
        "independent_visual_evidence": independent,
        "continuous_frame_evidence": continuous,
        "visual_review_channel": channel,
        "evidence_notes": notes,
    }


def _provenance(source_path: Path, *, source_kind: str, source_record_id: str | None = None, run_id: str | None = None, run_manifest_path: str | None = None, spec_path: str | None = None, prefab_path: str | None = None, render_candidate_id: str | None = None, timecodes: Iterable[str] = (), frames: Iterable[str] = (), parents: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "source_kind": source_kind,
        "source_path": _portable(source_path),
        "source_record_id": source_record_id,
        "source_sha256": _sha256(source_path),
        "run_id": run_id,
        "run_manifest_path": run_manifest_path,
        "spec_path": spec_path,
        "prefab_path": prefab_path,
        "render_candidate_id": render_candidate_id,
        "timecodes": sorted(set(str(value) for value in timecodes if str(value))),
        "frame_paths": sorted(set(str(value) for value in frames if str(value))),
        "parent_record_ids": sorted(set(str(value) for value in parents if str(value))),
    }


def _validate_record(record: dict[str, Any]) -> None:
    schema_path = _repo_root() / "workspace/data/vfx_generation/schemas/aesthetic_record.schema.json"
    errors = sorted(Draft202012Validator(_read_json(schema_path)).iter_errors(record), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise AestheticExportError(f"aesthetic record schema error at {location}: {errors[0].message}")


def _observation_record(dataset_id: str, path: Path, chunk_index: int, chunk: dict[str, Any]) -> dict[str, Any]:
    text = str(chunk["text"])
    family = _effect_family(f"{path.as_posix()}\n{chunk['heading']}\n{text}")
    record = {
        "schema_version": RECORD_SCHEMA,
        "record_id": _record_id(dataset_id, path, f"observation:{chunk_index}"),
        "record_kind": "observation",
        "provenance": _provenance(path, source_kind=_source_kind(path), source_record_id=f"{path.stem}:{chunk['line_start']}", timecodes=_timecodes(text)),
        "scope": _scope(family=family),
        "evidence": _evidence(
            visibility="blocked_environment",
            status="pending",
            technical="not_run",
            independent=False,
            continuous=False,
            channel="none",
            notes="资料文本已索引；尚未绑定可直接复核的连续画面，特效族仅为文本检索提示。",
        ),
        "payload": {
            "observation": text[:1200],
            "rule_candidate": None,
            "axes": [],
            "polarity": "unknown",
            "confidence": "unknown",
            "requires_unity_validation": True,
        },
        "training_eligibility": _eligibility(reasons=["observation_only", "no_independent_visual_evidence", "requires_unity_validation"]),
    }
    _validate_record(record)
    return record


def _frame_paths(label: dict[str, Any]) -> list[str]:
    trace = label.get("trace") if isinstance(label.get("trace"), dict) else {}
    values = trace.get("render_paths") if isinstance(trace.get("render_paths"), list) else []
    return [str(value) for value in values if str(value) and str(value) != "not_rendered"]


def _frame_evidence(source_path: Path, label: dict[str, Any]) -> tuple[list[str], bool, bool]:
    frames = _frame_paths(label)
    if not frames:
        return [], False, False
    existing = [_resolve_path(frame, source_path) for frame in frames]
    independent = all(path.is_file() for path in existing)
    return frames, independent, independent and len(frames) >= 2


def _load_review_metadata(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = _read_json(path.resolve())
        rows = payload.get("records") if isinstance(payload.get("records"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            candidate_id = str(row.get("candidate_id") or "")
            if candidate_id:
                if candidate_id in metadata:
                    raise AestheticExportError(f"duplicate review metadata candidate: {candidate_id}")
                metadata[candidate_id] = row
    return metadata


def _trace_run_id(frames: Iterable[str], fallback: str | None = None) -> str | None:
    for frame in frames:
        parts = str(frame).replace("\\", "/").split("/")
        if "runs" in parts:
            index = parts.index("runs")
            if index + 1 < len(parts) and parts[index + 1]:
                return parts[index + 1]
    return fallback


def _human_label_record(dataset_id: str, source_path: Path, label: dict[str, Any], parent: dict[str, Any] | None = None) -> dict[str, Any] | None:
    parent = parent if isinstance(parent, dict) else {}
    candidate_id = str(label.get("candidate_id") or "")
    scores = label.get("scores") if isinstance(label.get("scores"), dict) else {}
    if not candidate_id or any(name not in scores or not isinstance(scores[name], int) for name in SCORE_NAMES):
        return None
    frames, independent, continuous = _frame_evidence(source_path, label)
    trace = label.get("trace") if isinstance(label.get("trace"), dict) else {}
    decision = str(label.get("decision") or "")
    style = str(label.get("style_family") or "unknown")
    source_prefab = parent.get("source_prefab") if isinstance(parent.get("source_prefab"), dict) else {}
    prefab_path = str(trace.get("prefab_path") or source_prefab.get("prefab_path") or "")
    source_family = str(parent.get("effect_family_hint") or source_prefab.get("effect_family_hint") or "")
    family = source_family if source_family in EFFECT_FAMILIES else _effect_family(prefab_path)
    source_categories = parent.get("source_category") if isinstance(parent.get("source_category"), list) else source_prefab.get("source_category") if isinstance(source_prefab.get("source_category"), list) else []
    technical = str(trace.get("auto_eval_status") or "unknown")
    technical_status = technical if technical in {"pass", "warn", "reject", "unknown"} else "unknown"
    record = {
        "schema_version": RECORD_SCHEMA,
        "record_id": _record_id(dataset_id, source_path, f"human_label:{candidate_id}:{label.get('reviewed_at', '')}"),
        "record_kind": "human_label",
        "provenance": _provenance(
            source_path,
            source_kind="human_feedback",
            source_record_id=candidate_id,
            run_id=_trace_run_id(frames, str(label.get("batch_id") or "") or None),
            prefab_path=prefab_path or None,
            render_candidate_id=str(trace.get("render_candidate_id") or "") or None,
            frames=frames,
        ),
        "scope": _scope(
            family=family,
            style=style,
            keywords=label.get("style_keywords") or [],
            candidates=[candidate_id],
            context=source_categories,
        ),
        "evidence": _evidence(
            visibility="visible" if independent and continuous and decision != "not_visible" and technical_status in {"pass", "warn"} else "not_visible",
            status="observed",
            technical="pass" if technical_status == "pass" else "warn" if technical_status == "warn" else technical_status,
            independent=independent,
            continuous=continuous,
            channel="local_browser" if independent else "none",
            notes="人工评价已保存；训练资格仍由统一门禁决定。",
        ),
        "payload": {
            "reviewer": str(label.get("reviewer") or "unknown"),
            "reviewed_at": str(label.get("reviewed_at") or ""),
            "decision": decision,
            "quality_score": int(label.get("quality_score") or 1),
            "scores": {name: int(scores[name]) for name in SCORE_NAMES},
            "style_match_decision": "unlabeled",
            "layer_roles": {
                "core": str((label.get("layer_roles") or {}).get("core") or ""),
                "support": str((label.get("layer_roles") or {}).get("support") or ""),
                "hit": str((label.get("layer_roles") or {}).get("hit") or ""),
                "residual": str((label.get("layer_roles") or {}).get("residual") or ""),
            },
            "reusable_layers": list(label.get("reusable_layers") or []),
            "issues": list(label.get("issues") or []),
            "summary": str(label.get("summary") or ""),
            "notes": str(label.get("notes") or ""),
            "confirmation_mode": str(label.get("confirmation_mode") or "human_accepted_ai_draft"),
        },
        "training_eligibility": _eligibility(
            judge=independent and continuous and decision in {"accept_reference", "partial", "reject"} and technical_status in {"pass", "warn"},
            reasons=([] if independent and continuous else ["no_independent_visual_evidence", "continuous_frame_evidence_required"])
            + ([] if technical_status in {"pass", "warn"} else ["technical_status_not_ready"]),
        ),
    }
    _validate_record(record)
    return record


def _technical_exclusion_record(dataset_id: str, source_path: Path, row: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(row.get("candidate_id") or "")
    reason = str(row.get("exclusion_reason") or row.get("reason") or "technical_or_visual_evidence_not_ready")
    category = "context" if "context" in reason or "visual" in reason else "runtime"
    technical = str(row.get("technical_status") or "unknown")
    technical = technical if technical in {"pass", "warn", "reject", "unknown", "not_run", "context_required"} else "unknown"
    record = {
        "schema_version": RECORD_SCHEMA,
        "record_id": _record_id(dataset_id, source_path, f"technical_exclusion:{candidate_id}:{reason}"),
        "record_kind": "technical_exclusion",
        "provenance": _provenance(
            source_path,
            source_kind="human_feedback" if row.get("human_feedback") else "unity_run",
            source_record_id=candidate_id or None,
            prefab_path=str(row.get("prefab_path") or "") or None,
            render_candidate_id=str(row.get("render_candidate_id") or "") or None,
            frames=[],
        ),
        "scope": _scope(family=_effect_family(str(row.get("prefab_path") or "")), candidates=[candidate_id]),
        "evidence": _evidence(
            visibility="not_visible",
            status="excluded",
            technical=technical,
            independent=False,
            continuous=False,
            channel="none",
            notes="技术或可见性排除，不代表审美质量负例。",
        ),
        "payload": {
            "exclusion_category": category,
            "exclusion_code": reason,
            "reason": str(row.get("reason") or reason),
        },
        "training_eligibility": _eligibility(reasons=[reason, "technical_exclusion_is_not_aesthetic_negative"]),
    }
    _validate_record(record)
    return record


def _prompt_or_web_observation(dataset_id: str, source_path: Path, row: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(row.get("candidate_id") or "")
    trace = row.get("trace") if isinstance(row.get("trace"), dict) else {}
    frames = [str(value) for value in trace.get("render_paths", []) if str(value) and str(value) != "not_rendered"]
    frames, independent, continuous = _frame_evidence(source_path, {"trace": {"render_paths": frames}})
    feedback = row.get("feedback") if isinstance(row.get("feedback"), dict) else {}
    conditions = row.get("conditions") if isinstance(row.get("conditions"), dict) else {}
    summary = str(feedback.get("summary") or row.get("summary") or "")
    if conditions:
        summary = "；".join(f"{key}:{value}" for key, value in sorted(conditions.items()))
    record = {
        "schema_version": RECORD_SCHEMA,
        "record_id": _record_id(dataset_id, source_path, f"non_quality_feedback:{candidate_id}:{row.get('reviewed_at', '')}"),
        "record_kind": "observation",
        "provenance": _provenance(
            source_path,
            source_kind="human_feedback",
            source_record_id=candidate_id or None,
            run_id=str(row.get("run_id") or row.get("batch_id") or "") or None,
            prefab_path=str(trace.get("prefab_path") or "") or None,
            render_candidate_id=str(trace.get("render_candidate_id") or "") or None,
            frames=frames,
        ),
        "scope": _scope(family=_effect_family(str(trace.get("prefab_path") or row.get("effect_family") or "")), candidates=[candidate_id]),
        "evidence": _evidence(
            visibility="visible" if independent else "not_visible",
            status="observed" if independent else "excluded",
            technical="pass" if independent else "unknown",
            independent=independent,
            continuous=continuous,
            channel="local_browser" if independent else "none",
            notes="Prompt条件或动态反馈不是完整审美质量标签，保持为观察记录。",
        ),
        "payload": {
            "observation": summary or "反馈存在，但没有完整通用审美五维标签。",
            "rule_candidate": "；".join(str(value) for value in (feedback.get("next_mutation") or [])) or None,
            "axes": ["rhythm"] if isinstance(row.get("scores"), dict) and "rhythm_quality" in row["scores"] else [],
            "polarity": "unknown",
            "confidence": "unknown",
            "requires_unity_validation": False,
        },
        "training_eligibility": _eligibility(reasons=["prompt_or_web_feedback_is_not_complete_aesthetic_quality_label"]),
    }
    _validate_record(record)
    return record


def _normalize_feedback_row(dataset_id: str, source_path: Path, row: dict[str, Any], metadata: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    schema_version = str(row.get("schema_version") or "")
    if schema_version.endswith("human_label_overlay.v1") and isinstance(row.get("human_label"), dict):
        label = dict(row["human_label"])
        label.setdefault("trace", row.get("trace"))
        label.setdefault("batch_id", row.get("batch_id"))
        label_trace = label.get("trace") if isinstance(label.get("trace"), dict) else {}
        if str(label.get("decision") or "") == "not_visible" or not _frame_paths(label):
            return None, "human_not_visible_no_training_label"
        if str(label_trace.get("auto_eval_status") or "unknown") == "reject":
            return None, "technical_render_rejected_no_aesthetic_label"
        record = _human_label_record(dataset_id, source_path, label, {**(metadata or {}), **row})
        if record is not None:
            return record, None
        return None, "incomplete_aesthetic_dimensions"
    if schema_version == "prefab_human_feedback.v1":
        if str(row.get("decision") or "") == "not_visible" or not _frame_paths(row):
            return None, "human_not_visible_no_training_label"
        if str((row.get("trace") or {}).get("auto_eval_status") or "unknown") == "reject":
            return None, "technical_render_rejected_no_aesthetic_label"
        record = _human_label_record(dataset_id, source_path, row, metadata)
        return (record, None) if record is not None else (None, "incomplete_aesthetic_dimensions")
    if schema_version in {"human_feedback.v1", "prompt_condition_human_feedback.v1"} or isinstance(row.get("conditions"), dict):
        return _prompt_or_web_observation(dataset_id, source_path, row), None
    return None, "unsupported_feedback_schema"


def build_aesthetic_dataset(
    knowledge_inputs: Iterable[Path],
    feedback_paths: Iterable[Path],
    exclusion_paths: Iterable[Path],
    output_dir: Path,
    dataset_id: str,
    review_batch_paths: Iterable[Path] = (),
) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"aesthetic dataset output already exists and is not empty: {output_dir}")
    knowledge_inputs = list(knowledge_inputs)
    feedback_paths = [Path(path).resolve() for path in feedback_paths]
    exclusion_paths = [Path(path).resolve() for path in exclusion_paths]
    review_batch_paths = [Path(path).resolve() for path in review_batch_paths]
    review_metadata = _load_review_metadata(review_batch_paths)
    records: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    source_paths: set[str] = set()

    for path in _file_inputs(knowledge_inputs):
        source_paths.add(str(path))
        for index, chunk in enumerate(_chunks(path), start=1):
            records.append(_observation_record(dataset_id, path, index, chunk))

    for path in [*feedback_paths, *exclusion_paths, *review_batch_paths]:
        if not path.is_file():
            raise FileNotFoundError(f"feedback input does not exist: {path}")
        source_paths.add(str(path))
    for path in feedback_paths:
        for row in _read_jsonl(path):
            record, reason = _normalize_feedback_row(dataset_id, path, row, review_metadata.get(str(row.get("candidate_id") or "")))
            if record is not None:
                records.append(record)
            elif reason:
                exclusions.append(_technical_exclusion_record(dataset_id, path, {
                    "candidate_id": row.get("candidate_id"),
                    "prefab_path": ((row.get("trace") or {}).get("prefab_path") if isinstance(row.get("trace"), dict) else ""),
                    "exclusion_reason": reason,
                    "reason": reason,
                    "technical_status": ((row.get("trace") or {}).get("auto_eval_status") if isinstance(row.get("trace"), dict) else "unknown"),
                    "human_feedback": row,
                }))
    for path in exclusion_paths:
        for row in _read_jsonl(path):
            exclusions.append(_technical_exclusion_record(dataset_id, path, row))

    if not records and not exclusions:
        raise AestheticExportError("no knowledge, feedback or exclusion records were produced")

    for record in records:
        _validate_record(record)
    for record in exclusions:
        _validate_record(record)

    judge = [record for record in records if record["training_eligibility"]["aesthetic_judge"]]
    preference = [record for record in records if record["training_eligibility"]["preference_training"]]
    observations = [record for record in records if record["record_kind"] == "observation"]
    human_labels = [record for record in records if record["record_kind"] == "human_label"]
    all_records_path = _write_jsonl(output_dir / "aesthetic_records.jsonl", records)
    observation_path = _write_jsonl(output_dir / "reference_observations.jsonl", observations)
    feedback_path = _write_jsonl(output_dir / "aesthetic_feedback.jsonl", human_labels)
    judge_path = _write_jsonl(output_dir / "aesthetic_judge_records.jsonl", judge)
    exclusion_path = _write_jsonl(output_dir / "technical_exclusions.jsonl", exclusions)
    summary = {
        "schema_version": DATASET_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "source_count": len(source_paths),
        "record_count": len(records),
        "record_kind_counts": dict(sorted(Counter(record["record_kind"] for record in records).items())),
        "judge_eligible_count": len(judge),
        "preference_eligible_count": len(preference),
        "technical_exclusion_count": len(exclusions),
        "files": {
            "records": all_records_path.name,
            "reference_observations": observation_path.name,
            "aesthetic_feedback": feedback_path.name,
            "judge_records": judge_path.name,
            "technical_exclusions": exclusion_path.name,
        },
        "policy": {
            "source_text_is_not_visual_quality_label": True,
            "prompt_condition_feedback_is_not_aesthetic_quality_label": True,
            "technical_exclusion_is_not_aesthetic_negative": True,
            "not_visible_is_not_training_data": True,
            "ai_draft_is_not_human_label": True,
        },
        "status": "pass",
    }
    manifest_schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/aesthetic_dataset_manifest.schema.json")
    errors = sorted(Draft202012Validator(manifest_schema).iter_errors(summary), key=lambda error: list(error.path))
    if errors:
        raise AestheticExportError(f"aesthetic dataset manifest schema error: {errors[0].message}")
    manifest_path = _write_json(output_dir / "aesthetic_dataset_manifest.json", summary)
    return {
        "manifest": manifest_path,
        "records": all_records_path,
        "reference_observations": observation_path,
        "aesthetic_feedback": feedback_path,
        "judge_records": judge_path,
        "exclusions": exclusion_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize VFX aesthetic evidence and human review records.")
    parser.add_argument("--knowledge-input", type=Path, action="append", default=[])
    parser.add_argument("--human-feedback", type=Path, action="append", default=[])
    parser.add_argument("--technical-exclusion", type=Path, action="append", default=[])
    parser.add_argument("--review-batch", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    args = parser.parse_args(argv)
    try:
        paths = build_aesthetic_dataset(args.knowledge_input, args.human_feedback, args.technical_exclusion, args.output_dir, args.dataset_id, args.review_batch)
    except (AestheticExportError, FileNotFoundError, FileExistsError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
