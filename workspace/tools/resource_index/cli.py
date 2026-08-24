"""Command-line interface for the local VFX resource index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import ScanConfig
from .scanner import scan_resources
from .store import ResourceIndexStore


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_root() -> Path:
    return repository_root() / "resource"


def _default_output() -> Path:
    return repository_root() / "workspace" / "data" / "resource_index"


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, default=_default_output())
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--limit", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index and query local VFX resources.")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="Scan resources incrementally.")
    scan.add_argument("--root", type=Path, default=_default_root())
    scan.add_argument("--output", type=Path, default=_default_output())
    scan.add_argument("--json", action="store_true", dest="as_json")
    scan.add_argument("--no-thumbnails", action="store_true")
    scan.add_argument("--force-hash", action="store_true")

    for name in ("stats", "query", "duplicates"):
        command = commands.add_parser(name)
        _add_common(command)
    query = commands.choices["query"]
    query.add_argument("--type", dest="asset_type")
    query.add_argument("--tag")
    query.add_argument("--license", dest="license_status")
    query.add_argument("--min-width", type=int)
    query.add_argument("--min-height", type=int)
    return parser


def _record_payload(record):
    payload = record.to_dict()
    payload["status"] = getattr(record, "status", "present")
    return payload


def _print(value, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and "relative_path" in item:
                print(item["relative_path"])
            else:
                print(json.dumps(item, ensure_ascii=False, sort_keys=True))
    elif isinstance(value, dict):
        for key, item in value.items():
            print(f"{key}: {item}")
    else:
        print(value)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.resolve()
    try:
        if args.command == "scan":
            result = scan_resources(ScanConfig(
                root=args.root,
                output_dir=output,
                create_thumbnails=not args.no_thumbnails,
                force_hash=args.force_hash,
            ))
            _print(result, args.as_json)
            return 0

        store = ResourceIndexStore(output / "assets.sqlite3")
        try:
            if args.command == "stats":
                value = store.stats()
            elif args.command == "query":
                value = [_record_payload(record) for record in store.query(
                    asset_type=args.asset_type, tag=args.tag,
                    license_status=args.license_status, min_width=args.min_width,
                    min_height=args.min_height, limit=args.limit,
                )]
            else:
                value = store.duplicates(limit=args.limit)
        finally:
            store.close()
        _print(value, args.as_json)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
