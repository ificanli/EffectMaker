"""Local VFX resource index package."""

from .classify import classify_asset, derive_tags, infer_license
from .models import AssetRecord, ScanConfig

__all__ = [
    "AssetRecord",
    "ScanConfig",
    "classify_asset",
    "derive_tags",
    "infer_license",
]
