from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ScanSummary:
    source_id: str
    input_file_count: int
    supported_media_count: int
    skipped_count: int
    byte_total: int
    content_duplicate_group_count: int
    normalized_name_duplicate_group_count: int
    error_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
