from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_BUILD_ROOT = Path("E:/Unity特效人工智能学习/workspace/Builds/WebGL/VfxTrainingPlayer2022")


class VfxWebRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".data": "application/octet-stream",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"[vfx-web] {self.address_string()} - {format % args}")


def resolve_build_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    index_path = root / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(
            f"Unity WebGL build is missing index.html: {index_path}"
        )
    return root


def create_server(
    build_root: str | Path,
    host: str = "127.0.0.1",
    port: int = 8770,
) -> ThreadingHTTPServer:
    root = resolve_build_root(build_root)
    handler = functools.partial(VfxWebRequestHandler, directory=str(root))
    return ThreadingHTTPServer((host, port), handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve the local Unity WebGL VFX Prefab Player build."
    )
    parser.add_argument("--build-root", default=str(DEFAULT_BUILD_ROOT))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        server = create_server(args.build_root, args.host, args.port)
    except (FileNotFoundError, OSError) as error:
        print(f"error: {error}")
        return 2

    url = f"http://{args.host}:{args.port}/"
    print(f"VFX Prefab Player: {url}")
    print(f"Build root: {resolve_build_root(args.build_root)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
