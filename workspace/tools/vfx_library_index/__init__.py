"""Read-only indexer for GIF and video VFX references."""

from .models import ScanSummary
from .scanner import normalize_download_name, scan_library

__all__ = ["ScanSummary", "normalize_download_name", "scan_library"]
