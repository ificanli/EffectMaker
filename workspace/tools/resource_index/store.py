"""SQLite persistence for the local VFX resource index."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import AssetRecord


class ResourceIndexStore:
    """Persist AssetRecord values without modifying the source resource tree."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                relative_path TEXT NOT NULL UNIQUE,
                asset_type TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_time REAL NOT NULL,
                sha256 TEXT,
                license_status TEXT NOT NULL,
                license_hints TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                mode TEXT,
                channels INTEGER,
                thumbnail_status TEXT,
                error TEXT,
                status TEXT NOT NULL DEFAULT 'present'
            );
            CREATE TABLE IF NOT EXISTS asset_tags (
                asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                tag TEXT NOT NULL,
                PRIMARY KEY (asset_id, tag)
            );
            CREATE TABLE IF NOT EXISTS scans (
                scan_id TEXT PRIMARY KEY,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                seen_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_assets_path ON assets(relative_path);
            CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
            CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256);
            CREATE INDEX IF NOT EXISTS idx_assets_license ON assets(license_status);
            CREATE INDEX IF NOT EXISTS idx_assets_dimensions ON assets(width, height);
            CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
            CREATE INDEX IF NOT EXISTS idx_asset_tags_tag ON asset_tags(tag);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def upsert_assets(self, records: Iterable[AssetRecord]) -> None:
        rows = list(records)
        with self.connection:
            for record in rows:
                self.connection.execute(
                    """
                    INSERT INTO assets (
                        asset_id, relative_path, asset_type, extension, size_bytes,
                        modified_time, sha256, license_status, license_hints, width,
                        height, mode, channels, thumbnail_status, error, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'present')
                    ON CONFLICT(relative_path) DO UPDATE SET
                        asset_id=excluded.asset_id, asset_type=excluded.asset_type,
                        extension=excluded.extension, size_bytes=excluded.size_bytes,
                        modified_time=excluded.modified_time, sha256=excluded.sha256,
                        license_status=excluded.license_status,
                        license_hints=excluded.license_hints, width=excluded.width,
                        height=excluded.height, mode=excluded.mode,
                        channels=excluded.channels,
                        thumbnail_status=excluded.thumbnail_status, error=excluded.error,
                        status='present'
                    """,
                    (
                        record.asset_id, record.relative_path, record.asset_type,
                        record.extension, record.size_bytes, record.modified_time,
                        record.sha256, record.license_status,
                        json.dumps(record.license_hints, ensure_ascii=False), record.width,
                        record.height, record.mode, record.channels,
                        record.thumbnail_status, record.error,
                    ),
                )
                row = self.connection.execute(
                    "SELECT asset_id FROM assets WHERE relative_path = ?",
                    (record.relative_path,),
                ).fetchone()
                self.connection.execute("DELETE FROM asset_tags WHERE asset_id = ?", (row[0],))
                self.connection.executemany(
                    "INSERT INTO asset_tags (asset_id, tag) VALUES (?, ?)",
                    ((row[0], tag) for tag in sorted(set(record.tags))),
                )

    def mark_missing(self, seen_paths: Iterable[str], scan_id: str) -> None:
        seen = sorted(set(seen_paths))
        with self.connection:
            self.connection.execute("UPDATE assets SET status = 'missing'")
            for path in seen:
                self.connection.execute(
                    "UPDATE assets SET status = 'present' WHERE relative_path = ?", (path,)
                )
            self.connection.execute(
                "INSERT OR REPLACE INTO scans (scan_id, seen_count) VALUES (?, ?)",
                (scan_id, len(seen)),
            )

    def get_by_path(self, relative_path: str) -> AssetRecord | None:
        row = self.connection.execute(
            "SELECT * FROM assets WHERE relative_path = ?", (relative_path,)
        ).fetchone()
        return self._record(row) if row else None

    def query(self, *, asset_type: str | None = None, tag: str | None = None,
              license_status: str | None = None, min_width: int | None = None,
              min_height: int | None = None, limit: int | None = None) -> list[AssetRecord]:
        clauses, params = [], []
        if asset_type is not None:
            clauses.append("a.asset_type = ?"); params.append(asset_type)
        if tag is not None:
            clauses.append("EXISTS (SELECT 1 FROM asset_tags t WHERE t.asset_id = a.asset_id AND t.tag = ?)"); params.append(tag)
        if license_status is not None:
            clauses.append("a.license_status = ?"); params.append(license_status)
        if min_width is not None:
            clauses.append("a.width >= ?"); params.append(min_width)
        if min_height is not None:
            clauses.append("a.height >= ?"); params.append(min_height)
        sql = "SELECT a.* FROM assets a" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY a.relative_path"
        if limit is not None:
            sql += " LIMIT ?"; params.append(max(0, int(limit)))
        return [self._record(row) for row in self.connection.execute(sql, params)]

    def duplicates(self, limit: int | None = None) -> list[dict[str, object]]:
        groups = self.connection.execute(
            "SELECT sha256, COUNT(*) AS count FROM assets WHERE sha256 IS NOT NULL GROUP BY sha256 HAVING COUNT(*) > 1 ORDER BY sha256"
            + (" LIMIT ?" if limit is not None else ""),
            ((max(0, int(limit)),) if limit is not None else ()),
        ).fetchall()
        return [{"sha256": row["sha256"], "count": row["count"], "paths": [r[0] for r in self.connection.execute("SELECT relative_path FROM assets WHERE sha256 = ? ORDER BY relative_path", (row["sha256"],))]} for row in groups]

    def stats(self) -> dict[str, int]:
        row = self.connection.execute("SELECT COUNT(*) AS total, SUM(status = 'present') AS present, SUM(status = 'missing') AS missing FROM assets").fetchone()
        return {key: int(row[key] or 0) for key in ("total", "present", "missing")}

    def export_jsonl(self, path: Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            for record in self.query():
                stream.write(json.dumps(self._payload(record), ensure_ascii=False, sort_keys=True) + "\n")

    def _record(self, row: sqlite3.Row) -> AssetRecord:
        tags = [r[0] for r in self.connection.execute("SELECT tag FROM asset_tags WHERE asset_id = ? ORDER BY tag", (row["asset_id"],))]
        record = AssetRecord(
            asset_id=row["asset_id"], relative_path=row["relative_path"], asset_type=row["asset_type"],
            extension=row["extension"], size_bytes=row["size_bytes"], modified_time=row["modified_time"],
            sha256=row["sha256"], tags=tags, license_status=row["license_status"],
            license_hints=json.loads(row["license_hints"]), width=row["width"], height=row["height"],
            mode=row["mode"], channels=row["channels"], thumbnail_status=row["thumbnail_status"], error=row["error"],
        )
        record.status = row["status"]
        return record

    @staticmethod
    def _payload(record: AssetRecord) -> dict[str, object]:
        payload = record.to_dict()
        payload["status"] = getattr(record, "status", "present")
        return payload


__all__ = ["ResourceIndexStore"]
