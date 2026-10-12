from __future__ import annotations

import argparse
import json
from pathlib import Path

from .clustering import build_clusters, classify_title


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build conservative filename-based VFX reference clusters.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines()]
    args.output.mkdir(parents=True, exist_ok=True)
    clusters = build_clusters(records)
    (args.output / "clusters.json").write_text(json.dumps(clusters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assignments = []
    for record in sorted(records, key=lambda item: item["relative_path"]):
        assignments.append({
            "media_id": record["media_id"],
            "relative_path": record["relative_path"],
            "sha256": record["sha256"],
            **classify_title(record["relative_path"]),
        })
    (args.output / "assignments.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in assignments), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
