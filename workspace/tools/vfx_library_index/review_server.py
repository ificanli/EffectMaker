from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .observations import append_observation


_LABELS = ("start", "quarter", "middle", "three-quarter", "end")


def load_review_queue(path: Path) -> dict:
    queue = json.loads(path.read_text(encoding="utf-8"))
    if queue.get("status") != "review-queue" or queue.get("reference_only") is not True:
        raise ValueError("review queue must be a reference-only review-queue report")
    return queue


def build_server_manifest(queue: dict, frame_root: Path, review: dict | None = None) -> dict:
    frame_root = frame_root.resolve()
    output_by_key = {
        (item.get("relative_path"), item.get("label")): item.get("output")
        for item in (review or {}).get("results", [])
        if item.get("status") == "ok" and item.get("output")
    }
    samples = []
    for item in queue.get("items", []):
        frames = []
        for label in _LABELS:
            mapped = output_by_key.get((item.get("relative_path"), label))
            frame = (frame_root / Path(mapped).name).resolve() if mapped else (frame_root / f"{item.get('sha256', '')[:12]}_{label}.png").resolve()
            frames.append({"label": label, "url": f"/frames/{frame.name}", "available": frame_root in frame.parents and frame.is_file() and frame.stat().st_size > 0})
        samples.append({"relative_path": item.get("relative_path"), "sha256": item.get("sha256"), "theme_candidate": item.get("theme_candidate"), "frames": frames})
    return {"status": "review-queue", "reference_only": True, "disclaimer": queue.get("disclaimer", ""), "samples": samples}


def serve_review_server(queue_path: Path, frame_root: Path, observation_path: Path, review_path: Path | None = None, host: str = "127.0.0.1", port: int = 8765) -> None:
    queue = load_review_queue(queue_path)
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path else None
    manifest = build_server_manifest(queue, frame_root.resolve(), review)
    html = (Path(__file__).parent / "static" / "review.html").read_bytes()
    frame_root = frame_root.resolve()
    observation_path = observation_path.resolve()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(200, html, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/manifest":
                self._send(200, json.dumps(manifest, ensure_ascii=False).encode(), "application/json")
                return
            if parsed.path == "/health":
                self._send(200, b"ok", "text/plain; charset=utf-8")
                return
            if parsed.path.startswith("/frames/"):
                requested = (frame_root / unquote(parsed.path.removeprefix("/frames/"))).resolve()
                if frame_root not in requested.parents or requested.suffix.lower() != ".png" or not requested.is_file():
                    self._send(404, b"not found", "text/plain; charset=utf-8")
                    return
                self._send(200, requested.read_bytes(), "image/png")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/observations":
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                saved = append_observation(observation_path, payload, queue)
            except (ValueError, json.JSONDecodeError) as error:
                self._send(400, json.dumps({"error": str(error)}).encode(), "application/json")
                return
            self._send(200, json.dumps(saved, ensure_ascii=False).encode(), "application/json")

        def log_message(self, format: str, *args: object) -> None:
            return

    ThreadingHTTPServer((host, port), Handler).serve_forever()
