from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .evidence import select_evidence_points

REFERENCE_DISCLAIMER = (
    "Reference material only; it is not an aesthetic quality standard, a style target, "
    "or proof of a correct implementation."
)


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def select_seed_records(
    records: Iterable[dict],
    assignments: Iterable[dict],
    themes: tuple[str, ...],
    per_theme: int,
) -> list[dict]:
    record_by_path = {item["relative_path"]: item for item in records}
    selected: list[dict] = []
    seen_sha: set[str] = set()
    for theme in themes:
        count = 0
        for assignment in assignments:
            if assignment.get("theme") != theme:
                continue
            relative_path = assignment["relative_path"]
            record = record_by_path.get(relative_path)
            if record is None:
                continue
            sha256 = record.get("sha256")
            if not sha256 or sha256 in seen_sha:
                continue
            selected.append({**record, "theme": theme})
            seen_sha.add(sha256)
            count += 1
            if count >= per_theme:
                break
    return selected


def build_visual_package(
    source_root: Path,
    manifest_path: Path,
    assignments_path: Path,
    output: Path,
    themes: tuple[str, ...] = ("fire", "lightning", "water", "slash", "smoke", "energy"),
    per_theme: int = 5,
) -> dict:
    del source_root
    output.mkdir(parents=True, exist_ok=True)
    records = _load_jsonl(manifest_path)
    assignments = _load_jsonl(assignments_path)
    seeds = select_seed_records(records, assignments, themes, per_theme)
    samples: list[dict] = []
    evidence_point_count = 0
    for record in seeds:
        points = select_evidence_points(
            record.get("duration_seconds"),
            record.get("frame_count"),
            record["media_type"],
        )
        if record.get("duration_seconds") and record["duration_seconds"] >= 0.3:
            duration = float(record["duration_seconds"])
            end = max(0.0, duration - min(0.05, duration / 10))
            quarter = round(duration / 4, 3)
            middle = round(duration / 2, 3)
            three_quarter = round(duration * 3 / 4, 3)
            points = [
                ("start", 0.0),
                ("quarter", quarter),
                ("middle", middle),
                ("three-quarter", three_quarter),
                ("end", round(end, 3)),
            ]
        evidence = [
            {
                "relative_path": record["relative_path"],
                "sha256": record.get("sha256"),
                "theme_candidate": record["theme"],
                "label": label,
                "second": second,
                "evidence_level": "title-keyword-candidate",
                "observation_status": "unreviewed",
            }
            for label, second in points
        ]
        evidence_point_count += len(evidence)
        samples.append({
            "relative_path": record["relative_path"],
            "sha256": record.get("sha256"),
            "theme_candidate": record["theme"],
            "media_type": record["media_type"],
            "duration_seconds": record.get("duration_seconds"),
            "evidence": evidence,
        })
    report = {
        "status": "candidate-package",
        "reference_only": True,
        "disclaimer": REFERENCE_DISCLAIMER,
        "themes": list(themes),
        "per_theme": per_theme,
        "sample_count": len(samples),
        "evidence_point_count": evidence_point_count,
        "samples": samples,
        "limitations": [
            "Theme labels originate from filename keyword candidates and require visual review.",
            "This package does not rank quality, style, originality, or aesthetic value.",
            "This package does not infer Unity implementation parameters or licensing rights.",
        ],
    }
    (output / "visual_package.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    evidence_lines = [
        json.dumps(point, ensure_ascii=False, sort_keys=True)
        for sample in samples
        for point in sample["evidence"]
    ]
    (output / "evidence_manifest.jsonl").write_text(
        "\n".join(evidence_lines) + ("\n" if evidence_lines else ""),
        encoding="utf-8",
    )
    return report
