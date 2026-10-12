"""Build and serve an all-Prefab human review queue using only Chinese fixed-choice controls."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

from jsonschema import Draft202012Validator, FormatChecker
import cv2
import numpy as np


BATCH_SCHEMA = "prefab_human_review_batch.v3"
STORE_SCHEMA = "prefab_human_feedback_store.v2"
VISIBLE_THRESHOLD = 0.01
AUTO_STATUS_CN = {"pass": "自动可见", "warn": "主体偏小", "reject": "当前不可见", "unknown": "未渲染"}
TECHNICAL_STATUS_CN = {
    "particle_playable": "可独立播放", "particle_context_required": "需要运行上下文",
    "static_or_contextual": "静态或需上下文", "empty_or_invalid": "当前无有效输出", "audit_error": "审计异常",
    "composition_technical_pass": "组合执行通过",
}

AI_DRAFT_SCHEMA = "prefab_ai_review_draft.v1"
WEBGL_CATALOG_SCHEMA = "vfx_web_review_catalog.v1"
WEBGL_STATUS_CN = {
    "webgl_ready": "真实 WebGL 预览可用",
    "needs_context": "需要角色、UI、脚本或战斗上下文",
    "not_in_direct_playable_set": "当前无独立 WebGL 输出",
    "build_excluded": "未纳入本次独立 WebGL 构建",
}
TECHNICAL_EXCLUSION_ROUTES = {"需要上下文", "当前无有效输出"}


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


def _feedback_validator() -> Draft202012Validator:
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_human_feedback.schema.json")
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _ai_draft_validator() -> Draft202012Validator:
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/prefab_ai_review_draft.schema.json")
    return Draft202012Validator(schema)


def _read_cv_image(path: Path, flags: int) -> np.ndarray | None:
    try:
        return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), flags)
    except OSError:
        return None


def _pixel_metrics(frame_path: Path) -> dict[str, float]:
    image = _read_cv_image(frame_path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"could not read review frame: {frame_path}")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners = np.concatenate((
        image[:8, :8].reshape(-1, 3), image[:8, -8:].reshape(-1, 3),
        image[-8:, :8].reshape(-1, 3), image[-8:, -8:].reshape(-1, 3),
    ))
    background = np.median(corners, axis=0).astype(np.uint8)
    difference = cv2.cvtColor(cv2.absdiff(image, background), cv2.COLOR_BGR2GRAY)
    mask = difference > 8
    visible = float(mask.mean())
    saturation = float(hsv[:, :, 1][mask].mean() / 255.0) if mask.any() else 0.0
    brightness = float(gray[mask].mean() / 255.0) if mask.any() else 0.0
    edges = cv2.Canny(gray, 40, 120)
    edge_density = float((edges[mask] > 0).mean()) if mask.any() else 0.0
    return {
        "visible_area_ratio": round(visible, 8),
        "saturation": round(saturation, 8),
        "brightness": round(brightness, 8),
        "edge_density": round(edge_density, 8),
    }


def _draft_for_record(batch_id: str, record: dict[str, Any]) -> dict[str, Any]:
    rendered = bool(record["frames"])
    reason_codes = []
    if not rendered:
        reason_codes.append("no_independent_render")
        if record["review_route"] == "需要上下文":
            reason_codes.append("runtime_context_required")
        else:
            reason_codes.append("no_effective_output")
        suggestion = {
            "decision": "not_visible", "style_family": "unknown", "style_keywords": [],
            "quality_score": 1,
            "scores": {"core_readability": 0, "layer_separation": 0, "rhythm": 0, "material": 0, "composition": 0},
            "layer_roles": {"core": "没有", "support": "没有", "hit": "没有", "residual": "没有"},
            "reusable_layers": ["无"], "issues": ["主体不清楚"], "summary": "无法判断",
        }
        return {
            "schema_version": AI_DRAFT_SCHEMA, "batch_id": batch_id, "candidate_id": record["candidate_id"],
            "status": "ai_draft_not_human_label", "confidence": 0.05, "suggested_feedback": suggestion,
            "evidence": {"review_route": record["review_route"], "technical_status": record["technical_status"], "rendered": False, "reason_codes": reason_codes},
        }
    paths = [Path(frame["path"]) for frame in record["frames"]]
    metrics = max((_pixel_metrics(path) for path in paths), key=lambda item: item["visible_area_ratio"])
    visible = metrics["visible_area_ratio"]
    motion = float(record["auto_eval"]["metrics"].get("frame_delta_mean") or 0.0)
    particles = int(record["particle_system_count"])
    if visible < VISIBLE_THRESHOLD:
        decision, quality, confidence = "not_visible", 1, 0.25
        reason_codes.extend(("subject_too_small", "insufficient_independent_preview"))
    elif visible < 0.03:
        decision, quality, confidence = "partial", 2, 0.35
        reason_codes.append("small_subject_area")
    elif visible < 0.07:
        decision, quality, confidence = "partial", 3, 0.45
        reason_codes.append("moderate_subject_area")
    else:
        decision, quality, confidence = "partial", 4, 0.52
        reason_codes.append("large_subject_area")
    if motion < 0.0002:
        reason_codes.append("low_detected_motion")
    style = "ui_graphic" if "ui" in record["source_category"] else "stylized" if metrics["saturation"] >= 0.25 else "unknown"
    keywords = []
    if metrics["saturation"] >= 0.45: keywords.append("高饱和")
    elif metrics["saturation"] <= 0.15: keywords.append("低饱和")
    if metrics["brightness"] >= 0.55: keywords.append("明亮")
    elif metrics["brightness"] <= 0.25: keywords.append("暗色")
    if particles >= 3: keywords.append("粒子感")
    if "ui" in record["source_category"]: keywords.append("UI感")
    if motion >= 0.001: keywords.append("能量感")
    if metrics["edge_density"] >= 0.12: keywords.append("尖锐")
    scores = {
        "core_readability": min(5, max(0, round(visible * 45))),
        "layer_separation": min(5, max(0, 1 + min(4, particles // 3))),
        "rhythm": min(5, max(0, round(motion * 1500))),
        "material": min(5, max(0, 2 + round(metrics["saturation"] * 3))),
        "composition": min(5, max(0, round(visible * 35))),
    }
    issues = []
    if visible < 0.03: issues.append("构图偏小")
    if motion < 0.0002: issues.append("节奏拖沓")
    if quality <= 2: issues.append("主体不清楚")
    if not issues: issues.append("无明显问题")
    suggestion = {
        "decision": decision, "style_family": style, "style_keywords": sorted(set(keywords)), "quality_score": quality,
        "scores": scores,
        "layer_roles": {
            "core": "清楚" if scores["core_readability"] >= 3 else "一般" if scores["core_readability"] >= 1 else "不清楚",
            "support": "有效" if particles >= 4 else "一般" if particles >= 2 else "没有",
            "hit": "有效" if motion >= 0.0015 else "一般" if motion >= 0.0003 else "没有",
            "residual": "有效" if float(record["prefab_summary"]["estimated_duration_seconds"]) >= 1.0 and motion >= 0.0005 else "没有",
        },
        "reusable_layers": ["粒子参数"] if quality >= 3 else ["无"],
        "issues": issues,
        "summary": {"accept_reference": "可作为参考", "partial": "部分可复用", "reject": "不建议参考", "not_visible": "无法判断"}[decision],
    }
    return {
        "schema_version": AI_DRAFT_SCHEMA, "batch_id": batch_id, "candidate_id": record["candidate_id"],
        "status": "ai_draft_not_human_label", "confidence": confidence, "suggested_feedback": suggestion,
        "evidence": {"review_route": record["review_route"], "technical_status": record["technical_status"], "rendered": True, "reason_codes": reason_codes, "pixel_metrics": metrics},
    }


def generate_ai_drafts(root: Path) -> Path:
    root = root.resolve()
    batch = _read_json(root / "review_batch.json")
    validator = _ai_draft_validator()
    drafts = []
    for record in batch["records"]:
        draft = _draft_for_record(batch["batch_id"], record)
        errors = list(validator.iter_errors(draft))
        if errors:
            raise ValueError(f"AI draft schema error for {record['candidate_id']}: {errors[0].message}")
        drafts.append(draft)
    return _write_jsonl(root / "ai_drafts.jsonl", drafts)


def _load_drafts(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "ai_drafts.jsonl"
    if not path.is_file():
        return {}
    return {str(row["candidate_id"]): row for row in _read_jsonl(path)}


_CAPTURE_FRAME_TIME = re.compile(r"frame_\d+_(\d+)_(\d+)\.(?:png|jpg|jpeg)$", re.IGNORECASE)


def _frame_time_seconds(path: str, fallback: int) -> float:
    match = _CAPTURE_FRAME_TIME.search(Path(path).name)
    if match is None:
        return float(fallback)
    return float(f"{match.group(1)}.{match.group(2)}")


def _build_records(dataset_root: Path, run_root: Path) -> list[dict[str, Any]]:
    examples = _read_jsonl(dataset_root / "examples.jsonl")
    records: list[dict[str, Any]] = []
    for example in examples:
        output = example["outputs"]
        evidence = output.get("render_evidence")
        summary = output["prefab_summary"]
        if evidence is None:
            visibility = "未渲染"
            review_route = "需要上下文" if summary["status"] in {"particle_context_required", "static_or_contextual"} else "当前无有效输出"
            frames: list[dict[str, Any]] = []
            auto_status = "unknown"
        else:
            metric = float(evidence["metrics"].get("visible_area_ratio_peak") or 0.0)
            auto_status = str(evidence["status"])
            visibility = "可见" if metric >= VISIBLE_THRESHOLD else "主体过小"
            review_route = "可评价" if metric >= VISIBLE_THRESHOLD else "主体过小"
            frames = [
                {"time_seconds": _frame_time_seconds(path, index), "path": path}
                for index, path in enumerate(output.get("diagnostic_render_paths", []))
            ]
        selection = example["inputs"].get("material_selection", {})
        records.append({
            "candidate_id": example["candidate_id"],
            "prefab_path": example["inputs"]["prefab_path"],
            "source_category": example["inputs"]["source_category"],
            "effect_family_hint": example["inputs"]["effect_family_hint"],
            "technical_status": summary["status"],
            "technical_status_cn": TECHNICAL_STATUS_CN.get(summary["status"], summary["status"]),
            "review_route": review_route,
            "visibility_status": visibility,
            "auto_eval": evidence or {"status": "unknown", "metrics": {}, "hard_reject_reasons": []},
            "auto_eval_status_cn": AUTO_STATUS_CN.get(auto_status, auto_status),
            "prefab_summary": summary,
            "particle_system_count": summary["particle_system_count"],
            "material_count": len(selection.get("materials", [])),
            "texture_count": sum(len(row.get("texture_bindings", [])) for row in selection.get("materials", [])),
            "frames": frames,
            "contact_sheet_path": output.get("contact_sheet_path"),
            "feedback_status": "pending",
        })
    return sorted(records, key=lambda row: row["candidate_id"])


def _load_webgl_catalog(path: Path) -> tuple[str, dict[str, dict[str, str]]]:
    catalog = _read_json(path.resolve())
    if catalog.get("schemaVersion") != WEBGL_CATALOG_SCHEMA:
        raise ValueError(f"unsupported WebGL review catalog: {catalog.get('schemaVersion')}")
    player_url = str(catalog.get("playerUrl") or "")
    if not player_url.startswith(("http://", "https://")):
        raise ValueError("WebGL review catalog has no http(s) playerUrl")
    entries: dict[str, dict[str, str]] = {}
    for entry in catalog.get("entries", []):
        if not isinstance(entry, dict):
            raise ValueError("WebGL review catalog entries must be objects")
        source_candidate_id = str(entry.get("candidateId") or "")
        candidate_id = str(entry.get("reviewCandidateId") or source_candidate_id)
        catalog_id = str(entry.get("catalogId") or "")
        source_path = str(entry.get("sourcePrefabPath") or "").replace("\\", "/")
        if not source_candidate_id or not candidate_id or not catalog_id or not source_path:
            raise ValueError("WebGL review catalog entry is incomplete")
        if candidate_id in entries:
            raise ValueError(f"WebGL review catalog repeats candidate: {candidate_id}")
        entries[candidate_id] = {
            "catalog_id": catalog_id,
            "source_prefab_path": source_path,
            "web_prefab_path": str(entry.get("webPrefabPath") or source_path).replace("\\", "/"),
        }
    if not entries:
        raise ValueError("WebGL review catalog has no entries")
    return player_url.rstrip("/") + "/", entries


def _attach_webgl_previews(records: list[dict[str, Any]], catalog_path: Path | None) -> dict[str, int]:
    player_url, catalog_entries = _load_webgl_catalog(catalog_path) if catalog_path is not None else ("", {})
    known_ids = {str(row["candidate_id"]) for row in records}
    unknown_ids = sorted(set(catalog_entries) - known_ids)
    if unknown_ids:
        raise ValueError(f"WebGL review catalog includes candidates outside this batch: {unknown_ids[0]}")

    for record in records:
        candidate_id = str(record["candidate_id"])
        mapped = catalog_entries.get(candidate_id)
        if mapped is not None:
            source_path = str(record["prefab_path"]).replace("\\", "/")
            if source_path != mapped["source_prefab_path"]:
                raise ValueError(f"WebGL source Prefab mismatch for {candidate_id}: {source_path} != {mapped['source_prefab_path']}")
            preview = {
                "status": "webgl_ready",
                "status_cn": WEBGL_STATUS_CN["webgl_ready"],
                "availability_reason_cn": "这条 Prefab 已从真实 Play Mode 训练样本构建进 Unity WebGL 播放器。",
                "player_url": player_url,
                "catalog_id": mapped["catalog_id"],
                "source_prefab_path": mapped["source_prefab_path"],
            }
        elif record["technical_status"] in {"particle_context_required", "static_or_contextual"}:
            preview = {
                "status": "needs_context",
                "status_cn": WEBGL_STATUS_CN["needs_context"],
                "availability_reason_cn": "该 Prefab 需要角色挂点、UI Canvas、脚本事件或战斗目标，空场景的 WebGL 播放不能替代原始上下文。",
            }
        elif record["technical_status"] == "particle_playable":
            preview = {
                "status": "build_excluded",
                "status_cn": WEBGL_STATUS_CN["build_excluded"],
                "availability_reason_cn": "这条 Prefab 未进入本次已验证的 59 条独立 Play Mode WebGL 集合。",
            }
        else:
            preview = {
                "status": "not_in_direct_playable_set",
                "status_cn": WEBGL_STATUS_CN["not_in_direct_playable_set"],
                "availability_reason_cn": "当前审计没有取得可作为独立 WebGL 预览依据的有效输出。",
            }
        record["webgl_preview"] = preview
    return dict(sorted(Counter(str(row["webgl_preview"]["status"]) for row in records).items()))


def build_review_batch(
    dataset_root: Path,
    run_root: Path,
    output_root: Path,
    batch_id: str,
    count: int | None = None,
    webgl_catalog_path: Path | None = None,
) -> dict[str, Path]:
    dataset_root, run_root, output_root = dataset_root.resolve(), run_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"review output already exists and is not empty: {output_root}")
    records = _build_records(dataset_root, run_root)
    if count is not None:
        records = records[:count]
    webgl_status_counts = _attach_webgl_previews(records, webgl_catalog_path)
    routes = Counter(row["review_route"] for row in records)
    technical = Counter(row["technical_status"] for row in records)
    batch = {
        "schema_version": BATCH_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_dataset": _portable(dataset_root / "dataset_manifest.json"),
        "source_run": _portable(run_root / "run_manifest.json"),
        "selection_strategy": "all_prefabs_technical_route.v1",
        "requested_count": len(records),
        "selected_count": len(records),
        "review_route_counts": dict(sorted(routes.items())),
        "technical_status_counts": dict(sorted(technical.items())),
        "webgl_catalog": _portable(webgl_catalog_path) if webgl_catalog_path is not None else None,
        "webgl_status_counts": webgl_status_counts,
        "records": [{"review_index": index, **row} for index, row in enumerate(records, start=1)],
    }
    batch_path = _write_json(output_root / "review_batch.json", batch)
    store_path = _write_json(output_root / "feedback_store.json", {"schema_version": STORE_SCHEMA, "batch_id": batch_id, "records": {}})
    feedback_path = _write_jsonl(output_root / "feedback.jsonl", [])
    return {"review_batch": batch_path, "feedback_store": store_path, "feedback": feedback_path}


def _composition_frame_delta_mean(paths: list[Path]) -> float:
    previous = None
    deltas = []
    for path in paths:
        image = _read_cv_image(path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f"could not read composition frame: {path}")
        image = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
        if previous is not None:
            deltas.append(float(cv2.absdiff(image, previous).mean()) / 255.0)
        previous = image
    return round(sum(deltas) / len(deltas), 8) if deltas else 0.0


def _source_label_note(label_context: dict[str, Any] | None) -> str:
    if not isinstance(label_context, dict):
        return "来源 Prefab 未使用人工审美标签；请只判断本次组合结果。"
    decision = {
        "accept_reference": "可作为参考", "partial": "部分可复用", "reject": "不建议参考",
    }.get(str(label_context.get("decision")), "未评价")
    style = {
        "realistic": "写实", "stylized": "风格化", "cartoon": "卡通", "anime": "动漫",
        "fantasy_painterly": "幻想绘制", "ui_graphic": "UI图形", "mixed": "混合", "unknown": "暂不判断",
    }.get(str(label_context.get("style_family")), "暂不判断")
    return f"来源 Prefab 标签：{decision} / {style}；仅用于检索，不代表本次组合结论。"


def build_composition_review_batch(composition_root: Path, output_root: Path, batch_id: str) -> dict[str, Path]:
    composition_root, output_root = composition_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"review output already exists and is not empty: {output_root}")
    composition = _read_json(composition_root / "composition_manifest.json")
    retrieval_path = Path(str(composition["retrieval_manifest_path"]))
    if not retrieval_path.is_absolute():
        retrieval_path = _repo_root() / retrieval_path
    retrieval = _read_json(retrieval_path)
    retrieval_by_id = {str(row["candidate_id"]): row for row in retrieval["candidates"]}
    records = []
    for index, candidate in enumerate(composition["candidates"], start=1):
        candidate_id = str(candidate["candidate_id"])
        proposal = retrieval_by_id.get(candidate_id)
        if proposal is None:
            raise ValueError(f"composition candidate is absent from retrieval manifest: {candidate_id}")
        result = _read_json(composition_root / "candidates" / candidate_id / "execution_result.json")
        frame_paths = [composition_root / "candidates" / candidate_id / "frames" / str(frame["path"]) for frame in result["frames"]]
        if any(not path.is_file() for path in frame_paths):
            raise FileNotFoundError(f"composition review frame is missing: {candidate_id}")
        independently_reviewable = candidate["execution_status"] == "technical_pass" and candidate["visual_status"] == "visible"
        source_summary = proposal["evidence"]["prefab_summary"]
        records.append({
            "review_index": index,
            "candidate_id": candidate_id,
            "review_subject": "prompt_composition",
            "review_subject_cn": "组合候选（本次运行结果）",
            "source_label_note": _source_label_note(proposal.get("human_label_context")),
            "prefab_path": candidate["source_prefab"]["prefab_path"],
            "source_category": candidate["source_prefab"]["source_category"],
            "effect_family_hint": candidate["source_prefab"]["effect_family_hint"],
            "technical_status": "composition_technical_pass" if independently_reviewable else "empty_or_invalid",
            "technical_status_cn": TECHNICAL_STATUS_CN["composition_technical_pass"] if independently_reviewable else TECHNICAL_STATUS_CN["empty_or_invalid"],
            "review_route": "可评价" if independently_reviewable else "当前无有效输出",
            "visibility_status": "可见" if independently_reviewable else "当前无有效输出",
            "auto_eval": {
                "status": "pass" if independently_reviewable else "unknown",
                "metrics": {
                    "visible_area_ratio_peak": candidate["max_visible_area_ratio"],
                    "frame_delta_mean": _composition_frame_delta_mean(frame_paths),
                },
                "hard_reject_reasons": [],
            },
            "auto_eval_status_cn": "自动可见" if independently_reviewable else "当前不可见",
            "prefab_summary": source_summary,
            "particle_system_count": int(source_summary["particle_system_count"]),
            "material_count": len(candidate["material_trajectory"].get("material_paths") or []),
            "texture_count": 0,
            "frames": [
                {"time_seconds": float(frame["requested_time_seconds"]), "path": _portable(path)}
                for frame, path in zip(result["frames"], frame_paths)
            ] if independently_reviewable else [],
            "contact_sheet_path": composition["contact_sheet_paths"][0],
            "feedback_status": "pending",
            "composition_manifest_path": _portable(composition_root / "composition_manifest.json"),
            "source_prefab_label": proposal.get("human_label_context"),
        })
    routes = Counter(str(row["review_route"]) for row in records)
    technical = Counter(str(row["technical_status"]) for row in records)
    batch = {
        "schema_version": BATCH_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "review_subject": "prompt_composition",
        "source_dataset": _portable(retrieval_path),
        "source_run": _portable(composition_root / "run_manifest.json"),
        "source_composition_manifest": _portable(composition_root / "composition_manifest.json"),
        "selection_strategy": "prompt_composition_visual_review.v1",
        "requested_count": len(records),
        "selected_count": len(records),
        "review_route_counts": dict(sorted(routes.items())),
        "technical_status_counts": dict(sorted(technical.items())),
        "webgl_catalog": None,
        "webgl_status_counts": {},
        "records": records,
    }
    batch_path = _write_json(output_root / "review_batch.json", batch)
    store_path = _write_json(output_root / "feedback_store.json", {"schema_version": STORE_SCHEMA, "batch_id": batch_id, "records": {}})
    feedback_path = _write_jsonl(output_root / "feedback.jsonl", [])
    return {"review_batch": batch_path, "feedback_store": store_path, "feedback": feedback_path}


def save_feedback(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    batch = _read_json(root / "review_batch.json")
    sources = {str(row["candidate_id"]): row for row in batch["records"]}
    candidate_id = str(payload.get("candidate_id") or "")
    if candidate_id not in sources:
        raise ValueError(f"candidate is not in review batch: {candidate_id}")
    source = sources[candidate_id]
    payload = dict(payload)
    ai_draft_changed = bool(payload.pop("ai_draft_changed", False))
    notes = payload.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("feedback notes must be a string")
    payload.update({
        "schema_version": "prefab_human_feedback.v1",
        "batch_id": batch["batch_id"],
        "candidate_id": candidate_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "local_human",
        "notes": notes.strip(),
        "confirmation_mode": "human_corrected_ai_draft" if ai_draft_changed else "human_accepted_ai_draft",
        "trace": {
            "prefab_path": source["prefab_path"],
            "render_candidate_id": source["auto_eval"].get("candidate_id") or "not_rendered",
            "render_paths": [frame["path"] for frame in source["frames"]] or ["not_rendered"],
            "auto_eval_status": source["auto_eval"]["status"],
        },
    })
    errors = sorted(_feedback_validator().iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ValueError(f"feedback schema error at {location}: {errors[0].message}")
    store = _read_json(root / "feedback_store.json")
    store["records"][candidate_id] = payload
    _write_json(root / "feedback_store.json", store)
    _write_jsonl(root / "feedback.jsonl", [store["records"][key] for key in sorted(store["records"])])
    return payload


def _technical_exclusion(
    source: dict[str, Any],
    *,
    feedback: dict[str, Any] | None,
    batch_id: str,
) -> dict[str, Any]:
    if feedback is not None:
        exclusion_reason = "human_not_visible_no_training_label"
        source_kind = "human_feedback"
    else:
        exclusion_reason = "no_independent_visual_evidence"
        source_kind = "technical_route"
    preview = source.get("webgl_preview") if isinstance(source.get("webgl_preview"), dict) else {}
    return {
        "schema_version": "prefab_training_exclusion.v1",
        "batch_id": batch_id,
        "candidate_id": str(source["candidate_id"]),
        "prefab_path": str(source["prefab_path"]),
        "source_kind": source_kind,
        "exclusion_reason": exclusion_reason,
        "review_route": str(source.get("review_route") or ""),
        "technical_status": str(source.get("technical_status") or ""),
        "visibility_status": str(source.get("visibility_status") or ""),
        "webgl_status": str(preview.get("status") or ""),
        "render_frame_count": len(source.get("frames") or []),
        "auto_eval_status": str((source.get("auto_eval") or {}).get("status") or "unknown"),
        "human_feedback": feedback,
        "excluded_from": [
            "style_conditioned_supervision",
            "quality_supervision",
            "preference_training",
            "positive_generation_supervision",
        ],
    }


def finalize_feedback(root: Path, allow_technical_exclusions: bool = False) -> dict[str, Path]:
    root = root.resolve()
    batch = _read_json(root / "review_batch.json")
    store = _read_json(root / "feedback_store.json")
    records = store.get("records") if isinstance(store.get("records"), dict) else {}
    sources = {str(row["candidate_id"]): row for row in batch["records"]}
    expected = set(sources)
    missing = sorted(expected - set(records))
    if missing and not allow_technical_exclusions:
        raise ValueError(f"human review is incomplete: {len(records)}/{len(expected)} saved; next missing candidate: {missing[0]}")

    technical_exclusions: list[dict[str, Any]] = []
    if missing:
        invalid_missing = [
            candidate_id
            for candidate_id in missing
            if sources[candidate_id].get("review_route") not in TECHNICAL_EXCLUSION_ROUTES
            or sources[candidate_id].get("frames")
            or (sources[candidate_id].get("webgl_preview") or {}).get("status") == "webgl_ready"
        ]
        if invalid_missing:
            raise ValueError(
                "technical exclusion is only allowed for no-frame, non-WebGL context routes; "
                f"first invalid candidate: {invalid_missing[0]}"
            )
        technical_exclusions.extend(
            _technical_exclusion(sources[candidate_id], feedback=None, batch_id=batch["batch_id"])
            for candidate_id in missing
        )

    validator = _feedback_validator()
    ordered = [records[str(row["candidate_id"])] for row in batch["records"] if str(row["candidate_id"]) in records]
    for record in ordered:
        errors = list(validator.iter_errors(record))
        if errors:
            raise ValueError(f"stored feedback is invalid for {record.get('candidate_id')}: {errors[0].message}")

    trainable = [record for record in ordered if record["decision"] != "not_visible"]
    technical_exclusions.extend(
        _technical_exclusion(sources[record["candidate_id"]], feedback=record, batch_id=batch["batch_id"])
        for record in ordered
        if record["decision"] == "not_visible"
    )
    if not trainable:
        raise ValueError("no trainable human quality labels remain after excluding not_visible decisions")

    score_names = ("core_readability", "layer_separation", "rhythm", "material", "composition")
    summary = {
        "schema_version": "prefab_human_review_summary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch["batch_id"],
        "batch_candidate_count": len(expected),
        "review_count": len(ordered),
        "trainable_human_label_count": len(trainable),
        "technical_exclusion_count": len(technical_exclusions),
        "completion_mode": "all_human" if not missing else "human_plus_technical_exclusions",
        "decision_counts": dict(Counter(row["decision"] for row in ordered)),
        "trainable_decision_counts": dict(Counter(row["decision"] for row in trainable)),
        "style_family_counts": dict(Counter(row["style_family"] for row in trainable)),
        "quality_score_average": round(sum(int(row["quality_score"]) for row in trainable) / len(trainable), 4),
        "score_averages": {
            key: round(sum(int(row["scores"][key]) for row in trainable) / len(trainable), 4)
            for key in score_names
        },
        "aesthetic_labels_are_human": True,
        "not_visible_is_not_training_data": True,
    }
    overlays = [
        {
            "schema_version": "prefab_human_label_overlay.v1",
            "batch_id": batch["batch_id"],
            "candidate_id": row["candidate_id"],
            "reviewed_at": row["reviewed_at"],
            "human_label": row,
            "trace": row["trace"],
            "training_eligibility": {
                "quality_supervision": True,
                "style_conditioned_supervision": row["decision"] in {"accept_reference", "partial"},
                "preference_training": False,
            },
        }
        for row in trainable
    ]
    overlay_path = _write_jsonl(root / "human_label_overlays.jsonl", overlays)
    exclusion_path = _write_jsonl(root / "technical_exclusions.jsonl", technical_exclusions)
    summary_path = _write_json(root / "feedback_summary.json", summary)
    return {
        "human_label_overlays": overlay_path,
        "technical_exclusions": exclusion_path,
        "feedback_summary": summary_path,
    }


def finalize_composition_feedback(root: Path) -> dict[str, Path]:
    """Finalize human labels for rendered compositions without relabeling their source Prefabs."""
    root = root.resolve()
    batch = _read_json(root / "review_batch.json")
    if batch.get("review_subject") != "prompt_composition":
        raise ValueError("composition finalization requires a prompt_composition review batch")
    store = _read_json(root / "feedback_store.json")
    records = store.get("records") if isinstance(store.get("records"), dict) else {}
    expected = [str(row["candidate_id"]) for row in batch["records"]]
    missing = [candidate_id for candidate_id in expected if candidate_id not in records]
    if missing:
        raise ValueError(f"composition human review is incomplete: {len(records)}/{len(expected)} saved; next missing candidate: {missing[0]}")

    composition_path = Path(str(batch["source_composition_manifest"]))
    if not composition_path.is_absolute():
        composition_path = _repo_root() / composition_path
    composition = _read_json(composition_path)
    composition_by_id = {str(row["candidate_id"]): row for row in composition["candidates"]}
    validator = _feedback_validator()
    ordered = [records[candidate_id] for candidate_id in expected]
    for record in ordered:
        errors = list(validator.iter_errors(record))
        if errors:
            raise ValueError(f"stored composition feedback is invalid for {record.get('candidate_id')}: {errors[0].message}")

    trainable = [record for record in ordered if record["decision"] != "not_visible"]
    exclusions = []
    for record in ordered:
        if record["decision"] != "not_visible":
            continue
        source = composition_by_id[record["candidate_id"]]
        exclusions.append({
            "schema_version": "prompt_composition_training_exclusion.v1",
            "batch_id": batch["batch_id"],
            "candidate_id": record["candidate_id"],
            "reason": "human_not_visible_no_training_label",
            "source_composition_manifest": _portable(composition_path),
            "prefab_path": source["source_prefab"]["prefab_path"],
            "render_frame_count": len(record["trace"]["render_paths"]),
            "human_feedback": record,
            "excluded_from": [
                "composition_quality_supervision",
                "composition_style_supervision",
                "material_state_supervision",
                "prompt_condition_supervision",
                "preference_training",
                "positive_generation_supervision",
            ],
        })

    overlays = []
    for record in trainable:
        source = composition_by_id[record["candidate_id"]]
        overlays.append({
            "schema_version": "prompt_composition_human_label_overlay.v1",
            "batch_id": batch["batch_id"],
            "candidate_id": record["candidate_id"],
            "reviewed_at": record["reviewed_at"],
            "source_composition_manifest": _portable(composition_path),
            "prompt_condition": composition["prompt_condition"],
            "source_prefab": source["source_prefab"],
            "material_trajectory": source["material_trajectory"],
            "human_label": record,
            "trace": record["trace"],
            "unscored_prompt_conditions": source["prompt_conditions_unscored"],
            "training_eligibility": {
                "composition_quality_supervision": True,
                "composition_style_supervision": record["style_family"] != "unknown",
                "material_state_supervision": True,
                "prompt_condition_supervision": False,
                "preference_training": False,
                "positive_generation_supervision": False,
            },
        })

    score_names = ("core_readability", "layer_separation", "rhythm", "material", "composition")
    summary = {
        "schema_version": "prompt_composition_human_review_summary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch["batch_id"],
        "source_composition_manifest": _portable(composition_path),
        "batch_candidate_count": len(expected),
        "review_count": len(ordered),
        "trainable_human_label_count": len(trainable),
        "technical_exclusion_count": len(exclusions),
        "decision_counts": dict(Counter(row["decision"] for row in ordered)),
        "trainable_decision_counts": dict(Counter(row["decision"] for row in trainable)),
        "quality_score_average": round(sum(int(row["quality_score"]) for row in trainable) / len(trainable), 4) if trainable else None,
        "score_averages": {
            key: round(sum(int(row["scores"][key]) for row in trainable) / len(trainable), 4) if trainable else None
            for key in score_names
        },
        "aesthetic_labels_are_human": True,
        "not_visible_is_not_training_data": True,
        "prompt_conditions_are_not_inferred": True,
        "preference_pairs_available": False,
        "status": "human_labels_ready" if trainable else "all_candidates_excluded",
    }
    overlay_path = _write_jsonl(root / "composition_human_label_overlays.jsonl", overlays)
    exclusion_path = _write_jsonl(root / "composition_technical_exclusions.jsonl", exclusions)
    summary_path = _write_json(root / "composition_feedback_summary.json", summary)
    return {
        "composition_human_label_overlays": overlay_path,
        "composition_technical_exclusions": exclusion_path,
        "composition_feedback_summary": summary_path,
    }


def migrate_feedback(source_root: Path, destination_root: Path) -> Path:
    """Move human selections to a rebuilt batch while regenerating its evidence trace."""
    source_root, destination_root = source_root.resolve(), destination_root.resolve()
    source_batch = _read_json(source_root / "review_batch.json")
    source_store = _read_json(source_root / "feedback_store.json")
    destination_batch = _read_json(destination_root / "review_batch.json")
    destination_store = _read_json(destination_root / "feedback_store.json")
    if destination_store.get("records"):
        raise ValueError("destination feedback store must be empty before migration")
    source_records = source_store.get("records") if isinstance(source_store.get("records"), dict) else {}
    destination_ids = {str(row["candidate_id"]) for row in destination_batch["records"]}
    migrated: list[str] = []
    preserved_records: dict[str, dict[str, Any]] = {}
    for candidate_id in sorted(source_records):
        source = source_records[candidate_id]
        if candidate_id not in destination_ids:
            raise ValueError(f"source feedback candidate is absent from destination batch: {candidate_id}")
        payload = {
            key: source[key]
            for key in ("candidate_id", "decision", "style_family", "style_keywords", "quality_score", "scores", "layer_roles", "reusable_layers", "issues", "summary")
        }
        payload["notes"] = str(source.get("notes") or "")
        payload["ai_draft_changed"] = source.get("confirmation_mode") == "human_corrected_ai_draft"
        saved = save_feedback(destination_root, payload)
        saved["reviewed_at"] = source["reviewed_at"]
        saved["reviewer"] = source["reviewer"]
        preserved_records[candidate_id] = saved
        migrated.append(candidate_id)
    destination_store = _read_json(destination_root / "feedback_store.json")
    destination_store["records"].update(preserved_records)
    _write_json(destination_root / "feedback_store.json", destination_store)
    _write_jsonl(destination_root / "feedback.jsonl", [destination_store["records"][key] for key in sorted(destination_store["records"])])
    return _write_json(destination_root / "feedback_migration.json", {
        "schema_version": "prefab_human_feedback_migration.v1",
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "source_batch_id": source_batch["batch_id"],
        "destination_batch_id": destination_batch["batch_id"],
        "migrated_candidate_ids": migrated,
        "evidence_trace": "regenerated_from_destination_batch",
    })


_HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全部 Prefab 人工评价</title><style>
:root{--bg:#10151b;--panel:#171e26;--panel2:#1d2731;--line:#2b3946;--text:#e9eef4;--muted:#9aa8b6;--cyan:#49c7d6;--yellow:#f3c969;--green:#7cc58e;--coral:#ee8d72}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 "Segoe UI","Microsoft YaHei",sans-serif}button,input,select{font:inherit}header{height:54px;display:flex;align-items:center;gap:12px;padding:0 16px;border-bottom:1px solid var(--line);background:#121920}h1{margin:0;font-size:16px}.progress{margin-left:auto;color:var(--muted)}main{height:calc(100vh - 54px);display:grid;grid-template-columns:280px minmax(420px,1fr) 380px;gap:10px;padding:10px}.panel{min-height:0;border:1px solid var(--line);background:var(--panel)}.list{overflow-y:auto;overflow-x:hidden;padding:8px}.item{width:100%;display:grid;grid-template-columns:32px minmax(0,1fr);gap:7px;padding:8px;border:1px solid transparent;background:transparent;color:var(--text);text-align:left;cursor:pointer}.item>span{min-width:0;overflow-wrap:anywhere}.item.active{border-color:var(--cyan);background:var(--panel2)}.item.done .idx{color:var(--green)}.idx{color:var(--yellow);font-family:Consolas}.item small{display:block;color:var(--muted)}.stage{display:grid;grid-template-rows:minmax(0,1fr) 100px auto}.hero{display:grid;place-items:center;background:#080c10;overflow:hidden}.hero img{max-width:100%;max-height:100%;object-fit:contain}.empty{color:var(--muted);text-align:center;max-width:320px}.frames{display:flex;gap:6px;overflow-x:auto;padding:7px;border-top:1px solid var(--line)}.frame{flex:0 0 86px;border:1px solid var(--line);padding:3px;background:#111820;color:var(--muted);cursor:pointer}.frame.active{border-color:var(--yellow)}.frame img{width:78px;height:62px;object-fit:contain;background:#070a0d}.transport{display:grid;grid-template-columns:auto auto auto minmax(100px,1fr) auto;gap:7px;align-items:center;padding:8px;border-top:1px solid var(--line)}.icon{width:34px;height:32px;border:1px solid var(--line);background:var(--panel2);color:var(--text);cursor:pointer}.details{overflow:auto;padding:12px}.meta{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px}.meta div{padding:7px;background:var(--panel2);color:var(--muted);font-size:12px}.meta b{display:block;color:var(--text)}label{display:block;margin:10px 0 4px;color:var(--muted);font-size:12px}select{width:100%;padding:8px;border:1px solid var(--line);background:#10161c;color:var(--text)}.scores{display:grid;gap:7px}.score{display:grid;grid-template-columns:95px 1fr 22px;gap:7px;align-items:center}.score label{margin:0}.roles{display:grid;grid-template-columns:1fr 1fr;gap:7px}.checks{display:flex;flex-wrap:wrap;gap:5px}.checks label{margin:0;padding:4px 6px;border:1px solid var(--line);background:#111820;color:var(--text);font-size:12px}.actions{display:flex;gap:8px;margin-top:14px;position:sticky;bottom:-12px;padding:10px 0 4px;background:var(--panel)}.save{flex:1;border:1px solid var(--green);background:#20372a;color:#d8f5df;padding:9px;cursor:pointer}.next{border:1px solid var(--cyan);background:var(--panel2);color:var(--text);padding:9px;cursor:pointer}.status{color:var(--muted);font-size:12px}.error{color:var(--coral)}@media(max-width:900px){main{height:auto;grid-template-columns:1fr}.list{max-height:245px}.stage{height:610px}.details{overflow:visible}.roles{grid-template-columns:1fr}.actions{bottom:0}}
</style></head><body><header><h1>全部 Prefab 人工评价</h1><span id="batch"></span><span id="progress" class="progress"></span></header><main><aside class="panel list" id="list"></aside><section class="panel stage"><div class="hero" id="hero"></div><div class="frames" id="frames"></div><div class="transport"><button class="icon" id="prev">←</button><button class="icon" id="play">▶</button><button class="icon" id="nextFrame">→</button><input id="timeline" type="range" min="0" max="0" value="0"><span id="time"></span></div></section><aside class="panel details"><div id="meta" class="meta"></div><div id="form"></div></aside></main><script>
let batch=null,feedback={},index=0,frame=0,timer=null;const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),current=()=>batch.records[index],asset=p=>'/asset/'+p.split('/').map(encodeURIComponent).join('/');const labels={decision:{accept_reference:'可作为参考',partial:'部分可复用',reject:'不建议参考',not_visible:'无法判断'},style:{realistic:'写实',stylized:'风格化',cartoon:'卡通',anime:'动漫',fantasy_painterly:'幻想绘制',ui_graphic:'UI图形',mixed:'混合',unknown:'暂不判断'}};function opts(id,values,value){return `<select id="${id}">${values.map(v=>`<option value="${v}" ${v===value?'selected':''}>${labels[id]?.[v]||v}</option>`).join('')}</select>`}function checks(id,values,saved){let set=new Set(saved||[]);return `<div class="checks" id="${id}">${values.map(v=>`<label><input type="checkbox" value="${v}" ${set.has(v)?'checked':''}>${v}</label>`).join('')}</div>`}function checked(id){return [...document.querySelectorAll(`#${id} input:checked`)].map(x=>x.value)}
function renderList(){$('list').innerHTML=batch.records.map((r,i)=>`<button class="item ${i===index?'active':''} ${feedback[r.candidate_id]?'done':''}" data-i="${i}"><span class="idx">${String(i+1).padStart(3,'0')}</span><span>${esc(r.candidate_id)}<small>${esc(r.source_category.join('/'))} · ${esc(r.technical_status_cn)} · ${esc(r.review_route)}</small></span></button>`).join('');document.querySelectorAll('.item').forEach(x=>x.onclick=()=>selectCandidate(Number(x.dataset.i)))}
function renderStage(){let r=current(),f=r.frames[frame];if(!f){$('hero').innerHTML=`<div class="empty">当前没有独立预览。请选择右侧的技术状态与总体结论：这条 Prefab 需要 UI、角色挂点、脚本或完整运行上下文后才能判断视觉质量。</div>`;$('frames').innerHTML='';$('timeline').max=0;$('timeline').value=0;$('time').textContent='无独立帧';return}$('hero').innerHTML=`<img src="${asset(f.path)}" alt="Prefab 帧">`;$('frames').innerHTML=r.frames.map((x,i)=>`<button class="frame ${i===frame?'active':''}" data-i="${i}"><img src="${asset(x.path)}"><span>${Number(x.time_seconds).toFixed(2)}s</span></button>`).join('');document.querySelectorAll('.frame').forEach(x=>x.onclick=()=>selectFrame(Number(x.dataset.i)));$('timeline').max=r.frames.length-1;$('timeline').value=frame;$('time').textContent=`${frame+1}/${r.frames.length}`}
function score(id,label,value){return `<div class="score"><label>${label}</label><input id="s-${id}" type="range" min="0" max="5" value="${value}"><output id="o-${id}">${value}</output></div>`}function renderForm(){let r=current(),draft=drafts[r.candidate_id]?.suggested_feedback||{},s=feedback[r.candidate_id]||draft,scores=s.scores||{};$('meta').innerHTML=`<div><b>技术状态</b>${esc(r.technical_status_cn)}</div><div><b>预览状态</b>${esc(r.review_route)}</div><div><b>粒子 / 材质</b>${r.particle_system_count} / ${r.material_count}</div><div><b>类别</b>${esc(r.source_category.join('/'))}</div>`;$('form').innerHTML=`<div class="status" id="saveStatus">${s.reviewed_at?'已保存':drafts[r.candidate_id]?'AI 建议，未保存':'未评价'}</div><label>总体结论</label>${opts('decision',['accept_reference','partial','reject','not_visible'],s.decision||'partial')}<label>风格</label>${opts('style',['realistic','stylized','cartoon','anime','fantasy_painterly','ui_graphic','mixed','unknown'],s.style_family||'unknown')}<label>风格特点（可多选）</label>${checks('keywords',['高饱和','低饱和','明亮','暗色','能量感','粒子感','UI感','写实材质','卡通轮廓','柔和','尖锐'],s.style_keywords)}<label>总体质量 1-5</label><input id="quality" type="range" min="1" max="5" value="${s.quality_score||3}"><output id="qualityOut">${s.quality_score||3}</output><div class="scores">${score('core','主体可读',scores.core_readability??3)}${score('layer','层级职责',scores.layer_separation??3)}${score('rhythm','节奏',scores.rhythm??3)}${score('material','材质',scores.material??3)}${score('composition','构图',scores.composition??3)}</div><div class="roles"><div><label>Core</label>${opts('core',['清楚','一般','不清楚','没有'],s.layer_roles?.core||'一般')}</div><div><label>Support</label>${opts('support',['有效','一般','干扰','没有'],s.layer_roles?.support||'一般')}</div><div><label>Hit</label>${opts('hit',['有效','一般','干扰','没有'],s.layer_roles?.hit||'一般')}</div><div><label>Residual</label>${opts('residual',['有效','一般','拖沓','没有'],s.layer_roles?.residual||'一般')}</div></div><label>可复用部分（可多选）</label>${checks('reusable',['主体','支撑','命中','残留','材质','粒子参数','无'],s.reusable_layers)}<label>主要问题（可多选）</label>${checks('issues',['主体不清楚','层级混乱','节奏拖沓','节奏突兀','材质普通','构图偏小','构图偏大','颜色不协调','缺少命中','缺少残留','无明显问题'],s.issues)}<label>人工备注</label><textarea id="notes" maxlength="2000">${esc(s.notes||'')}</textarea><label>总结</label>${opts('summary',['可作为参考','部分可复用','不建议参考','无法判断'],s.summary||'部分可复用')}<div class="actions"><button class="save" id="save">保存本条</button><button class="next" id="nextCandidate">下一条</button></div>`;['core','layer','rhythm','material','composition'].forEach(n=>$(`s-${n}`).oninput=e=>$(`o-${n}`).value=e.target.value);$('quality').oninput=e=>$('qualityOut').value=e.target.value;$('save').onclick=save;$('nextCandidate').onclick=()=>{let next=nextUnreviewed();selectCandidate(next>=0?next:Math.min(batch.records.length-1,index+1))}}
function render(){renderList();renderStage();renderForm();$('batch').textContent=batch.batch_id;$('progress').textContent=`${Object.keys(feedback).length}/${batch.records.length} 已评价`}function selectCandidate(i){stop();index=i;frame=Math.min(1,Math.max(0,batch.records[i].frames.length-1));render()}function nextUnreviewed(){for(let i=index+1;i<batch.records.length;i++)if(!feedback[batch.records[i].candidate_id])return i;return -1}function selectFrame(i){frame=i;renderStage()}function move(d){if(!current().frames.length)return;selectFrame(Math.max(0,Math.min(current().frames.length-1,frame+d)))}function stop(){if(timer){clearInterval(timer);timer=null;$('play').textContent='▶'}}function toggle(){if(timer){stop();return}if(!current().frames.length)return;$('play').textContent='Ⅱ';timer=setInterval(()=>{if(frame>=current().frames.length-1){stop();return}move(1)},350)}async function save(){let p={candidate_id:current().candidate_id,decision:$('decision').value,style_family:$('style').value,style_keywords:checked('keywords'),quality_score:Number($('quality').value),scores:{core_readability:Number($('s-core').value),layer_separation:Number($('s-layer').value),rhythm:Number($('s-rhythm').value),material:Number($('s-material').value),composition:Number($('s-composition').value)},layer_roles:{core:$('core').value,support:$('support').value,hit:$('hit').value,residual:$('residual').value},reusable_layers:checked('reusable'),issues:checked('issues'),notes:$('notes').value,summary:$('summary').value};let d=drafts[p.candidate_id]?.suggested_feedback;let x={decision:p.decision,style_family:p.style_family,style_keywords:p.style_keywords,quality_score:p.quality_score,scores:p.scores,layer_roles:p.layer_roles,reusable_layers:p.reusable_layers,issues:p.issues,summary:p.summary};p.ai_draft_changed=!d||JSON.stringify(x)!==JSON.stringify(d);let q=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}),b=await q.json();if(!q.ok){$('saveStatus').textContent=b.error||'保存失败';$('saveStatus').className='status error';return}feedback[p.candidate_id]=b.record;render()}$('prev').onclick=()=>move(-1);$('nextFrame').onclick=()=>move(1);$('play').onclick=toggle;$('timeline').oninput=e=>selectFrame(Number(e.target.value));Promise.all([fetch('/api/batch').then(r=>r.json()),fetch('/api/feedback').then(r=>r.json()),fetch('/api/drafts').then(r=>r.json())]).then(([b,f,d])=>{batch=b;feedback=f.records||{};drafts=d.records||{};let first=batch.records.findIndex(r=>!feedback[r.candidate_id]);if(first>=0)index=first;render()});
</script></body></html>'''

_AI_DRAFT_HTML = (
    _HTML
    .replace(
        "let batch=null,feedback={},index=0,frame=0,timer=null;",
        "let batch=null,feedback={},drafts={},index=0,frame=0,timer=null;",
    )
    .replace(
        "let r=current(),s=feedback[r.candidate_id]||{},scores=s.scores||{};",
        "let r=current(),draft=drafts[r.candidate_id]?.suggested_feedback||{},s=feedback[r.candidate_id]||draft,scores=s.scores||{};",
    )
    .replace(
        "${s.reviewed_at?'已保存':'未评价'}",
        "${s.reviewed_at?'已保存':drafts[r.candidate_id]?'AI 建议，未保存':'未评价'}",
    )
    .replace(
        "async function save(){let p=",
        "function aiChanged(p){let d=drafts[p.candidate_id]?.suggested_feedback;if(!d)return true;let x={decision:p.decision,style_family:p.style_family,style_keywords:p.style_keywords,quality_score:p.quality_score,scores:p.scores,layer_roles:p.layer_roles,reusable_layers:p.reusable_layers,issues:p.issues,summary:p.summary};return JSON.stringify(x)!==JSON.stringify(d)}async function save(){let p=",
    )
    .replace(
        "};let q=await fetch('/api/feedback'",
        "};p.ai_draft_changed=aiChanged(p);let q=await fetch('/api/feedback'",
    )
    .replace(
        "Promise.all([fetch('/api/batch').then(r=>r.json()),fetch('/api/feedback').then(r=>r.json())]).then(([b,f])=>{batch=b;feedback=f.records||{};render()});",
        "Promise.all([fetch('/api/batch').then(r=>r.json()),fetch('/api/feedback').then(r=>r.json()),fetch('/api/drafts').then(r=>r.json())]).then(([b,f,d])=>{batch=b;feedback=f.records||{};drafts=d.records||{};render()});",
    )
)

_WEBGL_REVIEW_HTML = (
    _AI_DRAFT_HTML
    .replace(
        ".hero{display:grid;place-items:center;background:#080c10;overflow:hidden}",
        ".hero{position:relative;display:grid;place-items:center;background:#080c10;overflow:hidden}.webgl-frame{width:100%;height:100%;border:0;background:#080c10}.webgl-label{position:absolute;top:9px;left:9px;z-index:2;padding:3px 7px;border:1px solid #49c7d6;background:#10151be6;color:#d8f8fb;font-size:12px;pointer-events:none}.playable-filter{display:inline-flex;align-items:center;gap:6px;margin:0;color:var(--text);font-size:12px;white-space:nowrap}.playable-filter input{width:15px;height:15px;accent-color:var(--cyan)}textarea{width:100%;min-height:76px;resize:vertical;padding:8px;border:1px solid var(--line);background:#10161c;color:var(--text);line-height:1.45}",
    )
    .replace(
        "function renderStage(){let r=current(),f=r.frames[frame];if(!f){$('hero').innerHTML=`<div class=\"empty\">当前没有独立预览。请选择右侧的技术状态与总体结论：这条 Prefab 需要 UI、角色挂点、脚本或完整运行上下文后才能判断视觉质量。</div>`;$('frames').innerHTML='';$('timeline').max=0;$('timeline').value=0;$('time').textContent='无独立帧';return}$('hero').innerHTML=`<img src=\"${asset(f.path)}\" alt=\"Prefab 帧\">`;$('frames').innerHTML=r.frames.map((x,i)=>`<button class=\"frame ${i===frame?'active':''}\" data-i=\"${i}\"><img src=\"${asset(x.path)}\"><span>${Number(x.time_seconds).toFixed(2)}s</span></button>`).join('');document.querySelectorAll('.frame').forEach(x=>x.onclick=()=>selectFrame(Number(x.dataset.i)));$('timeline').max=r.frames.length-1;$('timeline').value=frame;$('time').textContent=`${frame+1}/${r.frames.length}`}",
        "function readyWebgl(r){let p=r.webgl_preview;return p&&p.status==='webgl_ready'&&p.player_url&&p.catalog_id?p:null}let webglFrame=null,webglFrameUrl='',webglExpectedId='',webglAcknowledgedId='',webglFallbackTimer=null;function webglPlayerKey(p){let u=new URL(p.player_url,window.location.href);u.searchParams.set('embed','1');u.searchParams.set('parentOrigin',window.location.origin);return u.toString()}function webglPlayerSrc(p){let u=new URL(webglPlayerKey(p));u.searchParams.set('catalogId',p.catalog_id);return u.toString()}function selectWebgl(p){webglExpectedId=p.catalog_id;if(!webglFrame?.contentWindow)return;webglFrame.contentWindow.postMessage({type:'vfx-web-select',catalogId:p.catalog_id},new URL(p.player_url).origin);clearTimeout(webglFallbackTimer);webglFallbackTimer=setTimeout(()=>{if(webglAcknowledgedId!==webglExpectedId&&webglFrame&&webglFrameUrl===webglPlayerSrc(p)){webglFrame.src=webglPlayerSrc(p)}},1800)}window.addEventListener('message',e=>{let p=readyWebgl(current());if(!p||e.origin!==new URL(p.player_url).origin||e.data?.type!=='vfx-web-selected')return;webglAcknowledgedId=e.data.catalogId;if(webglAcknowledgedId===webglExpectedId)clearTimeout(webglFallbackTimer)});function syncWebgl(p){let hero=$('hero'),src=webglPlayerSrc(p),same=webglFrame&&webglFrameUrl===src&&webglFrame.isConnected;if(!same){hero.innerHTML='';webglFrame=document.createElement('iframe');webglFrame.className='webgl-frame';webglFrame.title='真实 Unity WebGL 特效预览';webglFrame.src=src;webglFrame.onload=()=>selectWebgl(p);hero.appendChild(webglFrame);let label=document.createElement('span');label.className='webgl-label';label.textContent='真实 Unity WebGL';hero.appendChild(label);webglFrameUrl=src;webglAcknowledgedId=''}selectWebgl(p)}function renderFrames(r){$('frames').innerHTML=r.frames.map((x,i)=>`<button class=\"frame ${i===frame?'active':''}\" data-i=\"${i}\"><img src=\"${asset(x.path)}\"><span>${Number(x.time_seconds).toFixed(2)}s</span></button>`).join('');document.querySelectorAll('.frame').forEach(x=>x.onclick=()=>selectFrame(Number(x.dataset.i)));$('timeline').max=Math.max(0,r.frames.length-1);$('timeline').value=Math.min(frame,Math.max(0,r.frames.length-1));$('time').textContent=r.frames.length?`${frame+1}/${r.frames.length}`:'真实 WebGL'}function renderStage(){let r=current(),f=r.frames[frame],p=readyWebgl(r);if(p){syncWebgl(p);renderFrames(r);return}webglFrame=null;if(!f){$('hero').innerHTML=`<div class=\"empty\">${esc(r.webgl_preview?.availability_reason_cn||'当前没有独立预览。')}<br>请结合技术状态与总体结论判断，不能把没有上下文的结果当成坏特效。</div>`;$('frames').innerHTML='';$('timeline').max=0;$('timeline').value=0;$('time').textContent='无独立帧';return}$('hero').innerHTML=`<img src=\"${asset(f.path)}\" alt=\"Prefab 帧\">`;renderFrames(r)}",
    )
    .replace(
        "<div><b>类别</b>${esc(r.source_category.join('/'))}</div>`",
        "<div><b>类别</b>${esc(r.source_category.join('/'))}</div><div><b>真实动态预览</b>${esc(r.webgl_preview?.status_cn||'未配置')}</div>`",
    )
    .replace(
        "<div><b>类别</b>${esc(r.source_category.join('/'))}</div><div><b>真实动态预览</b>${esc(r.webgl_preview?.status_cn||'未配置')}</div>`",
        "<div><b>类别</b>${esc(r.source_category.join('/'))}</div><div><b>评价对象</b>${esc(r.review_subject_cn||'源 Prefab')}</div><div><b>来源提示</b>${esc(r.source_label_note||'请只评价当前源 Prefab')}</div><div><b>真实动态预览</b>${esc(r.webgl_preview?.status_cn||'未配置')}</div>`",
    )
    .replace(
        "</h1><span id=\"batch\"></span>",
        "</h1><label class=\"playable-filter\"><input id=\"playableOnly\" type=\"checkbox\">仅看可播放</label><span id=\"batch\"></span>",
    )
    .replace(
        "let batch=null,feedback={},drafts={},index=0,frame=0,timer=null;",
        "let batch=null,feedback={},drafts={},index=0,frame=0,timer=null,playableOnly=false;",
    )
    .replace(
        "function renderList(){$('list').innerHTML=batch.records.map((r,i)=>`<button class=\"item ${i===index?'active':''} ${feedback[r.candidate_id]?'done':''}\" data-i=\"${i}\"><span class=\"idx\">${String(i+1).padStart(3,'0')}</span><span>${esc(r.candidate_id)}<small>${esc(r.source_category.join('/'))} · ${esc(r.technical_status_cn)} · ${esc(r.review_route)}</small></span></button>`).join('');document.querySelectorAll('.item').forEach(x=>x.onclick=()=>selectCandidate(Number(x.dataset.i)))}",
        "function isPlayable(r){return r.webgl_preview?.status==='webgl_ready'}function renderList(){let list=$('list'),rows=batch.records.map((r,i)=>({r,i})).filter(x=>!playableOnly||isPlayable(x.r));list.innerHTML='';if(!rows.length){let empty=document.createElement('div');empty.className='empty';empty.textContent='没有可独立播放的 Prefab';list.appendChild(empty);return}rows.forEach(x=>{let r=x.r,i=x.i,button=document.createElement('button'),idx=document.createElement('span'),copy=document.createElement('span'),meta=document.createElement('small');button.className='item '+(i===index?'active ':'')+(feedback[r.candidate_id]?'done':'');button.dataset.i=String(i);idx.className='idx';idx.textContent=String(i+1).padStart(3,'0');copy.textContent=r.candidate_id;meta.textContent=r.source_category.join('/')+' · '+r.technical_status_cn+' · '+r.review_route;copy.appendChild(meta);button.append(idx,copy);button.onclick=()=>selectCandidate(i);list.appendChild(button)})}",
    )
    .replace(
        "$('timeline').oninput=e=>selectFrame(Number(e.target.value));Promise.all",
        "$('timeline').oninput=e=>selectFrame(Number(e.target.value));$('playableOnly').onchange=e=>{playableOnly=e.target.checked;if(batch&&playableOnly&&!isPlayable(current())){index=batch.records.findIndex(isPlayable);frame=0}render()};Promise.all",
    )
    .replace(
        "let first=batch.records.findIndex(r=>!feedback[r.candidate_id]);if(first>=0)index=first;render()});",
        "let first=batch.records.findIndex(r=>!feedback[r.candidate_id]);if(first>=0)index=first;if(batch.review_subject==='prompt_composition'){document.querySelector('h1').textContent='组合候选人工评价';document.querySelector('.playable-filter').style.display='none'}render()});",
    )
    .replace(
        "issues:checked('issues'),summary:$('summary').value}",
        "issues:checked('issues'),notes:$('notes').value,summary:$('summary').value}",
    )
)


class ReviewHandler(BaseHTTPRequestHandler):
    root = Path("."); repo = _repo_root()
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/": self._send(200,"text/html; charset=utf-8",_WEBGL_REVIEW_HTML.encode("utf-8"))
        elif path == "/api/batch": self._json(_read_json(self.root/"review_batch.json"))
        elif path == "/api/feedback": self._json(_read_json(self.root/"feedback_store.json"))
        elif path == "/api/drafts": self._json({"records": _load_drafts(self.root)})
        elif path.startswith("/asset/"):
            asset=(self.repo/Path(unquote(path[7:]))).resolve()
            if asset.is_file() and asset.is_relative_to(self.repo.resolve()): self._send(200,"image/png" if asset.suffix.lower()==".png" else "image/jpeg",asset.read_bytes())
            else:self._json({"error":"asset not found"},404)
        else:self._json({"error":"not found"},404)
    def do_POST(self) -> None:
        if urlparse(self.path).path!="/api/feedback":self._json({"error":"not found"},404);return
        try:self._json({"ok":True,"record":save_feedback(self.root,json.loads(self.rfile.read(int(self.headers.get("Content-Length","0")))))})
        except (ValueError,json.JSONDecodeError) as e:self._json({"error":str(e)},400)
    def _send(self,code:int,content_type:str,body:bytes)->None:self.send_response(code);self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
    def _json(self,value:dict[str,Any],code:int=200)->None:self._send(code,"application/json; charset=utf-8",json.dumps(value,ensure_ascii=False).encode("utf-8"))
    def log_message(self,*_:object)->None:pass


def serve(root: Path, port: int) -> None:
    ReviewHandler.root=root.resolve(); ThreadingHTTPServer(("127.0.0.1",port),ReviewHandler).serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest="command",required=True);build=commands.add_parser("build");build.add_argument("--dataset-root",type=Path,required=True);build.add_argument("--run-root",type=Path,required=True);build.add_argument("--output-root",type=Path,required=True);build.add_argument("--batch-id",required=True);build.add_argument("--count",type=int);build.add_argument("--webgl-catalog",type=Path);composition=commands.add_parser("build-composition");composition.add_argument("--composition-root",type=Path,required=True);composition.add_argument("--output-root",type=Path,required=True);composition.add_argument("--batch-id",required=True);server=commands.add_parser("serve");server.add_argument("--root",type=Path,required=True);server.add_argument("--port",type=int,default=8774);finalize=commands.add_parser("finalize");finalize.add_argument("--root",type=Path,required=True);finalize.add_argument("--allow-technical-exclusions",action="store_true");composition_finalize=commands.add_parser("finalize-composition");composition_finalize.add_argument("--root",type=Path,required=True);drafts=commands.add_parser("drafts");drafts.add_argument("--root",type=Path,required=True);migration=commands.add_parser("migrate-feedback");migration.add_argument("--source-root",type=Path,required=True);migration.add_argument("--destination-root",type=Path,required=True);args=parser.parse_args(argv)
    if args.command=="serve":serve(args.root,args.port);return 0
    try:
        if args.command=="build":paths=build_review_batch(args.dataset_root,args.run_root,args.output_root,args.batch_id,args.count,args.webgl_catalog)
        elif args.command=="build-composition":paths=build_composition_review_batch(args.composition_root,args.output_root,args.batch_id)
        elif args.command=="finalize-composition":paths=finalize_composition_feedback(args.root)
        elif args.command=="drafts":paths={"ai_drafts":generate_ai_drafts(args.root)}
        elif args.command=="migrate-feedback":paths={"feedback_migration":migrate_feedback(args.source_root,args.destination_root)}
        else:paths=finalize_feedback(args.root,args.allow_technical_exclusions)
    except (FileExistsError,FileNotFoundError,ValueError,OSError,json.JSONDecodeError) as e:print(json.dumps({"success":False,"error":str(e)},ensure_ascii=False));return 2
    print(json.dumps({"success":True,**{k:v.as_posix() for k,v in paths.items()}},ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
