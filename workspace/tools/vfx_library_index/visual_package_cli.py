from __future__ import annotations

import argparse
from pathlib import Path

from .visual_package import build_visual_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a reference-only VFX visual review package.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-theme", type=int, default=5)
    args = parser.parse_args()
    report = build_visual_package(
        args.source_root,
        args.manifest,
        args.assignments,
        args.output,
        per_theme=args.per_theme,
    )
    print(
        f"status={report['status']} samples={report['sample_count']} "
        f"evidence_points={report['evidence_point_count']} reference_only={report['reference_only']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
