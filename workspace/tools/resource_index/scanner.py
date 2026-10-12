"""Incremental, read-only scanner for local VFX resources."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from .classify import classify_asset, derive_tags, infer_license
from .metadata import extract_metadata
from .models import AssetRecord, ScanConfig
from .store import ResourceIndexStore
from .thumbnails import create_thumbnail


def scan_resources(config: ScanConfig) -> dict[str, int | str]:
    """Scan *config.root* and persist an incremental resource index."""
    root = Path(config.root).resolve()
    output = Path(config.output_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"scan root is not a directory: {config.root}")
    if _paths_overlap(root, output):
        raise ValueError("scan root and output directory must not overlap")

    output.mkdir(parents=True, exist_ok=True)
    store = ResourceIndexStore(output / "assets.sqlite3")
    try:
        files = list(_iter_files(root))
        records: list[AssetRecord] = []
        seen_paths: list[str] = []
        counts = {
            "scanned": len(files), "added": 0, "modified": 0, "unchanged": 0,
            "removed": 0, "errors": 0, "thumbnails_created": 0,
            "thumbnails_failed": 0,
        }
        for path in files:
            relative = path.relative_to(root).as_posix()
            seen_paths.append(relative)
            try:
                stat = path.stat()
                asset_type = classify_asset(path)
                previous = store.get_by_path(relative)
                if (previous is not None and not config.force_hash
                        and previous.size_bytes == stat.st_size
                        and previous.modified_time == stat.st_mtime
                        and previous.thumbnail_status != "error"
                        and previous.error is None):
                    records.append(previous)
                    counts["unchanged"] += 1
                    continue

                counts["added" if previous is None else "modified"] += 1
                asset_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()
                license_status, license_hints = infer_license(Path(relative))
                metadata = extract_metadata(path, asset_type)
                error_messages = []
                if metadata.get("error"):
                    error_messages.append(str(metadata["error"]))
                thumbnail_status = None
                if asset_type == "texture" and config.create_thumbnails:
                    thumbnail_path, thumbnail_error = create_thumbnail(
                        path, output, asset_id, size=config.thumbnail_size
                    )
                    if thumbnail_path:
                        thumbnail_status = thumbnail_path
                        counts["thumbnails_created"] += 1
                    else:
                        thumbnail_status = "error"
                        counts["thumbnails_failed"] += 1
                        if thumbnail_error:
                            error_messages.append(thumbnail_error)
                record = AssetRecord(
                    asset_id=asset_id,
                    relative_path=relative,
                    asset_type=asset_type,
                    extension=path.suffix,
                    size_bytes=stat.st_size,
                    modified_time=stat.st_mtime,
                    sha256=metadata.get("sha256"),
                    tags=derive_tags(Path(relative)),
                    license_status=license_status,
                    license_hints=license_hints,
                    width=metadata.get("width"),
                    height=metadata.get("height"),
                    mode=metadata.get("mode"),
                    channels=metadata.get("channels"),
                    thumbnail_status=thumbnail_status,
                    error="; ".join(error_messages) or None,
                )
                if record.error:
                    counts["errors"] += 1
                records.append(record)
            except Exception as error:
                counts["errors"] += 1
                relative_path = Path(relative)
                license_status, license_hints = infer_license(relative_path)
                records.append(AssetRecord(
                    asset_id=hashlib.sha256(relative.encode("utf-8")).hexdigest(),
                    relative_path=relative,
                    asset_type=classify_asset(relative_path),
                    extension=relative_path.suffix,
                    size_bytes=0,
                    modified_time=0.0,
                    tags=derive_tags(relative_path),
                    license_status=license_status,
                    license_hints=license_hints,
                    error=f"{type(error).__name__}: {error}",
                ))

        previous_present_paths = {
            record.relative_path
            for record in store.query()
            if getattr(record, "status", "present") == "present"
        }
        store.upsert_assets(records)
        store.mark_missing(seen_paths, _scan_id(records))
        counts["removed"] = len(previous_present_paths - set(seen_paths))
        store.export_jsonl(output / "assets.jsonl")
        summary = {**counts, **store.stats(), "root": str(config.root)}
        (output / "scan_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary
    finally:
        store.close()


def _iter_files(root: Path) -> Iterable[Path]:
    """Yield regular files in stable order without following symlinks."""
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(name for name in directories
                                 if not (Path(current) / name).is_symlink())
        for name in sorted(filenames):
            path = Path(current) / name
            if not path.is_symlink() and path.is_file():
                yield path


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _scan_id(records: Iterable[AssetRecord]) -> str:
    payload = "\n".join(
        f"{record.relative_path}:{record.size_bytes}:{record.modified_time}"
        for record in records
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["scan_resources"]
