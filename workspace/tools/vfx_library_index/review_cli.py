from __future__ import annotations

import argparse
import json
from pathlib import Path

from .review import run_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automatically extract and verify VFX.library evidence frames.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=64)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.page_size <= 0:
        raise SystemExit("--page-size must be greater than zero")
    report = run_review(
        args.source_root,
        args.manifest,
        args.evidence_manifest,
        args.output,
        page_size=args.page_size,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in {"ready", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
