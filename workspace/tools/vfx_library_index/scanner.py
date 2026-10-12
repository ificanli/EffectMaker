from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from workspace.tools.media import probe

from .models import ScanSummary

_SUPPORTED = {
    ".gif": "gif",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".avi": "video",
}
_DOWNLOAD_SUFFIX = re.compile(r"\s*\(\d+\)(?=\.[^.]+$)")


def normalize_download_name(name: str) -> str:
    return _DOWNLOAD_SUFFIX.sub("", name)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_fields(payload: dict[str, Any]) -> dict[str, Any]:
    video = payload.get("video") or {}
    return {
        "duration_seconds": payload.get("duration_seconds"),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": video.get("fps"),
        "frame_count": video.get("frame_count"),
        "loop_count": payload.get("loop_count"),
        "media_probe_status": "ok",
    }


def _record(root: Path, path: Path, source_id: str, probe_media: bool) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    media_type = _SUPPORTED[path.suffix.casefold()]
    errors: list[str] = []
    try:
        digest = _sha256(path)
    except OSError as exc:
        digest = None
        errors.append(f"hash: {type(exc).__name__}: {exc}")
    try:
        payload = probe(path) if probe_media and digest is not None else {}
        probe_fields = _probe_fields(payload) if probe_media else {
            "duration_seconds": None,
            "width": None,
            "height": None,
            "fps": None,
            "frame_count": None,
            "loop_count": None,
            "media_probe_status": "skipped",
        }
    except Exception as exc:
        probe_fields = {
            "duration_seconds": None,
            "width": None,
            "height": None,
            "fps": None,
            "frame_count": None,
            "loop_count": None,
            "media_probe_status": "error",
        }
        errors.append(f"probe: {type(exc).__name__}: {exc}")
    stat = path.stat()
    return {
        "media_id": f"{source_id}:{digest or relative}",
        "source_id": source_id,
        "relative_path": relative,
        "extension": path.suffix.casefold(),
        "media_type": media_type,
        "size_bytes": stat.st_size,
        "modified_time": stat.st_mtime,
        "sha256": digest,
        **probe_fields,
        "license_status": "unknown",
        "license_notes": "Local provenance and license not verified.",
        "status": "needs_review" if errors else "screened",
        "errors": errors,
    }


def scan_library(root: Path, output: Path, source_id: str, probe_media: bool = True) -> ScanSummary:
    root = root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    supported = [path for path in paths if path.suffix.casefold() in _SUPPORTED]
    records = [_record(root, path, source_id, probe_media) for path in supported]
    records.sort(key=lambda record: record["relative_path"])

    manifest = output / "manifest.jsonl"
    manifest.write_text("".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records), encoding="utf-8")

    by_hash: dict[str, list[str]] = defaultdict(list)
    by_name: dict[str, list[str]] = defaultdict(list)
    for record in records:
        if record["sha256"]:
            by_hash[record["sha256"]].append(record["relative_path"])
        by_name[normalize_download_name(Path(record["relative_path"]).name)].append(record["relative_path"])
    content_groups = {key: value for key, value in sorted(by_hash.items()) if len(value) > 1}
    name_groups = {key: value for key, value in sorted(by_name.items()) if len(value) > 1}
    (output / "duplicates.json").write_text(
        json.dumps({"content_hash_groups": content_groups, "normalized_name_groups": name_groups}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = ScanSummary(
        source_id=source_id,
        input_file_count=len(paths),
        supported_media_count=len(supported),
        skipped_count=len(paths) - len(supported),
        byte_total=sum(record["size_bytes"] for record in records),
        content_duplicate_group_count=len(content_groups),
        normalized_name_duplicate_group_count=len(name_groups),
        error_count=sum(bool(record["errors"]) for record in records),
    )
    (output / "scan_summary.json").write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
