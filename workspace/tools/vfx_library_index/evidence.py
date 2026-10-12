from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class EvidencePoint:
    relative_path: str
    label: str
    second: float | None


def select_evidence_points(duration_seconds: float | None, frame_count: int | None, media_type: str) -> list[tuple[str, float | None]]:
    if duration_seconds is not None and duration_seconds > 0:
        end = max(0.0, duration_seconds - min(0.05, duration_seconds / 10))
        if duration_seconds < 0.3:
            return [("representative", round(duration_seconds / 2, 3))]
        return [("start", 0.0), ("middle", round(duration_seconds / 2, 3)), ("end", round(end, 3))]
    if frame_count is not None and frame_count > 0:
        middle = max(0, frame_count // 2)
        return [("representative", float(middle))]
    return [("representative", None)] if media_type == "gif" else []


def write_evidence_manifest(records: Iterable[dict], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for record in records:
        points = select_evidence_points(record.get("duration_seconds"), record.get("frame_count"), record["media_type"])
        for label, second in points:
            lines.append(json.dumps(asdict(EvidencePoint(record["relative_path"], label, second)), ensure_ascii=False, sort_keys=True))
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return output
