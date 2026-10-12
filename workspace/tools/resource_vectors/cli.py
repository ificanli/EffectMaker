"""CLI for the local VFX image-vector prototype."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .encoder import ModelUnavailableError, TransformersClipEncoder
from .index import build_full_vector_index, build_vector_index, load_vector_index, search_vectors
from .query import normalize_text_query, resolve_query_image
from .sample import select_sample

DEFAULT_MODEL = "openai/clip-vit-base-patch32"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _defaults() -> tuple[Path, Path, Path]:
    root = repository_root()
    return (
        root / "resource",
        root / "workspace" / "data" / "resource_index",
        root / "workspace" / "data" / "resource_vectors" / "prototype",
    )


def _encoder_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--allow-model-download", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    resource, phase_one, output = _defaults()
    parser = argparse.ArgumentParser(description="Search local VFX textures with CLIP vectors.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-sample", help="Select and encode a deterministic sample.")
    build.add_argument("--root", type=Path, default=resource)
    build.add_argument("--source-index", type=Path, default=phase_one)
    build.add_argument("--output", type=Path, default=output)
    build.add_argument("--limit", type=int, default=64)
    build.add_argument("--json", action="store_true", dest="as_json")
    _encoder_arguments(build)

    full = commands.add_parser("build-all", help="Build a resumable full texture index.")
    full.add_argument("--root", type=Path, default=resource)
    full.add_argument("--source-index", type=Path, default=phase_one)
    full.add_argument("--output", type=Path, default=repository_root() / "workspace" / "data" / "resource_vectors" / "full")
    full.add_argument("--batch-size", type=int, default=32)
    full.add_argument("--limit", type=int)
    full.add_argument("--json", action="store_true", dest="as_json")
    _encoder_arguments(full)

    text = commands.add_parser("search-text", help="Search with natural language.")
    text.add_argument("query")
    text.add_argument("--output", type=Path, default=output)
    text.add_argument("--limit", type=int, default=10)
    text.add_argument("--json", action="store_true", dest="as_json")
    _encoder_arguments(text)

    image = commands.add_parser("search-image", help="Search with a local image.")
    image.add_argument("image", type=Path)
    image.add_argument("--root", type=Path, default=resource)
    image.add_argument("--output", type=Path, default=output)
    image.add_argument("--limit", type=int, default=10)
    image.add_argument("--json", action="store_true", dest="as_json")
    _encoder_arguments(image)
    return parser


def _print(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    elif isinstance(value, list):
        for row in value:
            print(f"{row['score']:.6f}\t{row['relative_path']}")
    elif isinstance(value, dict):
        for key, item in value.items():
            print(f"{key}: {item}")


def _make_encoder(args: argparse.Namespace) -> TransformersClipEncoder:
    return TransformersClipEncoder(
        args.model, revision=args.revision, allow_download=args.allow_model_download
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build-sample":
            source = args.source_index
            sample = select_sample(
                args.root,
                limit=args.limit,
                sqlite_path=source / "assets.sqlite3",
                jsonl_path=source / "assets.jsonl",
            )
            args.output.mkdir(parents=True, exist_ok=True)
            sample_path = args.output / "sample.jsonl"
            with sample_path.open("w", encoding="utf-8", newline="\n") as stream:
                for row in sample:
                    stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            encoder = _make_encoder(args)
            summary = build_vector_index(sample, args.root, args.output, encoder)
            _print(summary, args.as_json)
            return 0

        if args.command == "build-all":
            source = args.source_index
            records = select_sample(args.root, limit=args.limit or 2**31 - 1, sqlite_path=source / "assets.sqlite3", jsonl_path=source / "assets.jsonl")
            encoder = _make_encoder(args)
            summary = build_full_vector_index(records, args.root, args.output, encoder, batch_size=args.batch_size)
            _print(summary, args.as_json)
            return 0

        vectors, metadata, manifest = load_vector_index(args.output)
        if args.model == DEFAULT_MODEL:
            args.model = str(manifest["model_id"])
        if args.revision == "main":
            args.revision = str(manifest["revision"])
        encoder = _make_encoder(args)
        if args.command == "search-text":
            query = encoder.encode_text(normalize_text_query(args.query))
        else:
            query_path = resolve_query_image(args.image, args.root)
            query = encoder.encode_images([query_path])[0]
        _print(search_vectors(query, vectors, metadata, limit=args.limit), args.as_json)
        return 0
    except ModelUnavailableError as error:
        print(f"blocked: {error}", file=sys.stderr)
        return 3
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
