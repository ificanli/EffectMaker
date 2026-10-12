"""MCP tool for returning a local image as a native image block."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import Image

from registry import mcp_for_unity_tool


SUPPORTED_FORMATS = {
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".webp": "webp",
    ".gif": "gif",
    ".bmp": "bmp",
}


@mcp_for_unity_tool(
    name="read_local_image",
    description=(
        "Read a local PNG/JPEG/WebP/GIF/BMP file and return it as a native MCP image attachment. "
        "The path must point to an existing image file."
    ),
)
def read_local_image(
    path: Annotated[str, "Absolute or relative path to a local image file"]
) -> Image:
    """Return a local image through FastMCP's native Image result type."""
    image_path = Path(path).expanduser()
    if not image_path.is_file():
        raise ValueError(f"image file not found: {image_path}")
    suffix = image_path.suffix.lower()
    image_format = SUPPORTED_FORMATS.get(suffix)
    if image_format is None:
        raise ValueError(f"unsupported image type: {suffix or '<none>'}")
    return Image(data=image_path.read_bytes(), format=image_format)
