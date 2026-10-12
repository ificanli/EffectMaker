"""Fuse slash narrow-axis rankings without mixing uncalibrated raw scores."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "vfx_professional_slash_multi_axis_ranking.v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def fuse_rankings(ranking_paths: dict[str, Path], output_path: Path) -> Path:
    if len(ranking_paths) < 2:
        raise ValueError("at least two axis rankings are required")
    rankings = {axis: _read(path.resolve()) for axis, path in ranking_paths.items()}
    candidate_sets = {axis: {row["candidate_id"] for row in data.get("ranking") or []} for axis, data in rankings.items()}
    first = next(iter(candidate_sets.values()))
    if not first or any(values != first for values in candidate_sets.values()):
        raise ValueError("all axis rankings must contain the same non-empty candidate set")
    rank_maps = {axis: {row["candidate_id"]: index for index, row in enumerate(data["ranking"])} for axis, data in rankings.items()}
    row_maps = {axis: {row["candidate_id"]: row for row in data["ranking"]} for axis, data in rankings.items()}
    count = len(first)
    records = []
    for candidate_id in sorted(first):
        axis_results = {}
        eligible = True
        normalized_ranks = []
        for axis in sorted(rankings):
            row = row_maps[axis][candidate_id]
            rank = rank_maps[axis][candidate_id] + 1
            in_distribution = bool((row.get("distribution") or {}).get("in_distribution"))
            eligible = eligible and in_distribution
            normalized = 1.0 if count == 1 else 1.0 - (rank - 1) / (count - 1)
            normalized_ranks.append(normalized)
            axis_results[axis] = {"rank": rank, "normalized_rank_score": normalized, "in_distribution": in_distribution}
        records.append({"candidate_id": candidate_id, "all_axes_in_distribution": eligible, "rank_fusion_score": sum(normalized_ranks) / len(normalized_ranks), "axis_results": axis_results})
    records.sort(key=lambda row: (not row["all_axes_in_distribution"], -row["rank_fusion_score"], row["candidate_id"]))
    eligible_count = sum(row["all_axes_in_distribution"] for row in records)
    return _write(output_path.resolve(), {"schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "axes": sorted(rankings), "candidate_count": len(records), "all_axes_in_distribution_count": eligible_count, "ranking": records, "score_interpretation": "Mean normalized rank across narrow axes; raw model scores are not mixed.", "status": "pass" if eligible_count else "blocked_no_all_axis_candidate"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fuse slash narrow-axis rankings by normalized rank.")
    parser.add_argument("--ranking", action="append", required=True, help="AXIS=path/to/ranking.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        ranking_paths = {}
        for value in args.ranking:
            axis, separator, path = value.partition("=")
            if not separator or not axis.strip() or not path.strip():
                raise ValueError(f"invalid --ranking value: {value}")
            ranking_paths[axis.strip()] = Path(path.strip())
        output = fuse_rankings(ranking_paths, args.output)
    except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, "ranking": output.as_posix()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
