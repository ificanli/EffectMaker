"""CLI for the VFX.library animation-media index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scanner import scan_library


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan a GIF/video VFX reference library.")
    scan = parser.add_subparsers(dest="command", required=True).add_parser("scan")
    scan.add_argument("--root", required=True, type=Path)
    scan.add_argument("--output", required=True, type=Path)
    scan.add_argument("--source-id", required=True)
    scan.add_argument("--no-probe", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = scan_library(args.root, args.output, args.source_id, probe_media=not args.no_probe)
    print(json.dumps(summary.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
