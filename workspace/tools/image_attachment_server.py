"""Return local image files using MCP image content blocks."""

from __future__ import annotations

import base64
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any


SUPPORTED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/bmp",
}


class ImageAttachmentError(ValueError):
    """Raised when a requested image cannot be returned safely."""


def _mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ImageAttachmentError(f"unsupported image type: {path.suffix or '<none>'}")
    return mime_type


def build_image_content(path: Path | str) -> dict[str, str]:
    """Build one MCP image content block from a local image file."""
    image_path = Path(path)
    if not image_path.is_file():
        raise ImageAttachmentError(f"image file not found: {image_path}")

    mime_type = _mime_type(image_path)
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return {"type": "image", "data": data, "mimeType": mime_type}


def read_local_image(path: Path | str) -> dict[str, list[dict[str, str]]]:
    """Return an MCP-compatible tool result containing an image attachment."""
    return {"content": [build_image_content(path)]}


def main() -> int:
    """Read newline-delimited requests from stdin and write JSON results."""
    for line in sys.stdin:
        if not line.strip():
            continue
        request: dict[str, Any] = json.loads(line)
        try:
            result = read_local_image(request["path"])
        except (KeyError, ImageAttachmentError) as exc:
            result = {"error": str(exc)}
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
