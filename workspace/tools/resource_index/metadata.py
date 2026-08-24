"""Hash and image metadata helpers for the local VFX resource index."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image


_IMAGE_FIELDS = {
    "width": None,
    "height": None,
    "mode": None,
    "channels": None,
    "frame_count": None,
    "error": None,
}


def sha256_file(path: Path, chunk_size: int = 1048576) -> str:
    """Return a file's SHA-256 digest without reading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_image_metadata(path: Path) -> dict[str, object]:
    """Read image properties, recording decode failures in the result."""
    metadata: dict[str, object] = dict(_IMAGE_FIELDS)
    try:
        with Image.open(path) as image:
            metadata.update(
                width=image.width,
                height=image.height,
                mode=image.mode,
                channels=len(image.getbands()),
                frame_count=getattr(image, "n_frames", 1),
            )
    except Exception as exc:
        metadata["error"] = f"{type(exc).__name__}: {exc}"
    return metadata


def extract_metadata(path: Path, asset_type: str) -> dict[str, object]:
    """Return a hash and image metadata appropriate for an asset category."""
    result: dict[str, Any] = {
        "sha256": None,
        **_IMAGE_FIELDS,
    }
    try:
        result["sha256"] = sha256_file(path)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    if asset_type == "texture":
        result.update(read_image_metadata(path))
    return result
