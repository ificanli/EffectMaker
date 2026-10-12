"""Build an auditable Controller mutation guidance from Judge and preference evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_VERSION = "vfx_controller_aesthetic_guidance.v1"
SCORE_GOALS = {
    "core_readability": "提高主体可读性",
    "layer_separation": "重新明确 Core / Support / Hit / Residual 职责",
    "rhythm": "重新安排起势、峰值和收束节奏",
    "material": "修复材质、贴图、流动或溶解表现",
    "composition": "修正占屏、空间位置和镜头关系",
    "quality_score": "提高整体质量",
}


class ControllerGuidanceError(ValueError):
    """Raised when guidance input cannot be read safely."""


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ControllerGuidanceError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _id(prompt: str, effect_family: str, judge: dict[str, Any], preference: dict[str, Any]) -> str:
    raw = json.dumps({"prompt": prompt, "effect_family": effect_family, "judge": judge, "preference": preference}, ensure_ascii=False, sort_keys=True)
    return "guidance_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _judge_input(path: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if path is None:
        return {"status": "unavailable", "model_path": None, "candidate_id": None, "predictions": {}}, {}
    payload = _read_json(path.resolve())
    predictions = payload.get("predictions") if isinstance(payload.get("predictions"), list) else []
    selected = predictions[0] if predictions and isinstance(predictions[0], dict) else {}
    return {
        "status": "available" if selected else "not_trained",
        "model_path": str(payload.get("model_path") or path.resolve().as_posix()) if selected else None,
        "candidate_id": str(selected.get("candidate_id") or "") or None,
        "predictions": selected,
    }, selected


def _preference_input(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "unavailable", "model_path": None, "ranking_path": None, "top_candidate_id": None}
    payload = _read_json(path.resolve())
    ranking = payload.get("ranking") if isinstance(payload.get("ranking"), list) else []
    top = ranking[0] if ranking and isinstance(ranking[0], dict) else {}
    return {
        "status": "available" if top else "not_trained",
        "model_path": str(payload.get("model_path") or "") or None,
        "ranking_path": path.resolve().as_posix(),
        "top_candidate_id": str(top.get("candidate_id") or "") or None,
    }


def _feedback_input(paths: list[Path]) -> dict[str, Any]:
    record_ids: list[str] = []
    issues: list[str] = []
    next_mutation: list[str] = []
    for path in paths:
        payload = _read_json(path.resolve())
        records = payload.get("records") if isinstance(payload.get("records"), list) else [payload]
        for record in records:
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("record_id") or record.get("candidate_id") or "")
            if record_id:
                record_ids.append(record_id)
            label = record.get("label") if isinstance(record.get("label"), dict) else record.get("human_label") if isinstance(record.get("human_label"), dict) else record
            if isinstance(label, dict):
                issues.extend(str(value) for value in (label.get("issues") or []) if str(value))
                next_mutation.extend(str(value) for value in (label.get("next_mutation") or []) if str(value))
    return {"status": "available" if record_ids else "unavailable", "record_ids": sorted(set(record_ids)), "issues": sorted(set(issues)), "next_mutation": sorted(set(next_mutation))}


def build_guidance(
    prompt: str,
    effect_family: str,
    style_family: str,
    style_keywords: list[str],
    source_context: dict[str, Any],
    judge_path: Path | None = None,
    preference_path: Path | None = None,
    feedback_paths: list[Path] | None = None,
) -> dict[str, Any]:
    judge, predictions = _judge_input(judge_path)
    preference = _preference_input(preference_path)
    feedback = _feedback_input(feedback_paths or [])
    goals: list[str] = []
    change: list[str] = []
    rationale: list[str] = []
    for task, goal in SCORE_GOALS.items():
        value = predictions.get(task)
        if isinstance(value, (int, float)) and value <= 2.0:
            goals.append(goal)
            change.append(task)
            rationale.append(f"Judge预测 {task}={value}，低于或等于2，需要针对性变异。")
    target_style = style_family if style_family else "unknown"
    predicted_style = str(predictions.get("style_family") or "")
    if target_style != "unknown" and predicted_style and predicted_style != target_style:
        goals.append("修正目标风格匹配")
        change.append("style_profile/material_language")
        rationale.append(f"目标风格为 {target_style}，Judge预测为 {predicted_style}。")
    if feedback["issues"]:
        goals.extend(f"处理人工问题：{issue}" for issue in feedback["issues"])
        change.extend(feedback["issues"])
        rationale.append("人工反馈优先于自动草稿，问题标签被保留为下一轮变异依据。")
    if feedback["next_mutation"]:
        change.extend(feedback["next_mutation"])
        rationale.append("沿用已保存的人工作出的下一轮变异建议。")
    if preference["top_candidate_id"]:
        rationale.append(f"Preference Ranker当前Top候选为 {preference['top_candidate_id']}，仅作为人工复核排序依据。")
    if not goals:
        goals.append("等待更多可见人工评价和偏好比较")
        rationale.append("当前没有足够的Judge或人工问题证据，不能凭空指定修改变量。")
    preserve = ["Prefab依赖闭包", "材质/贴图/Shader真实绑定", "Unity运行证据和人工反馈 provenance"]
    record = {
        "schema_version": SCHEMA_VERSION,
        "guidance_id": _id(prompt, effect_family, judge, preference),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "prompt": prompt,
            "effect_family": effect_family,
            "target_style_profile": {"family": target_style, "keywords": sorted(set(style_keywords))},
            "source_context": source_context,
        },
        "evidence": {"judge": judge, "preference": preference, "human_feedback": feedback},
        "mutation_plan": {
            "goals": sorted(set(goals)),
            "preserve": preserve,
            "change": sorted(set(change)),
            "rationale": sorted(set(rationale)),
            "approval_required": True,
        },
        "training_eligibility": {
            "controller_sft": False,
            "preference_training": False,
            "positive_generation_supervision": False,
            "excluded_reasons": ["guidance_requires_unity_execution_and_human_confirmation"],
        },
        "status": "guidance_only",
    }
    schema = _read_json(_repo_root() / "workspace/data/vfx_generation/schemas/vfx_controller_aesthetic_guidance.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(record), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(value) for value in errors[0].path) or "<root>"
        raise ControllerGuidanceError(f"Controller guidance schema error at {location}: {errors[0].message}")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build auditable VFX Controller aesthetic guidance.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--effect-family", required=True)
    parser.add_argument("--style-family", default="unknown")
    parser.add_argument("--style-keyword", action="append", default=[])
    parser.add_argument("--source-context", type=Path)
    parser.add_argument("--judge-prediction", type=Path)
    parser.add_argument("--preference-ranking", type=Path)
    parser.add_argument("--human-feedback", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        context = _read_json(args.source_context.resolve()) if args.source_context else {}
        record = build_guidance(args.prompt, args.effect_family, args.style_family, args.style_keyword, context, args.judge_prediction, args.preference_ranking, args.human_feedback)
        path = _write_json(args.output.resolve(), record)
    except (ControllerGuidanceError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "path": path.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
