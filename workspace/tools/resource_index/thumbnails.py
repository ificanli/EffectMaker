"""Thumbnail generation for immutable local VFX resources."""

from pathlib import Path

from PIL import Image


_CHECKER_SIZE = 16
_CHECKER_LIGHT = (224, 224, 224)
_CHECKER_DARK = (192, 192, 192)


def thumbnail_relative_path(asset_id: str) -> Path:
    """Return the deterministic output path for an asset thumbnail."""
    if not asset_id:
        raise ValueError("asset_id must not be empty")
    if Path(asset_id).name != asset_id or Path(asset_id).is_absolute():
        raise ValueError("asset_id must be a single safe path component")
    return Path("thumbnails") / asset_id[:2] / f"{asset_id}.png"


def create_thumbnail(
    source: Path,
    destination_root: Path,
    asset_id: str,
    size: int = 256,
) -> tuple[str | None, str | None]:
    """Create an RGB PNG thumbnail without modifying the source tree."""
    try:
        if size <= 0:
            raise ValueError("size must be positive")
        relative_path = thumbnail_relative_path(asset_id)
        source_path = Path(source).resolve()
        destination_path = Path(destination_root).resolve()
        output = destination_path / relative_path
        output_path = output.resolve()
        if (
            source_path == destination_path
            or source_path in destination_path.parents
            or destination_path in source_path.parents
            or source_path.parent == destination_path
            or source_path.parent in destination_path.parents
        ):
            raise ValueError("source and thumbnail destination must not overlap")
        _validate_output_paths(source_path, destination_path, output_path)
        with Image.open(source_path) as image:
            image.load()
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            thumbnail = _to_rgb_on_checkerboard(image)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            thumbnail.save(output_path, format="PNG")
            thumbnail.close()
        return relative_path.as_posix(), None
    except Image.DecompressionBombError as error:
        return None, str(error)
    except (OSError, ValueError, SyntaxError) as error:
        return None, str(error)


def _validate_output_paths(source_path: Path, destination_path: Path, output_path: Path) -> None:
    """Reject resolved thumbnail paths that overlap the immutable source tree."""
    del destination_path
    source_parent = source_path.parent
    if output_path == source_path or output_path == source_parent or source_parent in output_path.parents:
        raise ValueError("thumbnail output must not overlap the source directory")


def _to_rgb_on_checkerboard(image: Image.Image) -> Image.Image:
    """Flatten transparency onto a neutral checkerboard for inspection."""
    if image.mode not in ("RGBA", "LA", "P") and "transparency" not in image.info:
        return image.convert("RGB")

    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size)
    pixels = background.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            pixels[x, y] = (
                _CHECKER_LIGHT
                if (x // _CHECKER_SIZE + y // _CHECKER_SIZE) % 2 == 0
                else _CHECKER_DARK
            )
    background.paste(rgba, mask=rgba.getchannel("A"))
    rgba.close()
    return background
