from __future__ import annotations

import argparse
from pathlib import Path

from .review_server import serve_review_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the local VFX continuous-frame review UI.")
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve_review_server(args.queue, args.frames, args.observations, args.review, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
