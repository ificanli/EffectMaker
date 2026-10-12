from __future__ import annotations

import json
from pathlib import Path

_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
_SCORE_FIELDS = {"score", "quality_score", "aesthetic_score", "rank", "rating"}


def _evidence_keys(queue: dict) -> set[tuple[str, str]]:
    keys = set()
    for item in queue.get("items", []):
        for label in ("start", "quarter", "middle", "three-quarter", "end"):
            keys.add((item.get("relative_path"), label))
    return keys


def validate_observation(payload: dict, queue: dict) -> dict:
    if _SCORE_FIELDS.intersection(payload):
        raise ValueError("quality and aesthetic scoring fields are not allowed")
    key = (payload.get("relative_path"), payload.get("label"))
    if key not in _evidence_keys(queue):
        raise ValueError("observation evidence is not present in the review queue")
    confidence = payload.get("confidence", "low")
    if confidence not in _ALLOWED_CONFIDENCE:
        raise ValueError("confidence must be low, medium, or high")
    result = {
        "relative_path": payload["relative_path"],
        "sha256": payload.get("sha256"),
        "label": payload["label"],
        "theme_status": payload.get("theme_status", "pending"),
        "borrowable_points": payload.get("borrowable_points", ""),
        "limitations": payload.get("limitations", ""),
        "do_not_use_reason": payload.get("do_not_use_reason", ""),
        "counterexample": payload.get("counterexample", ""),
        "confidence": confidence,
        "reference_only": True,
    }
    return result


def append_observation(path: Path, payload: dict, queue: dict) -> dict:
    result = validate_observation(payload, queue)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result
