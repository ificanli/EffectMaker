"""Deterministic texture sampling with first-phase index compatibility."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable

from workspace.tools.resource_index.metadata import sha256_file
from .query import is_within_root

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga", ".dds"}


def _asset_id(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()


def _valid_record(record: dict[str, object], root: Path) -> bool:
    relative = str(record.get("relative_path", ""))
    candidate = (root / relative).resolve() if relative else root
    return bool(
        relative
        and is_within_root(candidate, root)
        and str(record.get("asset_type", "texture")) == "texture"
        and str(record.get("status", "present")) == "present"
        and not record.get("error")
        and candidate.is_file()
    )


def _from_sqlite(path: Path, root: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    connection = None
    try:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        columns = {row[1] for row in connection.execute("PRAGMA table_info(assets)")}
        required = {"asset_id", "relative_path", "asset_type", "sha256"}
        if not required.issubset(columns):
            return []
        status = "status" if "status" in columns else "'present' AS status"
        error = "error" if "error" in columns else "NULL AS error"
        rows = connection.execute(
            f"SELECT asset_id, relative_path, asset_type, sha256, {status}, {error} "
            "FROM assets WHERE asset_type = 'texture' ORDER BY relative_path"
        ).fetchall()
        return [_metadata(dict(row), root) for row in rows if _valid_record(dict(row), root)]
    except sqlite3.Error:
        return []
    finally:
        if connection is not None:
            connection.close()


def _from_jsonl(path: Path, root: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    records = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if _valid_record(row, root):
                    records.append(_metadata(row, root))
    except (OSError, ValueError, TypeError):
        return []
    return sorted(records, key=lambda row: row["relative_path"])


def _metadata(record: dict[str, object], root: Path) -> dict[str, str]:
    relative = str(record["relative_path"])
    digest = str(record.get("sha256") or sha256_file(root / relative))
    return {
        "asset_id": str(record.get("asset_id") or _asset_id(relative)),
        "relative_path": relative,
        "sha256": digest,
    }


def _scan(root: Path) -> Iterable[dict[str, str]]:
    paths = sorted(
        path for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    for path in paths:
        relative = path.relative_to(root).as_posix()
        yield {
            "asset_id": _asset_id(relative),
            "relative_path": relative,
            "sha256": sha256_file(path),
        }


def _spread(records: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    """Select evenly across a stable list rather than only its first directory."""
    if len(records) <= limit:
        return records
    indices = [(index * len(records)) // limit for index in range(limit)]
    return [records[index] for index in indices]


def select_sample(
    root: Path,
    *,
    limit: int = 64,
    sqlite_path: Path | None = None,
    jsonl_path: Path | None = None,
) -> list[dict[str, str]]:
    """Return a deterministic representative texture sample without writing to root."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"resource root is not a directory: {root}")
    if limit <= 0:
        raise ValueError("sample limit must be positive")
    records = _from_sqlite(Path(sqlite_path), root) if sqlite_path else []
    if not records and jsonl_path:
        records = _from_jsonl(Path(jsonl_path), root)
    if not records:
        records = list(_scan(root))
    return _spread(records, limit)


__all__ = ["select_sample"]
