from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import build_all, build_sample, query_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index FBX/OBJ geometry with Blender previews.")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("build-sample", help="Build a bounded, resumable sample.")
    sample.add_argument("--root", type=Path, default=Path("resource"))
    sample.add_argument("--output", type=Path, default=Path("workspace/data/model_index"))
    sample.add_argument("--limit", type=int, default=5)
    sample.add_argument("--blender", default="blender")
    sample.add_argument("--resume", action="store_true")
    sample.add_argument("--json", action="store_true", dest="as_json")

    full = commands.add_parser("build-all", help="Build the full resumable model index sequentially.")
    full.add_argument("--root", type=Path, default=Path("resource"))
    full.add_argument("--output", type=Path, default=Path("workspace/data/model_index/full"))
    full.add_argument("--batch-size", type=int)
    full.add_argument("--limit", type=int, help="Limit discovery for acceptance tests.")
    full.add_argument("--blender", default="blender")
    full.add_argument("--timeout", type=int, default=300)
    full.add_argument("--resume", action="store_true")
    full.add_argument("--json", action="store_true", dest="as_json")

    query = commands.add_parser("query", help="Filter model metadata JSONL.")
    query.add_argument("--metadata", type=Path, default=Path("workspace/data/model_index/full/metadata.jsonl"))
    query.add_argument("--type", dest="asset_type", choices=("fbx", "obj"))
    query.add_argument("--tag")
    query.add_argument("--min-vertices", type=int)
    query.add_argument("--max-vertices", type=int)
    query.add_argument("--min-triangles", type=int)
    query.add_argument("--max-triangles", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build-sample":
        result = build_sample(args.root, args.output, args.limit, args.blender, args.resume)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.as_json else result)
    elif args.command == "build-all":
        result = build_all(args.root, args.output, args.batch_size, args.blender, args.resume,
                           args.timeout, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.as_json else result)
    else:
        rows = query_metadata(args.metadata, asset_type=args.asset_type, tag=args.tag,
                              min_vertices=args.min_vertices, max_vertices=args.max_vertices,
                              min_triangles=args.min_triangles, max_triangles=args.max_triangles)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
