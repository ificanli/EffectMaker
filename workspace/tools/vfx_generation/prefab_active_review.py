"""Build and serve sparse Chinese correction queues for active Prefab learning."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import unquote, urlparse

from jsonschema import Draft202012Validator, FormatChecker

from workspace.tools.vfx_generation.capture_visual_integrity import analyze_capture_manifest


BATCH_SCHEMA = "vfx_prefab_active_review_batch.v1"
FEEDBACK_SCHEMA = "vfx_prefab_active_review_feedback.v1"
CAPTURE_PIPELINE = "play_mode_runtime_isolated_multiview.v2"
_FEEDBACK_LOCK = threading.RLock()
_SEMANTIC_OPTIONS_LOCK = threading.RLock()
JUDGE_DOMAIN_CONFIDENCE_MULTIPLIER = 0.5
ALLOWED_ACTIONS = (
    "AI判断正确",
    "应该更好",
    "应该更差",
    "特效类型错误",
    "风格判断错误",
    "主体不清楚",
    "层次有问题",
    "节奏有问题",
    "材质有问题",
    "无法播放",
    "无法判断",
)
SEMANTIC_SCHEMA_VERSION = "effect_element_and_type.v2"
SEMANTIC_ACTIONS = ("AI判断正确", "特效元素错误", "特效类型错误", "无法播放", "无法判断")
ELEMENT_OPTIONS = (
    ("none", "无明确元素"),
    ("fire", "火焰"),
    ("ice", "冰霜"),
    ("lightning", "雷电"),
    ("water", "水"),
    ("wind", "风"),
    ("earth", "土/岩石"),
    ("nature", "自然/植物"),
    ("light", "光"),
    ("dark", "暗影"),
    ("poison", "毒"),
    ("blood", "血液"),
    ("smoke", "烟雾/尘土"),
    ("energy", "能量"),
)
EFFECT_TYPE_OPTIONS = (
    ("slash", "刀光/挥砍"),
    ("impact", "命中/爆点"),
    ("explosion", "爆炸"),
    ("magic_circle", "法阵"),
    ("laser", "激光/光束"),
    ("projectile", "飞行物/弹道"),
    ("muzzle", "枪口/施法起手"),
    ("shield", "护盾/防御"),
    ("portal", "传送门"),
    ("aura", "光环/附体"),
    ("trail", "拖尾/轨迹"),
    ("area", "范围提示/预警"),
    ("environment", "环境/天气"),
    ("ui", "UI表现"),
    ("unclassified", "其他"),
)
ELEMENT_OPTION_LABELS = dict(ELEMENT_OPTIONS)
EFFECT_TYPE_OPTION_LABELS = dict(EFFECT_TYPE_OPTIONS)
EFFECT_TYPE_ALIASES = {
    "hit": "impact",
    "命中/受击": "impact",
    "爆点/命中": "impact",
}
EXCLUSION_ACTIONS = {"无法播放", "无法判断"}
ACTION_ISSUES = {
    "特效元素错误": "特效元素错误",
    "特效类型错误": "特效类型错误",
    "风格判断错误": "风格判断错误",
    "主体不清楚": "主体不清楚",
    "层次有问题": "层次有问题",
    "节奏有问题": "节奏有问题",
    "材质有问题": "材质有问题",
}
ACTION_TASKS = {
    "应该更好": ["quality_direction_supervision", "pseudo_label_calibration"],
    "应该更差": ["quality_direction_supervision", "pseudo_label_calibration"],
    "特效类型错误": ["effect_family_error_detection", "pseudo_label_calibration"],
    "风格判断错误": ["style_error_detection", "pseudo_label_calibration"],
    "主体不清楚": ["core_readability_issue_detection", "pseudo_label_calibration"],
    "层次有问题": ["layer_separation_issue_detection", "pseudo_label_calibration"],
    "节奏有问题": ["rhythm_issue_detection", "pseudo_label_calibration"],
    "材质有问题": ["material_issue_detection", "pseudo_label_calibration"],
}
REASON_CN = {
    "uncertainty": "AI不确定",
    "new_cluster": "新结构簇",
    "model_disagreement": "模型分歧",
    "promotion_top": "高质量候选审计",
    "predicted_low": "低质量候选审计",
    "random_audit": "随机审计",
    "combined_fill": "综合优先级",
}
TERM_CN = {
    "fire": "火焰", "flame": "火焰", "lightning": "雷电", "slash": "刀光", "shield": "护盾",
    "smoke": "烟雾", "water": "水系", "ice": "冰霜", "explosion": "爆炸", "magic_circle": "法阵",
    "projectile": "飞行物", "wind": "风", "earth": "土/岩石", "nature": "自然/植物", "light": "光",
    "dark": "暗影", "poison": "毒", "blood": "血液", "energy": "能量", "none": "无明确元素",
    "unclassified": "未判断", "blue": "蓝色", "cyan": "青色", "white": "白色",
    "gray": "灰色", "grey": "灰色", "red": "红色", "orange": "橙色", "yellow": "黄色", "green": "绿色", "purple": "紫色",
}


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    _atomic_write_text(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
    return path


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (_repo_root() / path).resolve()


def _validator(name: str) -> Draft202012Validator:
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas" / name)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate(validator: Draft202012Validator, value: dict[str, Any], label: str) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {errors[0].message}")


def _semantic_option_store(root: Path) -> dict[str, Any]:
    root = root.resolve()
    path = root / "custom_semantic_options.json"
    if path.is_file():
        store = _read_json(path)
    else:
        batch = _read_json(root / "review_batch.json")
        store = {
            "schema_version": "vfx_prefab_custom_semantic_options.v2",
            "batch_id": batch["batch_id"],
            "updated_at": _now(),
            "options": [],
        }
    if store.get("schema_version") == "vfx_prefab_custom_semantic_options.v1":
        store = {
            **store,
            "schema_version": "vfx_prefab_custom_semantic_options.v2",
            "options": [{**row, "dimension": "effect_type"} for row in store.get("options") or []],
        }
    _validate(_validator("prefab_active_review_semantic_options.schema.json"), store, "custom semantic options")
    return store


def _semantic_option_labels(root: Path, dimension: str) -> dict[str, str]:
    labels = dict(ELEMENT_OPTION_LABELS if dimension == "effect_element" else EFFECT_TYPE_OPTION_LABELS)
    labels.update({
        _canonical_effect_type(row["value"]) if dimension == "effect_type" else str(row["value"]): str(row["label"])
        for row in _semantic_option_store(root)["options"]
        if row["dimension"] == dimension
    })
    return labels


def _canonical_effect_type(value: Any) -> str:
    return EFFECT_TYPE_ALIASES.get(str(value), str(value))


def _normalize_feedback_effect_type(
    feedback: dict[str, Any],
    target: dict[str, Any],
    batch_id: str,
    effect_type_labels: Mapping[str, str],
) -> tuple[dict[str, Any], int]:
    """Canonicalize the old hit/impact aliases without discarding the raw feedback."""
    normalized = deepcopy(feedback)
    semantic = normalized.get("semantic_selection")
    if not isinstance(semantic, dict):
        normalized["batch_id"] = batch_id
        return normalized, 0
    original_ai = str(semantic.get("ai_effect_type") or "")
    original_selected = str(semantic.get("selected_effect_type") or "") if semantic.get("selected_effect_type") is not None else None
    canonical_ai = _canonical_effect_type(original_ai)
    canonical_selected = _canonical_effect_type(original_selected) if original_selected is not None else None
    alias_count = int(canonical_ai != original_ai) + int(canonical_selected is not None and canonical_selected != original_selected)
    semantic["ai_effect_type"] = canonical_ai
    semantic["selected_effect_type"] = canonical_selected
    semantic["selected_effect_type_cn"] = effect_type_labels.get(canonical_selected, semantic.get("selected_effect_type_cn")) if canonical_selected is not None else None

    actions = list(normalized.get("selected_actions") or [normalized.get("action")])
    actions = [str(action) for action in actions if action]
    alias_only_type_error = (
        original_selected is not None
        and canonical_selected == canonical_ai
        and original_selected != canonical_ai
        and "特效类型错误" in actions
    )
    if alias_only_type_error:
        actions = [action for action in actions if action != "特效类型错误"]
        if not actions:
            actions = ["AI判断正确"]
        alias_count += 1
    actions = list(dict.fromkeys(actions))
    normalized["action"] = actions[0]
    normalized["selected_actions"] = actions
    normalized["confirmation_mode"] = (
        "human_exclusion" if any(action in EXCLUSION_ACTIONS for action in actions)
        else "human_accepted_ai_draft" if actions == ["AI判断正确"]
        else "human_corrected_ai_draft"
    )
    correction = normalized.get("correction")
    if isinstance(correction, dict):
        correction["action"] = actions[0]
        delta = correction.setdefault("label_delta", {})
        delta["ai_effect_type"] = canonical_ai
        delta["selected_effect_type"] = canonical_selected
        delta["selected_effect_type_cn"] = semantic.get("selected_effect_type_cn")
        if alias_count:
            delta["effect_type_alias_normalization"] = {
                "canonical_value": "impact",
                "canonical_label": effect_type_labels.get("impact", "命中/爆点"),
                "original_ai_effect_type": original_ai,
                "original_selected_effect_type": original_selected,
                "source_aliases": {"hit": "impact", "爆点/命中": "命中/爆点", "命中/受击": "命中/爆点"},
            }
    result = normalized.get("result")
    if isinstance(result, dict):
        labels = result.get("labels")
        if isinstance(labels, dict):
            labels["effect_type"] = canonical_selected
            labels["target_effect_family"] = canonical_selected
            labels["decision"] = actions[0] if len(actions) == 1 else "；".join(actions)
            labels["decisions"] = actions
            labels["issues"] = [issue for issue in labels.get("issues") or [] if issue != "特效类型错误" or "特效类型错误" in actions]
        result["trainable"] = not any(action in EXCLUSION_ACTIONS for action in actions)
        result["disposition"] = "excluded" if not result["trainable"] else "human_gold"
    normalized["batch_id"] = batch_id
    return normalized, alias_count


def add_custom_semantic_option(root: Path, label: str, dimension: str = "effect_type") -> dict[str, Any]:
    if dimension not in {"effect_element", "effect_type"}:
        raise ValueError("新增标签必须指定特效元素或特效类型")
    if not isinstance(label, str):
        raise ValueError("新增标签必须是文字")
    normalized = " ".join(label.split())
    if not normalized:
        raise ValueError("请输入新的标签名称")
    if len(normalized) > 24:
        raise ValueError("标签名称不能超过24个字符")
    if any(ord(character) < 32 for character in normalized):
        raise ValueError("标签名称不能包含控制字符")
    built_in_options = ELEMENT_OPTIONS if dimension == "effect_element" else EFFECT_TYPE_OPTIONS
    for value, existing_label in built_in_options:
        if existing_label.casefold() == normalized.casefold():
            return {"created": False, "option": {"value": value, "label": existing_label, "dimension": dimension}, "store": _semantic_option_store(root)}
    with _SEMANTIC_OPTIONS_LOCK:
        store = _semantic_option_store(root)
        existing = next((row for row in store["options"] if row["dimension"] == dimension and str(row["label"]).casefold() == normalized.casefold()), None)
        if existing is not None:
            return {"created": False, "option": existing, "store": store}
        option = {
            "value": "custom_" + hashlib.sha256(f"{dimension}|{normalized.casefold()}".encode("utf-8")).hexdigest()[:16],
            "label": normalized,
            "dimension": dimension,
        }
        store["options"].append(option)
        store["options"].sort(key=lambda row: (str(row["dimension"]), str(row["label"]).casefold(), str(row["value"])))
        store["updated_at"] = _now()
        _validate(_validator("prefab_active_review_semantic_options.schema.json"), store, "custom semantic options")
        _write_json(root.resolve() / "custom_semantic_options.json", store)
    return {"created": True, "option": option, "store": store}


def _draft_labels(draft: dict[str, Any]) -> dict[str, Any]:
    labels = draft.get("labels")
    return deepcopy(labels) if isinstance(labels, dict) else deepcopy(draft)


def _ai_summary(draft: dict[str, Any]) -> str:
    labels = _draft_labels(draft)
    colors = [TERM_CN.get(str(value), str(value)) for value in labels.get("observed_color_tags") or []]
    quality = labels.get("quality_score")
    parts = [f"颜色：{'、'.join(colors) if colors else '未判断'}"]
    if quality is not None:
        parts.append(f"质量：{quality}")
    return "；".join(parts)


def _path_tokens(prefab_path: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", prefab_path)
    return set(re.findall(r"[a-z0-9]+", expanded.lower()))


def _ai_effect_elements(draft: dict[str, Any], prefab_path: str) -> list[str]:
    tags = [str(value) for value in _draft_labels(draft).get("observed_element_tags") or []]
    elements = [tag for tag in tags if tag in ELEMENT_OPTION_LABELS and tag != "none"]
    tokens = _path_tokens(prefab_path)
    path_terms = {
        "fire": {"fire", "flame"}, "ice": {"ice", "frost", "snow"}, "lightning": {"lightning", "thunder", "electric"},
        "water": {"water", "splash"}, "wind": {"wind", "tornado"}, "earth": {"earth", "rock", "stone"},
        "nature": {"nature", "leaf", "plant"}, "light": {"holy"}, "dark": {"dark", "shadow"},
        "poison": {"poison", "acid", "toxic"}, "blood": {"blood"}, "smoke": {"smoke", "dust", "fog"},
        "energy": {"energy", "ki"},
    }
    elements.extend(element for element, terms in path_terms.items() if tokens.intersection(terms))
    unique = [value for value, _ in ELEMENT_OPTIONS if value in set(elements)]
    return unique or ["none"]


def _ai_effect_type(draft: dict[str, Any], prefab_path: str) -> str:
    tags = [str(value) for value in _draft_labels(draft).get("observed_element_tags") or []]
    tagged = next((tag for tag in tags if _canonical_effect_type(tag) in EFFECT_TYPE_OPTION_LABELS and _canonical_effect_type(tag) != "unclassified"), None)
    if tagged:
        return _canonical_effect_type(tagged)
    tokens = _path_tokens(prefab_path)
    if tokens.intersection({"slash", "sword", "blade"}):
        return "slash"
    if "explosion" in tokens or "boom" in tokens:
        return "explosion"
    if tokens.intersection({"impact", "burst"}):
        return "impact"
    if "muzzle" in tokens:
        return "muzzle"
    if tokens.intersection({"laser", "beam"}):
        return "laser"
    if tokens.intersection({"projectile", "missile", "bullet"}):
        return "projectile"
    if "hit" in tokens:
        return "impact"
    if "shield" in tokens:
        return "shield"
    if "portal" in tokens:
        return "portal"
    if "circle" in tokens or "rune" in tokens:
        return "magic_circle"
    if tokens.intersection({"aura", "charge"}):
        return "aura"
    if tokens.intersection({"trail", "tracer"}):
        return "trail"
    if tokens.intersection({"warning", "telegraph", "aoe"}):
        return "area"
    if tokens.intersection({"weather", "storm", "fireflies"}):
        return "environment"
    if "ui" in tokens:
        return "ui"
    return "unclassified"


def _webgl_index(path: Path | None) -> tuple[str, dict[str, str]]:
    if path is None:
        return "", {}
    payload = _read_json(path.resolve())
    if payload.get("schemaVersion") != "vfx_web_review_catalog.v1":
        raise ValueError("unsupported WebGL review catalog")
    player_url = str(payload.get("playerUrl") or "")
    if not player_url.startswith(("http://", "https://")):
        raise ValueError("WebGL review catalog requires an http(s) playerUrl")
    entries = {
        str(row.get("sourcePrefabPath") or "").replace("\\", "/"): str(row.get("catalogId") or "")
        for row in payload.get("entries") or []
        if isinstance(row, dict) and row.get("sourcePrefabPath") and row.get("catalogId")
    }
    return player_url, entries


def _judge_index(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = _read_json(path.resolve())
    if payload.get("schema_version") != "vfx_aesthetic_judge_predictions.v1":
        raise ValueError("unsupported Aesthetic Judge predictions")
    available = list(payload.get("available_tasks") or [])
    blocked = payload.get("blocked_tasks") or {}
    result = {}
    for prediction in payload.get("predictions") or []:
        candidate_id = str(prediction.get("candidate_id") or "")
        if not candidate_id or candidate_id in result:
            raise ValueError("Aesthetic Judge predictions contain missing or repeated candidate IDs")
        pseudo = prediction.get("ai_pseudo_label") or {}
        raw_confidences = pseudo.get("task_confidences") or {}
        adjusted_confidences = {
            task: round(float(raw_confidences.get(task) or 0.0) * JUDGE_DOMAIN_CONFIDENCE_MULTIPLIER, 6)
            for task in available
            if task != "style_family"
        }
        scores = {task: prediction[task] for task in available if task in prediction and task != "style_family"}
        result[candidate_id] = {
            "status": "experimental_low_confidence",
            "model_version": payload.get("model_version"),
            "training_sample_count": 45,
            "domain_status": "capture_v2_partial_training_feature_compatibility",
            "domain_confidence_multiplier": JUDGE_DOMAIN_CONFIDENCE_MULTIPLIER,
            "scores": scores,
            "task_confidences": adjusted_confidences,
            "model_disagreement": pseudo.get("model_disagreement"),
            "style_family": {
                "status": "not_trained" if "style_family" in blocked else "available",
                "value": prediction.get("style_family"),
                "reason": (blocked.get("style_family") or {}).get("reasons", [None])[0] if isinstance(blocked, dict) else None,
            },
            "training": {
                "eligible_tasks": ["active_learning_priority"],
                "excluded_tasks": ["human_gold", "regression_evaluation", "model_promotion", "preference_training"],
                "weight": 0.0,
            },
        }
    return result


def _capture_frames(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    manifest = _read_json(manifest_path)
    if manifest.get("capture_pipeline_version") != CAPTURE_PIPELINE:
        raise ValueError(f"active review requires Capture v2: {manifest_path}")
    if manifest.get("image_sequence_training_eligible") is not True:
        raise ValueError(f"active review capture is not image-sequence eligible: {manifest_path}")
    integrity = analyze_capture_manifest(manifest_path, manifest)
    if integrity["material_render_error"]:
        raise ValueError(f"active review capture has Unity error-magenta material pixels: {manifest_path}")
    capture_root_value = manifest.get("capture_root")
    capture_root = Path(str(capture_root_value)).resolve() if capture_root_value else manifest_path.parent / "captures"
    frames = []
    visible_ratios = []
    for frame in manifest.get("frames") or []:
        if frame.get("valid") is not True:
            continue
        path = (capture_root / str(frame["path"])).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Capture v2 frame is missing: {path}")
        frames.append({"time_seconds": float(frame.get("requested_time_seconds") or 0.0), "path": _portable(path)})
        visible_ratios.append(float((frame.get("pixel_metrics") or {}).get("visible_area_ratio") or 0.0))
    if not frames:
        raise ValueError(f"active review capture has no valid dynamic frames: {manifest_path}")
    peak_frame_index = max(range(len(frames)), key=lambda index: visible_ratios[index])
    return manifest, frames, peak_frame_index


def build_review_batch(
    active_root: Path,
    output_root: Path,
    batch_id: str,
    webgl_catalog_path: Path | None = None,
    capture_manifest_overrides: Mapping[str, Path] | None = None,
    judge_predictions_path: Path | None = None,
    review_mode: str = "aesthetic_correction",
    carry_feedback_root: Path | None = None,
) -> dict[str, Path]:
    active_root, output_root = active_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"active review output already exists and is not empty: {output_root}")
    if review_mode not in {"aesthetic_correction", "semantic_function_only"}:
        raise ValueError(f"unsupported active review mode: {review_mode}")
    active = _read_json(active_root / "active_learning_batch.json")
    _validate(_validator("prefab_active_learning_batch.schema.json"), active, "active-learning batch")
    player_url, webgl = _webgl_index(webgl_catalog_path)
    judge_predictions = _judge_index(judge_predictions_path)
    records = []
    for item in active["items"]:
        prefab_path = str(item["prefab_path"]).replace("\\", "/")
        override = (capture_manifest_overrides or {}).get(prefab_path)
        manifest_path = _resolve(str(override)) if override else _resolve(str(item["capture_manifest_path"]))
        manifest, frames, peak_frame_index = _capture_frames(manifest_path)
        catalog_id = webgl.get(prefab_path)
        ai_draft = deepcopy(item["ai_draft"])
        if item["sample_id"] in judge_predictions:
            ai_draft["aesthetic_judge"] = judge_predictions[item["sample_id"]]
        ai_effect_elements = _ai_effect_elements(ai_draft, prefab_path)
        ai_effect_type = _ai_effect_type(ai_draft, prefab_path)
        allowed_actions = SEMANTIC_ACTIONS if review_mode == "semantic_function_only" else ALLOWED_ACTIONS
        records.append({
            "review_index": len(records) + 1,
            "sample_id": item["sample_id"],
            "prefab_path": prefab_path,
            "cluster_id": item["cluster_id"],
            "selection_reason": item["selection_reason"],
            "selection_reason_cn": REASON_CN.get(item["selection_reason"], item["selection_reason"]),
            "priority_score": item["priority_score"],
            "ai_draft": ai_draft,
            "ai_summary_cn": _ai_summary(ai_draft),
            "review_mode": review_mode,
            "semantic_schema_version": SEMANTIC_SCHEMA_VERSION,
            "ai_effect_elements": ai_effect_elements,
            "ai_effect_elements_cn": [ELEMENT_OPTION_LABELS[value] for value in ai_effect_elements],
            "ai_effect_type": ai_effect_type,
            "ai_effect_type_cn": EFFECT_TYPE_OPTION_LABELS[ai_effect_type],
            "element_options": [{"value": value, "label": label} for value, label in ELEMENT_OPTIONS],
            "effect_type_options": [{"value": value, "label": label} for value, label in EFFECT_TYPE_OPTIONS],
            "capture_manifest_path": _portable(manifest_path),
            "capture_pipeline_version": manifest["capture_pipeline_version"],
            "peak_frame_index": peak_frame_index,
            "frames": frames,
            "webgl_preview": {"player_url": player_url, "catalog_id": catalog_id} if player_url and catalog_id else None,
            "allowed_actions": list(allowed_actions),
        })
    batch_actions = SEMANTIC_ACTIONS if review_mode == "semantic_function_only" else ALLOWED_ACTIONS
    batch = {
        "schema_version": BATCH_SCHEMA,
        "created_at": _now(),
        "batch_id": batch_id,
        "review_mode": review_mode,
        "semantic_schema_version": SEMANTIC_SCHEMA_VERSION if review_mode == "semantic_function_only" else None,
        "source_active_batch": _portable(active_root / "active_learning_batch.json"),
        "selection_strategy": "bounded_active_learning_chinese_correction.v1",
        "record_count": len(records),
        "allowed_actions": list(batch_actions),
        "records": records,
    }
    _validate(_validator("prefab_active_review_batch.schema.json"), batch, "active review batch")
    paths = {
        "review_batch": _write_json(output_root / "review_batch.json", batch),
        "feedback_store": _write_json(output_root / "feedback_store.json", {"schema_version": "vfx_prefab_active_review_store.v1", "batch_id": batch_id, "records": {}}),
        "feedback": _write_jsonl(output_root / "feedback.jsonl", []),
        "semantic_options": _write_json(output_root / "custom_semantic_options.json", {
            "schema_version": "vfx_prefab_custom_semantic_options.v2",
            "batch_id": batch_id,
            "updated_at": _now(),
            "options": [],
        }),
    }
    if carry_feedback_root is not None:
        paths["feedback_carry_manifest"] = carry_compatible_feedback(carry_feedback_root, output_root)
    return paths


def _normalize_actions(payload: dict[str, Any]) -> list[str]:
    raw_actions = payload.get("actions")
    if raw_actions is None:
        raw_actions = [payload.get("action")]
    if not isinstance(raw_actions, list):
        raise ValueError("active review actions must be a list")
    actions = []
    for value in raw_actions:
        if not isinstance(value, str) or value not in ALLOWED_ACTIONS:
            raise ValueError(f"unsupported active review action: {value}")
        if value not in actions:
            actions.append(value)
    if not actions:
        raise ValueError("active review requires at least one action")
    if any(action in EXCLUSION_ACTIONS for action in actions) and len(actions) > 1:
        raise ValueError("无法播放和无法判断不能与其他选项同时选择")
    if "AI判断正确" in actions and len(actions) > 1:
        raise ValueError("AI判断正确不能与修正选项同时选择")
    if {"应该更好", "应该更差"}.issubset(actions):
        raise ValueError("应该更好和应该更差不能同时选择")
    return sorted(actions, key=ALLOWED_ACTIONS.index)


def _corrected_result(actions: list[str], draft: dict[str, Any]) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    labels = _draft_labels(draft)
    labels.setdefault("issues", [])
    delta: dict[str, Any] = {"selected_actions": list(actions)}
    tasks: set[str] = set()
    for action in actions:
        if action in {"应该更好", "应该更差"}:
            direction = "higher" if action == "应该更好" else "lower"
            delta["quality_direction"] = direction
            labels["quality_direction"] = direction
            current = labels.get("quality_score")
            if isinstance(current, (int, float)) and not isinstance(current, bool):
                labels["quality_score"] = max(0.0, min(5.0, float(current) + (1.0 if direction == "higher" else -1.0)))
                delta["quality_score"] = labels["quality_score"]
        issue = ACTION_ISSUES.get(action)
        if issue:
            labels["issues"] = sorted(set([*labels.get("issues", []), issue]))
            delta.setdefault("issues_added", []).append(issue)
        if action == "特效类型错误":
            labels["observed_element_tags"] = []
            delta["observed_element_tags"] = []
        tasks.update(ACTION_TASKS.get(action, []))
    labels["decision"] = actions[0] if len(actions) == 1 else "；".join(actions)
    labels["decisions"] = list(actions)
    if actions == ["AI判断正确"]:
        tasks = {"pseudo_label_calibration"}
        if labels.get("observed_element_tags"):
            tasks.add("element_supervision")
        if labels.get("observed_color_tags"):
            tasks.add("color_supervision")
        if labels.get("quality_score") is not None:
            tasks.add("aesthetic_judge")
    return labels, sorted(tasks), delta


def _semantic_result(
    source: dict[str, Any],
    payload: dict[str, Any],
    element_labels: Mapping[str, str],
    effect_type_labels: Mapping[str, str],
) -> tuple[list[str], bool, dict[str, Any], list[str], dict[str, Any], dict[str, Any]]:
    exclusion = payload.get("exclusion_action")
    if exclusion is not None:
        if exclusion not in EXCLUSION_ACTIONS:
            raise ValueError(f"unsupported semantic exclusion action: {exclusion}")
        return [str(exclusion)], True, {}, [], {"semantic_scope": "element_and_type", "semantic_schema_version": SEMANTIC_SCHEMA_VERSION}, {
            "semantic_schema_version": SEMANTIC_SCHEMA_VERSION,
            "ai_effect_elements": source["ai_effect_elements"],
            "selected_effect_elements": None,
            "selected_effect_elements_cn": None,
            "ai_effect_type": source["ai_effect_type"],
            "selected_effect_type": None,
            "selected_effect_type_cn": None,
        }
    selected_elements_raw = payload.get("effect_elements")
    if not isinstance(selected_elements_raw, list):
        raise ValueError("特效元素必须是列表")
    selected_elements = []
    for value in selected_elements_raw:
        value = str(value)
        if value not in element_labels:
            raise ValueError(f"unsupported semantic effect element: {value or '<empty>'}")
        if value not in selected_elements:
            selected_elements.append(value)
    if not selected_elements:
        raise ValueError("至少选择一个特效元素；没有明确元素时请选择无明确元素")
    if "none" in selected_elements and len(selected_elements) > 1:
        raise ValueError("无明确元素不能与其他元素同时选择")
    selected_type = _canonical_effect_type(payload.get("effect_type") or "")
    if selected_type not in effect_type_labels:
        raise ValueError(f"unsupported semantic effect type: {selected_type or '<empty>'}")
    selected_elements = sorted(selected_elements, key=lambda value: list(element_labels).index(value))
    ai_elements = list(source["ai_effect_elements"])
    ai_effect_type = _canonical_effect_type(source["ai_effect_type"])
    actions = []
    if selected_elements != ai_elements:
        actions.append("特效元素错误")
    if selected_type != ai_effect_type:
        actions.append("特效类型错误")
    if not actions:
        actions = ["AI判断正确"]
    labels = {
        "target_effect_family": selected_type,
        "effect_type": selected_type,
        "target_color_tags": [],
        "observed_element_tags": [] if selected_elements == ["none"] else selected_elements,
        "observed_color_tags": [],
        "quality_score": None,
        "scores": {},
        "issues": [] if actions == ["AI判断正确"] else list(actions),
        "decision": actions[0] if len(actions) == 1 else "；".join(actions),
        "decisions": list(actions),
    }
    tasks = ["effect_element_supervision", "effect_type_supervision", "pseudo_label_calibration"]
    delta = {
        "semantic_scope": "element_and_type",
        "semantic_schema_version": SEMANTIC_SCHEMA_VERSION,
        "ai_effect_elements": ai_elements,
        "selected_effect_elements": selected_elements,
        "selected_effect_elements_cn": [element_labels[value] for value in selected_elements],
        "ai_effect_type": ai_effect_type,
        "selected_effect_type": selected_type,
        "selected_effect_type_cn": effect_type_labels[selected_type],
    }
    return actions, False, labels, tasks, delta, {
        "semantic_schema_version": SEMANTIC_SCHEMA_VERSION,
        "ai_effect_elements": ai_elements,
        "selected_effect_elements": selected_elements,
        "selected_effect_elements_cn": [element_labels[value] for value in selected_elements],
        "ai_effect_type": ai_effect_type,
        "selected_effect_type": selected_type,
        "selected_effect_type_cn": effect_type_labels[selected_type],
    }


def _review_summary_actions(batch: dict[str, Any]) -> tuple[str, ...]:
    if batch.get("review_mode") == "semantic_function_only":
        return tuple(str(action) for action in batch.get("allowed_actions") or SEMANTIC_ACTIONS)
    return ALLOWED_ACTIONS


def save_feedback(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    batch = _read_json(root / "review_batch.json")
    sources = {str(row["sample_id"]): row for row in batch["records"]}
    sample_id = str(payload.get("sample_id") or "")
    notes = payload.get("notes", "")
    if sample_id not in sources:
        raise ValueError(f"sample is not in active review batch: {sample_id}")
    if not isinstance(notes, str):
        raise ValueError("active review notes must be a string")
    source = sources[sample_id]
    review_scope = str(source.get("review_mode") or batch.get("review_mode") or "aesthetic_correction")
    semantic_selection = None
    if review_scope == "semantic_function_only":
        if source.get("semantic_schema_version") != SEMANTIC_SCHEMA_VERSION:
            raise ValueError("旧语义维度不能继续提交，请使用拆分元素与类型的新批次")
        actions, excluded, labels, tasks, delta, semantic_selection = _semantic_result(
            source,
            payload,
            _semantic_option_labels(root, "effect_element"),
            _semantic_option_labels(root, "effect_type"),
        )
    else:
        actions = _normalize_actions(payload)
        excluded = any(action in EXCLUSION_ACTIONS for action in actions)
        labels, tasks, delta = ({}, [], {"selected_actions": list(actions)}) if excluded else _corrected_result(actions, source["ai_draft"])
    reviewed_at = _now()
    record_id = "active_feedback_" + hashlib.sha256(f"{batch['batch_id']}|{sample_id}|{reviewed_at}|{'|'.join(actions)}".encode("utf-8")).hexdigest()[:20]
    feedback = {
        "schema_version": FEEDBACK_SCHEMA,
        "record_id": record_id,
        "batch_id": batch["batch_id"],
        "sample_id": sample_id,
        "prefab_path": source["prefab_path"],
        "action": actions[0],
        "selected_actions": actions,
        "review_scope": review_scope,
        "semantic_selection": semantic_selection,
        "notes": notes.strip(),
        "reviewed_at": reviewed_at,
        "reviewer": "local_human",
        "confirmation_mode": "human_exclusion" if excluded else "human_accepted_ai_draft" if actions == ["AI判断正确"] else "human_corrected_ai_draft",
        "ai_draft": deepcopy(source["ai_draft"]),
        "correction": {"action": actions[0], "label_delta": delta},
        "evidence": {
            "capture_manifest_path": source["capture_manifest_path"],
            "capture_pipeline_version": source["capture_pipeline_version"],
            "dynamic_frame_paths": [frame["path"] for frame in source["frames"]],
            "webgl_catalog_id": (source.get("webgl_preview") or {}).get("catalog_id"),
        },
        "result": {
            "disposition": "excluded" if excluded else "human_gold",
            "trainable": not excluded,
            "labels": labels,
            "eligible_tasks": tasks,
            "exclusion_reason": "human_unable_to_play" if actions == ["无法播放"] else "human_unable_to_judge" if actions == ["无法判断"] else None,
        },
    }
    _validate(_validator("prefab_active_review_feedback.schema.json"), feedback, "active review feedback")
    with _FEEDBACK_LOCK:
        store = _read_json(root / "feedback_store.json")
        entry = store["records"].setdefault(sample_id, {"revisions": [], "latest": None})
        entry["revisions"].append(feedback)
        entry["latest"] = feedback
        _write_json(root / "feedback_store.json", store)
        _write_jsonl(root / "feedback.jsonl", (store["records"][key]["latest"] for key in sorted(store["records"])))
    return feedback


def carry_compatible_feedback(source_root: Path, target_root: Path) -> Path:
    source_root = source_root.resolve()
    target_root = target_root.resolve()
    source_store = _read_json(source_root / "feedback_store.json")
    target_batch = _read_json(target_root / "review_batch.json")
    target_store = _read_json(target_root / "feedback_store.json")
    source_options = _semantic_option_store(source_root)
    target_options = _semantic_option_store(target_root)
    target_options["options"] = deepcopy(source_options["options"])
    target_options["updated_at"] = _now()
    _validate(_validator("prefab_active_review_semantic_options.schema.json"), target_options, "carried custom semantic options")
    _write_json(target_root / "custom_semantic_options.json", target_options)
    targets = {str(row["sample_id"]): row for row in target_batch["records"]}
    carried = []
    skipped = []
    normalized_alias_count = 0
    effect_type_labels = _semantic_option_labels(target_root, "effect_type")
    for sample_id, entry in sorted((source_store.get("records") or {}).items()):
        feedback = deepcopy((entry or {}).get("latest"))
        target = targets.get(str(sample_id))
        reason = None
        if not isinstance(feedback, dict):
            reason = "missing_latest_feedback"
        elif target is None:
            reason = "sample_not_in_target_batch"
        elif str(feedback.get("prefab_path") or "") != str(target.get("prefab_path") or ""):
            reason = "prefab_path_changed"
        elif str(feedback.get("review_scope") or "") != str(target.get("review_mode") or target_batch.get("review_mode") or ""):
            reason = "review_scope_changed"
        elif str((feedback.get("semantic_selection") or {}).get("semantic_schema_version") or "") != str(target.get("semantic_schema_version") or ""):
            reason = "semantic_schema_changed"
        elif str((feedback.get("evidence") or {}).get("capture_manifest_path") or "") != str(target.get("capture_manifest_path") or ""):
            reason = "capture_evidence_changed"
        if reason:
            skipped.append({"sample_id": sample_id, "reason": reason})
            continue
        feedback, alias_count = _normalize_feedback_effect_type(feedback, target, target_batch["batch_id"], effect_type_labels)
        normalized_alias_count += alias_count
        _validate(_validator("prefab_active_review_feedback.schema.json"), feedback, "carried active review feedback")
        target_store["records"][sample_id] = {"revisions": [feedback], "latest": feedback}
        carried.append({"sample_id": sample_id, "feedback_record_id": feedback["record_id"]})
    _write_json(target_root / "feedback_store.json", target_store)
    _write_jsonl(target_root / "feedback.jsonl", (target_store["records"][key]["latest"] for key in sorted(target_store["records"])))
    return _write_json(target_root / "feedback_carry_manifest.json", {
        "schema_version": "vfx_prefab_active_review_feedback_carry.v1",
        "created_at": _now(),
        "source_batch_id": source_store.get("batch_id"),
        "target_batch_id": target_batch["batch_id"],
        "source_feedback_count": len(source_store.get("records") or {}),
        "carried_count": len(carried),
        "skipped_count": len(skipped),
        "carried_custom_semantic_option_count": len(target_options["options"]),
        "normalized_effect_type_alias_count": normalized_alias_count,
        "carried": carried,
        "skipped": skipped,
        "quality_gates": {"capture_evidence_mismatch_carried": 0, "review_scope_mismatch_carried": 0},
        "status": "pass",
    })


def _human_gold(feedback: dict[str, Any], base_records: list[dict[str, Any]]) -> dict[str, Any]:
    technical = next(row for row in base_records if row["tier"] == "technical_corpus")
    parent_ids = [row["record_id"] for row in base_records if row["tier"] == "ai_pseudo_label"]
    record = deepcopy(technical)
    record.update({
        "record_id": "layer_" + hashlib.sha256(f"{feedback['record_id']}|human_gold".encode("utf-8")).hexdigest()[:20],
        "tier": "human_gold",
        "observations": {"ai_draft": feedback["ai_draft"], "human_correction": feedback["correction"]},
        "labels": feedback["result"]["labels"],
        "label_provenance": {
            "label_source": "human", "confidence": 1.0, "model_version": None, "reviewer": feedback["reviewer"],
            "parent_human_record_id": None, "distance": None, "created_at": feedback["reviewed_at"],
        },
        "training": {
            "weight": 1.0,
            "eligible_tasks": feedback["result"]["eligible_tasks"],
            "excluded_tasks": ["preference_training", "regression_evaluation", "model_promotion"],
            "split": technical["training"]["split"],
            "frozen": False,
            "expires_with_model_version": False,
        },
        "status": "ready",
        "limitations": [],
    })
    record["evidence"] = deepcopy(technical["evidence"])
    record["evidence"].update({
        "capture_manifest_path": feedback["evidence"]["capture_manifest_path"],
        "human_record_id": feedback["record_id"],
        "parent_record_ids": parent_ids,
    })
    _validate(_validator("prefab_training_layer_record.schema.json"), record, "human gold")
    return record


def finalize_feedback(root: Path) -> dict[str, Path]:
    root = root.resolve()
    batch = _read_json(root / "review_batch.json")
    store = _read_json(root / "feedback_store.json")
    missing = [row["sample_id"] for row in batch["records"] if row["sample_id"] not in store["records"]]
    if missing:
        raise ValueError(f"active review is incomplete; next missing sample: {missing[0]}")
    active_root = _resolve(str(Path(batch["source_active_batch"]).parent))
    routed = _read_jsonl(active_root / "routed_records.jsonl")
    by_sample: dict[str, list[dict[str, Any]]] = {}
    for row in routed:
        by_sample.setdefault(str(row["sample_id"]), []).append(row)
    human_gold = []
    exclusions = []
    for source in batch["records"]:
        feedback = store["records"][source["sample_id"]]["latest"]
        _validate(_validator("prefab_active_review_feedback.schema.json"), feedback, "stored active review feedback")
        if feedback["result"]["trainable"]:
            human_gold.append(_human_gold(feedback, by_sample[source["sample_id"]]))
        else:
            exclusions.append({
                "schema_version": "vfx_prefab_active_review_exclusion.v1",
                "sample_id": feedback["sample_id"],
                "prefab_path": feedback["prefab_path"],
                "reason": feedback["result"]["exclusion_reason"],
                "human_feedback_record_id": feedback["record_id"],
                "excluded_from": ["human_gold", "aesthetic_judge", "preference_training", "positive_generation_supervision", "regression_evaluation"],
            })
    summary = {
        "schema_version": "vfx_prefab_active_review_summary.v1",
        "created_at": _now(),
        "batch_id": batch["batch_id"],
        "review_count": len(batch["records"]),
        "human_gold_count": len(human_gold),
        "exclusion_count": len(exclusions),
        "action_counts": {
            action: sum(action in (store["records"][row["sample_id"]]["latest"].get("selected_actions") or [store["records"][row["sample_id"]]["latest"].get("action")]) for row in batch["records"])
            for action in _review_summary_actions(batch)
        },
        "capture_v2_only": True,
        "unable_actions_are_exclusions": True,
        "status": "pass",
    }
    return {
        "human_gold": _write_jsonl(root / "human_gold.jsonl", human_gold),
        "exclusions": _write_jsonl(root / "exclusions.jsonl", exclusions),
        "summary": _write_json(root / "review_summary.json", summary),
    }


HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prefab 主动复核</title><style>
:root{--bg:#111417;--panel:#181d21;--line:#30383e;--text:#edf1f2;--muted:#9ba6ad;--cyan:#55b8c7;--green:#79bd85;--yellow:#d7b861;--red:#d87b6e}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 "Segoe UI","Microsoft YaHei",sans-serif}button,textarea,input{font:inherit}header{height:52px;display:flex;align-items:center;padding:0 16px;border-bottom:1px solid var(--line);gap:12px}h1{font-size:16px;margin:0}.progress{margin-left:auto;color:var(--muted)}main{height:calc(100vh - 52px);display:grid;grid-template-columns:260px minmax(420px,1fr) 360px;gap:10px;padding:10px}.pane{border:1px solid var(--line);background:var(--panel);min-height:0}.queue{overflow:auto;padding:7px}.queue button{width:100%;display:grid;grid-template-columns:30px minmax(0,1fr);gap:7px;padding:8px;border:1px solid transparent;background:none;color:var(--text);text-align:left}.queue button.active{border-color:var(--cyan);background:#20282d}.queue small{display:block;color:var(--muted);overflow-wrap:anywhere}.stage{display:grid;grid-template-rows:minmax(0,1fr) 96px 40px}.viewer{display:grid;place-items:center;background:#080a0c;overflow:hidden}.viewer img,.viewer iframe{max-width:100%;max-height:100%;border:0}.viewer iframe{width:100%;height:100%}.frames{display:flex;gap:5px;overflow-x:auto;padding:6px;border-top:1px solid var(--line)}.frames button{flex:0 0 82px;background:#101417;border:1px solid var(--line);color:var(--muted)}.frames button.active{border-color:var(--yellow)}.frames img{width:72px;height:58px;object-fit:contain}.transport{display:grid;grid-template-columns:auto 34px minmax(80px,1fr) auto;gap:8px;align-items:center;padding:5px 8px;border-top:1px solid var(--line)}.mode{display:grid;grid-template-columns:1fr 1fr}.mode button,.icon{height:30px;border:1px solid var(--line);background:#222a30;color:var(--text)}.mode button.active{border-color:var(--cyan);color:#d9f8fc}.review{padding:12px;overflow:auto}.meta{display:grid;gap:7px;margin-bottom:12px}.meta div{padding:8px;background:#20262b;color:var(--muted)}.meta b{display:block;color:var(--text)}.actions{display:grid;grid-template-columns:1fr 1fr;gap:7px}.actions button{min-height:40px;border:1px solid var(--line);background:#222a30;color:var(--text);padding:7px}.actions button:hover{border-color:var(--cyan)}.actions button.exclude{border-color:#704a46}label{display:block;color:var(--muted);margin:12px 0 5px}textarea{width:100%;min-height:76px;resize:vertical;background:#101417;border:1px solid var(--line);color:var(--text);padding:8px}.status{margin-top:10px;color:var(--green)}.error{color:var(--red)}@media(max-width:900px){main{height:auto;grid-template-columns:1fr}.queue{max-height:220px}.stage{height:560px}.review{overflow:visible}}
</style></head><body><header><h1>Prefab 主动复核</h1><span id="batch"></span><span class="progress" id="progress"></span></header><main><aside class="pane queue" id="queue"></aside><section class="pane stage"><div class="viewer" id="viewer"></div><div class="frames" id="frames"></div><div class="transport"><div class="mode" id="mode"><button id="framesMode">截图</button><button id="webglMode">WebGL</button></div><button class="icon" id="play" title="播放">▶</button><input id="timeline" type="range" min="0" max="0" value="0"><span id="time"></span></div></section><aside class="pane review"><div class="meta" id="meta"></div><div class="actions" id="actions"></div><label for="notes">备注</label><textarea id="notes" maxlength="2000"></textarea><div class="status" id="status"></div></aside></main><script>
let batch,store={},index=0,frame=0,timer=null,mode='frames';const $=id=>document.getElementById(id),cur=()=>batch.records[index],asset=p=>'/asset/'+p.split('/').map(encodeURIComponent).join('/'),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function renderQueue(){$('queue').innerHTML=batch.records.map((r,i)=>`<button class="${i===index?'active':''}" data-i="${i}"><span>${String(i+1).padStart(3,'0')}</span><span>${esc(r.ai_summary_cn)}<small>${esc(r.prefab_path)}</small></span></button>`).join('');document.querySelectorAll('#queue button').forEach(b=>b.onclick=()=>{stop();index=Number(b.dataset.i);frame=cur().peak_frame_index||0;render()})}
function webglSrc(p){let u=new URL(p.player_url);u.searchParams.set('embed','1');u.searchParams.set('parentOrigin',location.origin);u.searchParams.set('catalogId',p.catalog_id);return u.toString()}function renderViewer(){let r=cur(),f=r.frames[frame],hasWebgl=Boolean(r.webgl_preview);if(!hasWebgl)mode='frames';$('mode').style.display=hasWebgl?'grid':'none';$('framesMode').className=mode==='frames'?'active':'';$('webglMode').className=mode==='webgl'?'active':'';$('play').disabled=mode==='webgl';$('timeline').disabled=mode==='webgl';$('viewer').innerHTML=mode==='webgl'?`<iframe src="${esc(webglSrc(r.webgl_preview))}" title="Unity WebGL Prefab"></iframe>`:f?`<img src="${asset(f.path)}" alt="Capture v2 动态帧">`:'';$('frames').innerHTML=r.frames.map((x,i)=>`<button class="${i===frame?'active':''}" data-i="${i}"><img src="${asset(x.path)}"><span>${Number(x.time_seconds).toFixed(3)}s</span></button>`).join('');document.querySelectorAll('#frames button').forEach(b=>b.onclick=()=>{stop();mode='frames';frame=Number(b.dataset.i);renderViewer()});$('timeline').max=Math.max(0,r.frames.length-1);$('timeline').value=frame;$('time').textContent=mode==='webgl'?'WebGL':`${frame+1}/${r.frames.length}`}
function renderReview(){let r=cur(),saved=store[r.sample_id]?.latest;$('meta').innerHTML=`<div><b>AI 草稿</b>${esc(r.ai_summary_cn)}</div><div><b>入队原因</b>${esc(r.selection_reason_cn)}</div><div><b>证据</b>Capture v2 · ${r.frames.length} 帧</div>`;$('actions').innerHTML=r.allowed_actions.map(a=>`<button class="${a.startsWith('无法')?'exclude':''}" data-action="${esc(a)}">${esc(a)}</button>`).join('');document.querySelectorAll('#actions button').forEach(b=>b.onclick=()=>save(b.dataset.action));$('notes').value=saved?.notes||'';$('status').textContent=saved?`已选择：${saved.action}`:''}
function render(){renderQueue();renderViewer();renderReview();$('batch').textContent=batch.batch_id;$('progress').textContent=`${Object.keys(store).length}/${batch.records.length}`}
function stop(){if(timer){clearTimeout(timer);timer=null;$('play').textContent='▶'}}function tick(){let frames=cur().frames,next=(frame+1)%frames.length,delay=Math.max(50,Math.min(500,(frames[next].time_seconds-frames[frame].time_seconds)*1000||100));frame=next;renderViewer();timer=setTimeout(tick,delay)}
async function save(action){let r=cur(),response=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_id:r.sample_id,action,notes:$('notes').value})}),data=await response.json();if(!response.ok){$('status').className='status error';$('status').textContent=data.error;return}$('status').className='status';store[r.sample_id]={latest:data.record};let next=batch.records.findIndex((x,i)=>i>index&&!store[x.sample_id]);if(next>=0){index=next;frame=cur().peak_frame_index||0}render()}
$('play').onclick=()=>{if(timer)stop();else{$('play').textContent='■';tick()}};$('timeline').oninput=e=>{stop();frame=Number(e.target.value);renderViewer()};Promise.all([fetch('/api/batch').then(r=>r.json()),fetch('/api/feedback').then(r=>r.json())]).then(([b,s])=>{batch=b;store=s.records||{};let first=batch.records.findIndex(r=>!store[r.sample_id]);if(first>=0)index=first;frame=cur().peak_frame_index||0;render()});
$('framesMode').onclick=()=>{stop();mode='frames';renderViewer()};$('webglMode').onclick=()=>{stop();mode='webgl';renderViewer()};
</script></body></html>'''


_MULTI_SELECT_REVIEW_SCRIPT = r'''let batch,store={},index=0,frame=0,timer=null,mode='frames',pendingActions=[],pendingActionsDirty=false,pendingNotes='',pendingNotesDirty=false;
const $=id=>document.getElementById(id),cur=()=>batch.records[index],asset=p=>'/asset/'+p.split('/').map(encodeURIComponent).join('/'),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const exclusionActions=new Set(['无法播放','无法判断']),qualityActions=new Set(['应该更好','应该更差']);
function savedActions(r){let value=store[r.sample_id]?.latest?.selected_actions;if(!Array.isArray(value)||!value.length)value=store[r.sample_id]?.latest?.action?[store[r.sample_id].latest.action]:[];return value}
function savedNotes(r){return store[r.sample_id]?.latest?.notes||''}
function selectedActions(){return pendingActionsDirty?[...pendingActions]:savedActions(cur())}
function selectedNotes(){return pendingNotesDirty?pendingNotes:savedNotes(cur())}
function beginActionSelection(){if(!pendingActionsDirty){pendingActions=savedActions(cur());pendingActionsDirty=true}}
function toggleAction(action){beginActionSelection();if(exclusionActions.has(action)){pendingActions=pendingActions.includes(action)?[]:[action]}else if(action==='AI判断正确'){pendingActions=pendingActions.includes(action)?[]:['AI判断正确']}else{pendingActions=pendingActions.filter(x=>x!=='AI判断正确'&&!(qualityActions.has(x)&&qualityActions.has(action)));pendingActions=pendingActions.includes(action)?pendingActions.filter(x=>x!==action):[...pendingActions,action]}renderReview()}
function renderQueue(){$('queue').innerHTML=batch.records.map((r,i)=>`<button class="${i===index?'active':''} ${store[r.sample_id]?'done':''}" data-i="${i}"><span>${String(i+1).padStart(3,'0')}</span><span>${esc(r.ai_summary_cn)}<small>${esc(r.prefab_path)}</small></span></button>`).join('');document.querySelectorAll('#queue button').forEach(b=>b.onclick=()=>{stop();index=Number(b.dataset.i);pendingActions=[];pendingActionsDirty=false;pendingNotes='';pendingNotesDirty=false;frame=cur().peak_frame_index||0;render()})}
function webglSrc(p){let u=new URL(p.player_url);u.searchParams.set('embed','1');u.searchParams.set('parentOrigin',location.origin);u.searchParams.set('catalogId',p.catalog_id);return u.toString()}
function renderViewer(){let r=cur(),f=r.frames[frame],hasWebgl=Boolean(r.webgl_preview);if(!hasWebgl)mode='frames';$('mode').style.display=hasWebgl?'grid':'none';$('framesMode').className=mode==='frames'?'active':'';$('webglMode').className=mode==='webgl'?'active':'';$('play').disabled=mode==='webgl';$('timeline').disabled=mode==='webgl';$('viewer').innerHTML=mode==='webgl'?`<iframe src="${esc(webglSrc(r.webgl_preview))}" title="Unity WebGL Prefab"></iframe>`:f?`<img src="${asset(f.path)}" alt="Capture v2 动态帧">`:'';$('frames').innerHTML=r.frames.map((x,i)=>`<button class="${i===frame?'active':''}" data-i="${i}"><img src="${asset(x.path)}"><span>${Number(x.time_seconds).toFixed(3)}s</span></button>`).join('');document.querySelectorAll('#frames button').forEach(b=>b.onclick=()=>{stop();mode='frames';frame=Number(b.dataset.i);renderViewer()});$('timeline').max=Math.max(0,r.frames.length-1);$('timeline').value=frame;$('time').textContent=mode==='webgl'?'WebGL':`${frame+1}/${r.frames.length}`}
function renderReview(){let r=cur(),saved=store[r.sample_id]?.latest,selected=selectedActions();$('meta').innerHTML=`<div><b>AI 草稿</b>${esc(r.ai_summary_cn)}</div><div><b>入队原因</b>${esc(r.selection_reason_cn)}</div><div><b>证据</b>Capture v2 · ${r.frames.length} 帧</div>`;$('actions').innerHTML=r.allowed_actions.map(a=>`<button class="${a.startsWith('无法')?'exclude ':''}${selected.includes(a)?'selected':''}" aria-pressed="${selected.includes(a)}" data-action="${esc(a)}">${esc(a)}</button>`).join('');document.querySelectorAll('#actions button').forEach(b=>b.onclick=()=>toggleAction(b.dataset.action));$('selectionSummary').textContent=selected.length?`已选择：${selected.join('、')}`:'请选择一个或多个判断';$('confirm').disabled=selected.length===0;$('confirm').onclick=confirmSelection;$('clear').onclick=()=>{pendingActions=[];pendingActionsDirty=true;renderReview()};$('notes').value=selectedNotes();$('notes').oninput=()=>{pendingNotes=$('notes').value;pendingNotesDirty=true;$('status').textContent=selected.length?`待确认：${selected.join('、')}`:'尚未选择'};$('status').textContent=(pendingActionsDirty||pendingNotesDirty)?(selected.length?`待确认：${selected.join('、')}`:'尚未选择'):saved?`已保存：${selected.join('、')}`:'未评价'}
function render(){renderQueue();renderViewer();renderReview();$('batch').textContent=batch.batch_id;$('progress').textContent=`${Object.keys(store).length}/${batch.records.length}`}
function stop(){if(timer){clearTimeout(timer);timer=null;$('play').textContent='▶'}}function tick(){let frames=cur().frames,next=(frame+1)%frames.length,delay=Math.max(50,Math.min(500,(frames[next].time_seconds-frames[frame].time_seconds)*1000||100));frame=next;renderViewer();timer=setTimeout(tick,delay)}
async function confirmSelection(){let r=cur(),actions=selectedActions();if(!actions.length)return;$('confirm').disabled=true;let response=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_id:r.sample_id,actions,notes:selectedNotes()})}),data=await response.json();if(!response.ok){$('status').className='status error';$('status').textContent=data.error;$('confirm').disabled=false;return}$('status').className='status';store[r.sample_id]={latest:data.record};pendingActions=[];pendingActionsDirty=false;pendingNotes='';pendingNotesDirty=false;let next=batch.records.findIndex((x,i)=>i>index&&!store[x.sample_id]);if(next>=0){index=next;frame=cur().peak_frame_index||0}render()}
$('play').onclick=()=>{if(timer)stop();else{$('play').textContent='■';tick()}};$('timeline').oninput=e=>{stop();frame=Number(e.target.value);renderViewer()};Promise.all([fetch('/api/batch').then(r=>r.json()),fetch('/api/feedback').then(r=>r.json())]).then(([b,s])=>{batch=b;store=s.records||{};let first=batch.records.findIndex(r=>!store[r.sample_id]);if(first>=0)index=first;frame=cur().peak_frame_index||0;render()});
$('framesMode').onclick=()=>{stop();mode='frames';renderViewer()};$('webglMode').onclick=()=>{stop();mode='webgl';renderViewer()};'''


def _build_multi_select_review_html() -> str:
    html = HTML.replace(
        ".actions button:hover{border-color:var(--cyan)}",
        ".actions button:hover{border-color:var(--cyan)}.actions button.selected{border-color:var(--green);background:#214c40}.selection-summary{margin-top:10px;color:var(--muted);font-size:12px}.confirm-row{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:10px}.confirm-row button{min-height:38px;border:1px solid var(--line);background:#222a30;color:var(--text);padding:7px;cursor:pointer}.confirm-row .confirm{border-color:var(--green);background:#20372a}.confirm-row .confirm:disabled{cursor:not-allowed;opacity:.45}.confirm-row .clear{border-color:var(--line)}"
    )
    html = html.replace(
        '<div class="actions" id="actions"></div><label for="notes">备注</label>',
        '<div class="actions" id="actions"></div><div class="selection-summary" id="selectionSummary"></div><div class="confirm-row"><button id="confirm" class="confirm" disabled>确认本条</button><button id="clear" class="clear">清除选择</button></div><label for="notes">备注</label>'
    )
    start = html.index("<script>\nlet batch,store={}")
    end = html.index("</script></body></html>", start)
    return html[:start] + "<script>\n" + _MULTI_SELECT_REVIEW_SCRIPT + "\n</script></body></html>" + html[end + len("</script></body></html>"):]


HTML = _build_multi_select_review_html()


_SEMANTIC_REVIEW_SCRIPT = r'''let batch,store={},customSemanticOptions=[],index=0,frame=0,timer=null,mode='frames',pendingElements=[],pendingElementsDirty=false,pendingType='',pendingTypeDirty=false,pendingExclusion=null,pendingExclusionDirty=false,pendingNotes='',pendingNotesDirty=false;
const $=id=>document.getElementById(id),cur=()=>batch.records[index],asset=p=>'/asset/'+p.split('/').map(encodeURIComponent).join('/'),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function dimensionOptions(r,dimension){let base=dimension==='effect_element'?r.element_options:r.effect_type_options,custom=customSemanticOptions.filter(x=>x.dimension===dimension),seen=new Set();return [...base,...custom].filter(x=>!seen.has(x.value)&&(seen.add(x.value),true))}function savedRecord(r){return store[r.sample_id]?.latest||null}function savedElements(r){return savedRecord(r)?.semantic_selection?.selected_effect_elements||r.ai_effect_elements}function savedType(r){return savedRecord(r)?.semantic_selection?.selected_effect_type||r.ai_effect_type}function savedExclusion(r){let a=savedRecord(r)?.action;return a==='无法播放'||a==='无法判断'?a:null}function selectedElements(){return pendingElementsDirty?[...pendingElements]:savedElements(cur())}function selectedType(){return pendingTypeDirty?pendingType:savedType(cur())}function selectedExclusion(){return pendingExclusionDirty?pendingExclusion:savedExclusion(cur())}function selectedNotes(){return pendingNotesDirty?pendingNotes:(savedRecord(cur())?.notes||'')}
function resetPending(){pendingElements=[];pendingElementsDirty=false;pendingType='';pendingTypeDirty=false;pendingExclusion=null;pendingExclusionDirty=false;pendingNotes='';pendingNotesDirty=false}
function renderQueue(){$('queue').innerHTML=batch.records.map((r,i)=>`<button class="${i===index?'active':''} ${store[r.sample_id]?'done':''}" data-i="${i}"><span>${String(i+1).padStart(3,'0')}</span><span>AI类型：${esc(r.ai_effect_type_cn)}<small>${esc(r.prefab_path)}</small></span></button>`).join('');document.querySelectorAll('#queue button').forEach(b=>b.onclick=()=>{stop();index=Number(b.dataset.i);resetPending();frame=cur().peak_frame_index||0;render()})}
function webglSrc(p){let u=new URL(p.player_url);u.searchParams.set('embed','1');u.searchParams.set('parentOrigin',location.origin);u.searchParams.set('catalogId',p.catalog_id);return u.toString()}
function renderViewer(){let r=cur(),f=r.frames[frame],hasWebgl=Boolean(r.webgl_preview);if(!hasWebgl)mode='frames';$('mode').style.display=hasWebgl?'grid':'none';$('framesMode').className=mode==='frames'?'active':'';$('webglMode').className=mode==='webgl'?'active':'';$('play').disabled=mode==='webgl';$('timeline').disabled=mode==='webgl';$('viewer').innerHTML=mode==='webgl'?`<iframe src="${esc(webglSrc(r.webgl_preview))}" title="Unity WebGL Prefab"></iframe>`:f?`<img src="${asset(f.path)}" alt="Capture v2 动态帧">`:'';$('frames').innerHTML=r.frames.map((x,i)=>`<button class="${i===frame?'active':''}" data-i="${i}"><img src="${asset(x.path)}"><span>${Number(x.time_seconds).toFixed(3)}s</span></button>`).join('');document.querySelectorAll('#frames button').forEach(b=>b.onclick=()=>{stop();mode='frames';frame=Number(b.dataset.i);renderViewer()});$('timeline').max=Math.max(0,r.frames.length-1);$('timeline').value=frame;$('time').textContent=mode==='webgl'?'WebGL':`${frame+1}/${r.frames.length}`}
function toggleElement(value){let values=selectedElements();if(value==='none')values=values.includes('none')?[]:['none'];else{values=values.filter(x=>x!=='none');values=values.includes(value)?values.filter(x=>x!==value):[...values,value]}pendingElements=values;pendingElementsDirty=true;pendingExclusion=null;pendingExclusionDirty=true;renderReview()}
function renderReview(){let r=cur(),saved=savedRecord(r),elements=selectedElements(),type=selectedType(),exclusion=selectedExclusion(),elementOptions=dimensionOptions(r,'effect_element'),typeOptions=dimensionOptions(r,'effect_type');$('meta').innerHTML=`<div><b>AI特效元素</b>${esc(r.ai_effect_elements_cn.join('、'))}</div><div><b>AI特效类型</b>${esc(r.ai_effect_type_cn)}</div><div><b>AI颜色</b>${esc(r.ai_summary_cn)}</div><div><b>AI审美状态</b>专业资料教师训练中，本页不需要人工评价审美</div><div><b>证据</b>Capture v2 · ${r.frames.length} 帧</div>`;$('elementOptions').innerHTML=elementOptions.map(x=>`<button type="button" class="element-chip ${elements.includes(x.value)?'selected':''}" data-value="${esc(x.value)}">${esc(x.label)}</button>`).join('');document.querySelectorAll('#elementOptions button').forEach(b=>b.onclick=()=>toggleElement(b.dataset.value));$('effectType').innerHTML=typeOptions.map(x=>`<option value="${esc(x.value)}" ${x.value===type?'selected':''}>${esc(x.label)}</option>`).join('');$('effectType').disabled=Boolean(exclusion);$('effectType').onchange=e=>{pendingType=e.target.value;pendingTypeDirty=true;pendingExclusion=null;pendingExclusionDirty=true;renderReview()};$('unable').className=exclusion==='无法判断'?'selected':'';$('notPlayable').className=exclusion==='无法播放'?'selected':'';$('unable').onclick=()=>{pendingExclusion=exclusion==='无法判断'?null:'无法判断';pendingExclusionDirty=true;renderReview()};$('notPlayable').onclick=()=>{pendingExclusion=exclusion==='无法播放'?null:'无法播放';pendingExclusionDirty=true;renderReview()};$('normal').onclick=()=>{pendingExclusion=null;pendingExclusionDirty=true;renderReview()};$('addElement').onclick=()=>addSemanticOption('effect_element');$('addType').onclick=()=>addSemanticOption('effect_type');$('customElement').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();addSemanticOption('effect_element')}};$('customType').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();addSemanticOption('effect_type')}};let elementLabels=elements.map(v=>elementOptions.find(x=>x.value===v)?.label||v),typeLabel=typeOptions.find(x=>x.value===type)?.label||'其他';$('selectionSummary').textContent=exclusion==='无法播放'?'已选择：无法播放':exclusion==='无法判断'?'已选择：无法判断':`元素：${elementLabels.join('、')||'未选择'}；类型：${typeLabel}`;$('confirm').disabled=(!elements.length||!type)&&!exclusion;$('confirm').onclick=confirmSelection;$('notes').value=selectedNotes();$('notes').oninput=()=>{pendingNotes=$('notes').value;pendingNotesDirty=true;$('status').textContent='待确认'};$('status').textContent=(pendingElementsDirty||pendingTypeDirty||pendingExclusionDirty||pendingNotesDirty)?'待确认':saved?'已保存':'未评价'}
function render(){renderQueue();renderViewer();renderReview();$('batch').textContent=batch.batch_id;$('progress').textContent=`${Object.keys(store).length}/${batch.records.length}`}
function stop(){if(timer){clearTimeout(timer);timer=null;$('play').textContent='▶'}}function tick(){let frames=cur().frames,next=(frame+1)%frames.length,delay=Math.max(50,Math.min(500,(frames[next].time_seconds-frames[frame].time_seconds)*1000||100));frame=next;renderViewer();timer=setTimeout(tick,delay)}
async function confirmSelection(){let r=cur(),exclusion=selectedExclusion(),payload={sample_id:r.sample_id,notes:selectedNotes()};if(exclusion)payload.exclusion_action=exclusion;else{payload.effect_elements=selectedElements();payload.effect_type=selectedType()}$('confirm').disabled=true;let response=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),data=await response.json();if(!response.ok){$('status').className='status error';$('status').textContent=data.error;$('confirm').disabled=false;return}$('status').className='status';store[r.sample_id]={latest:data.record};resetPending();let next=batch.records.findIndex((x,i)=>i>index&&!store[x.sample_id]);if(next>=0){index=next;frame=cur().peak_frame_index||0}render()}
async function addSemanticOption(dimension){let input=$(dimension==='effect_element'?'customElement':'customType'),label=input.value.trim();if(!label){$('status').className='status error';$('status').textContent='请输入新的标签名称';return}let response=await fetch('/api/semantic-options',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label,dimension})}),data=await response.json();if(!response.ok){$('status').className='status error';$('status').textContent=data.error;return}customSemanticOptions=data.store.options||[];if(dimension==='effect_element'){let values=selectedElements().filter(x=>x!=='none');pendingElements=values.includes(data.option.value)?values:[...values,data.option.value];pendingElementsDirty=true}else{pendingType=data.option.value;pendingTypeDirty=true}pendingExclusion=null;pendingExclusionDirty=true;input.value='';renderReview();$('status').className='status';$('status').textContent=data.created?'已新增并选中':'已选中现有标签'}
$('play').onclick=()=>{if(timer)stop();else{$('play').textContent='■';tick()}};$('timeline').oninput=e=>{stop();frame=Number(e.target.value);renderViewer()};$('framesMode').onclick=()=>{stop();mode='frames';renderViewer()};$('webglMode').onclick=()=>{stop();mode='webgl';renderViewer()};Promise.all([fetch('/api/batch').then(r=>r.json()),fetch('/api/feedback').then(r=>r.json()),fetch('/api/semantic-options').then(r=>r.json())]).then(([b,s,o])=>{batch=b;store=s.records||{};customSemanticOptions=o.options||[];let first=batch.records.findIndex(r=>!store[r.sample_id]);if(first>=0)index=first;frame=cur().peak_frame_index||0;render()});'''


def _build_semantic_review_html() -> str:
    html = HTML.replace(
        '<div class="actions" id="actions"></div><div class="selection-summary" id="selectionSummary"></div><div class="confirm-row"><button id="confirm" class="confirm" disabled>确认本条</button><button id="clear" class="clear">清除选择</button></div>',
        '<label>特效元素（可多选）</label><div class="element-options" id="elementOptions"></div><div class="custom-type-row"><input id="customElement" type="text" maxlength="24" placeholder="新的特效元素"><button id="addElement" type="button">新增元素</button></div><label for="effectType">特效类型（主要表现形态）</label><select id="effectType"></select><div class="custom-type-row"><input id="customType" type="text" maxlength="24" placeholder="新的特效类型"><button id="addType" type="button">新增类型</button></div><div class="semantic-actions"><button id="normal">按元素和类型判断</button><button id="unable">无法判断</button><button id="notPlayable">无法播放</button></div><div class="selection-summary" id="selectionSummary"></div><div class="confirm-row"><button id="confirm" class="confirm" disabled>确认本条</button></div>'
    )
    html = html.replace(
        "textarea{width:100%",
        "select{width:100%;background:#101417;border:1px solid var(--line);color:var(--text);padding:8px}.element-options{display:flex;flex-wrap:wrap;gap:6px}.element-options button{border:1px solid var(--line);background:#222a30;color:var(--text);padding:6px 9px}.element-options button.selected{border-color:var(--green);background:#214c40}.custom-type-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px;margin-top:7px}.custom-type-row input{min-width:0;background:#101417;border:1px solid var(--line);color:var(--text);padding:8px}.custom-type-row button{border:1px solid var(--cyan);background:#20353a;color:var(--text);padding:6px 12px}.semantic-actions{display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:6px;margin-top:8px}.semantic-actions button{min-height:36px;border:1px solid var(--line);background:#222a30;color:var(--text);padding:6px}.semantic-actions button.selected{border-color:var(--yellow);background:#423920}textarea{width:100%"
    )
    start = html.index("<script>\nlet batch,store={}")
    end = html.index("</script></body></html>", start)
    return html[:start] + "<script>\n" + _SEMANTIC_REVIEW_SCRIPT + "\n</script></body></html>" + html[end + len("</script></body></html>"):]


SEMANTIC_HTML = _build_semantic_review_html()


class ReviewHandler(BaseHTTPRequestHandler):
    root = Path(".")
    repo = _repo_root()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            batch = _read_json(self.root / "review_batch.json")
            body = SEMANTIC_HTML if batch.get("review_mode") == "semantic_function_only" else HTML
            self._send(200, "text/html; charset=utf-8", body.encode("utf-8"))
        elif path == "/api/batch":
            self._json(_read_json(self.root / "review_batch.json"))
        elif path == "/api/feedback":
            self._json(_read_json(self.root / "feedback_store.json"))
        elif path == "/api/semantic-options":
            self._json(_semantic_option_store(self.root))
        elif path.startswith("/asset/"):
            asset = (self.repo / Path(unquote(path[7:]))).resolve()
            if asset.is_file() and asset.is_relative_to(self.repo):
                content_type = "image/png" if asset.suffix.lower() == ".png" else "image/jpeg"
                self._send(200, content_type, asset.read_bytes())
            else:
                self._json({"error": "asset not found"}, 404)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/feedback", "/api/semantic-options"}:
            self._json({"error": "not found"}, 404)
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            if path == "/api/semantic-options":
                result = add_custom_semantic_option(self.root, payload.get("label"), str(payload.get("dimension") or ""))
                self._json({"ok": True, **result})
            else:
                self._json({"ok": True, "record": save_feedback(self.root, payload)})
        except (ValueError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, 400)

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: dict[str, Any], code: int = 200) -> None:
        self._send(code, "application/json; charset=utf-8", json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def log_message(self, *_: object) -> None:
        pass


def serve(root: Path, port: int) -> None:
    ReviewHandler.root = root.resolve()
    ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler).serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, serve and finalize a sparse Prefab active-review queue.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--active-root", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--batch-id", required=True)
    build.add_argument("--webgl-catalog", type=Path)
    build.add_argument("--capture-override", action="append", default=[], metavar="PREFAB=MANIFEST", help="Use another verified Capture v2 manifest for a matching Prefab path.")
    build.add_argument("--judge-predictions", type=Path, help="Attach experimental Aesthetic Judge scores and confidence to the AI draft.")
    build.add_argument("--review-mode", choices=["aesthetic_correction", "semantic_function_only"], default="semantic_function_only")
    build.add_argument("--carry-feedback-root", type=Path, help="Carry compatible submitted feedback from an older immutable review batch.")
    server = commands.add_parser("serve")
    server.add_argument("--root", type=Path, required=True)
    server.add_argument("--port", type=int, default=8792)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(args.root, args.port)
        return 0
    try:
        if args.command == "build":
            overrides = {}
            for value in args.capture_override:
                prefab_path, separator, manifest_path = value.partition("=")
                if not separator or not prefab_path.strip() or not manifest_path.strip():
                    raise ValueError("capture override must use PREFAB=MANIFEST")
                overrides[prefab_path.replace("\\", "/")] = Path(manifest_path)
            paths = build_review_batch(args.active_root, args.output_root, args.batch_id, args.webgl_catalog, overrides, args.judge_predictions, args.review_mode, args.carry_feedback_root)
        else:
            paths = finalize_feedback(args.root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
