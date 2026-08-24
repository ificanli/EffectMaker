"""Local VFX resource index data models."""

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScanConfig:
    """Immutable settings for a resource scan."""

    root: Path
    output_dir: Path = Path("workspace/data/resource_index")
    thumbnail_size: int = 256
    follow_symlinks: bool = False
    create_thumbnails: bool = True
    force_hash: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {field.name: _json_value(getattr(self, field.name)) for field in fields(self)}


@dataclass
class AssetRecord:
    """A serializable description of one resource file."""

    asset_id: str
    relative_path: str
    asset_type: str
    extension: str
    size_bytes: int
    modified_time: float
    sha256: str | None = None
    tags: list[str] = field(default_factory=list)
    license_status: str = "unknown"
    license_hints: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    mode: str | None = None
    channels: int | None = None
    thumbnail_status: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {field.name: _json_value(getattr(self, field.name)) for field in fields(self)}


def _json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value
