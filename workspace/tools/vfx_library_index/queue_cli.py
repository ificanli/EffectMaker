from __future__ import annotations

import argparse
import json
from pathlib import Path

from .queue import build_review_queue


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a reference-only VFX visual review queue.")
    parser.add_argument("--triage", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    triage = json.loads(args.triage.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    report = build_review_queue(triage, review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"status={report['status']} samples={report['sample_count']} "
        f"themes={report['theme_count']} reference_only={report['reference_only']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
