from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Callable

from PIL import Image

from .blender_runner import run_blender
from workspace.tools.resource_index.classify import derive_tags

PARSER_VERSION = "blender-model-index-v2"
EXTENSIONS = {".fbx", ".obj"}


def asset_id_for(relative_path: str) -> str:
    return hashlib.sha256(relative_path.replace("\\", "/").encode("utf-8")).hexdigest()


def content_hash_for(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_assets(root: Path, limit: int | None = None) -> list[Path]:
    paths = sorted((p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS),
                   key=lambda p: p.relative_to(root).as_posix())
    return paths if limit is None else paths[:limit]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def build_sample(root: Path, output: Path, limit: int = 5, blender: str = "blender",
                 resume: bool = False, runner: Callable | None = None) -> dict:
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {}
    previous = checkpoint.get("assets", {})
    assets = discover_assets(root, limit)
    metadata_path, progress_path = output / "metadata.jsonl", output / "progress.jsonl"
    existing = {}
    if resume and metadata_path.exists():
        for line in metadata_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                existing[row["asset_id"]] = row
    metadata_rows, progress_rows, errors = [], [], 0
    run = runner or (lambda path, preview_dir, asset_id: run_blender(path, preview_dir, blender, asset_id=asset_id))
    for path in assets:
        relative = path.relative_to(root).as_posix()
        asset_id, content_hash = asset_id_for(relative), content_hash_for(path)
        cached = previous.get(asset_id)
        if resume and cached and cached.get("content_sha256") == content_hash and cached.get("parser_version") == PARSER_VERSION:
            row = existing.get(asset_id, cached.get("metadata"))
            if row:
                metadata_rows.append(row)
                progress_rows.append({"asset_id": asset_id, "relative_path": relative, "status": "skipped"})
                continue
        base = {"asset_id": asset_id, "relative_path": relative, "content_sha256": content_hash,
                "parser_version": PARSER_VERSION, "format": path.suffix.lower().lstrip("."),
                "tags": derive_tags(Path(relative))}
        try:
            data = run(path, output / "previews", asset_id)
            row = {**base, **data, "status": "ok"}
        except Exception as error:  # per-model isolation is part of the prototype contract
            errors += 1
            row = {**base, "status": "error", "error": str(error), "previews": {}}
        metadata_rows.append(row)
        progress_rows.append({"asset_id": asset_id, "relative_path": relative, "status": row["status"]})
        previous[asset_id] = {"content_sha256": content_hash, "parser_version": PARSER_VERSION, "metadata": row}
    _write_jsonl(metadata_path, metadata_rows)
    _write_jsonl(progress_path, progress_rows)
    _write_json(checkpoint_path, {"parser_version": PARSER_VERSION, "assets": previous})
    _write_json(output / "manifest.json", {"parser_version": PARSER_VERSION, "root": str(root),
                                            "requested_limit": limit, "assets": len(metadata_rows), "errors": errors})
    return {"discovered": len(assets), "processed": len(metadata_rows), "errors": errors,
            "skipped": sum(1 for row in progress_rows if row["status"] == "skipped")}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _valid_preview(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False
        with Image.open(path) as image:
            if image.format != "PNG":
                return False
            image.load()
            return any(low != high for low, high in image.convert("RGB").getextrema())
    except (OSError, ValueError):
        return False


def _previews_exist(row: dict) -> bool:
    previews = row.get("previews", {})
    return row.get("status") == "ok" and set(previews) == {"front", "side", "perspective"} and all(
        _valid_preview(Path(path)) for path in previews.values())


def build_all(root: Path, output: Path, batch_size: int | None = None, blender: str = "blender",
              resume: bool = False, timeout: int = 300, *, limit: int | None = None,
              runner: Callable | None = None, write_observer: Callable | None = None) -> dict:
    """Build a sequential, resumable index; batch_size bounds this invocation when supplied."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root in output.parents:
        raise ValueError("output must be outside resource root")
    output.mkdir(parents=True, exist_ok=True)
    all_assets = discover_assets(root, limit)
    checkpoint_path = output / "checkpoint.json"
    metadata_path, progress_path = output / "metadata.jsonl", output / "progress.jsonl"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {}
    previous = checkpoint.get("assets", {})
    existing = {row["asset_id"]: row for row in _read_jsonl(metadata_path)} if resume else {}
    current_ids = {asset_id_for(path.relative_to(root).as_posix()) for path in all_assets}
    existing = {asset_id: row for asset_id, row in existing.items() if asset_id in current_ids}
    metadata_by_id: dict[str, dict] = dict(existing)
    progress_rows: list[dict] = []
    processed_now = 0
    latest_counts: dict | None = None
    run = runner or (lambda path, preview_dir, asset_id, timeout: run_blender(
        path, preview_dir, blender, timeout=timeout, asset_id=asset_id))

    def persist() -> dict:
        ordered = [metadata_by_id[key] for key in sorted(metadata_by_id, key=lambda item: metadata_by_id[item]["relative_path"])]
        succeeded = sum(row.get("status") == "ok" for row in ordered)
        failed = sum(row.get("status") == "error" for row in ordered)
        skipped = sum(row.get("status") == "skipped" for row in progress_rows)
        counts = {"input": len(all_assets), "processed": len(ordered), "succeeded": succeeded,
                  "failed": failed, "skipped": skipped, "remaining": len(all_assets) - len(ordered)}
        _write_jsonl(metadata_path, ordered)
        _write_jsonl(progress_path, progress_rows)
        _write_json(checkpoint_path, {"parser_version": PARSER_VERSION, "assets": previous})
        failures = [{"asset_id": row["asset_id"], "relative_path": row["relative_path"],
                     "error": row.get("error", "unknown")} for row in ordered if row.get("status") == "error"]
        _write_json(output / "manifest.json", {"parser_version": PARSER_VERSION, "root": str(root),
                    "output": str(output), "counts": counts, "failures": failures,
                    "updated_unix": time.time()})
        if write_observer:
            write_observer(progress_path, progress_rows)
        return counts

    for path in all_assets:
        relative = path.relative_to(root).as_posix()
        asset_id, content_hash = asset_id_for(relative), content_hash_for(path)
        cached = previous.get(asset_id)
        row = existing.get(asset_id) or (cached or {}).get("metadata")
        if (resume and cached and cached.get("content_sha256") == content_hash
                and cached.get("parser_version") == PARSER_VERSION and row and _previews_exist(row)):
            metadata_by_id[asset_id] = row
            progress_rows.append({"asset_id": asset_id, "relative_path": relative, "status": "skipped"})
            continue
        if batch_size is not None and processed_now >= batch_size:
            continue
        base = {"asset_id": asset_id, "relative_path": relative, "content_sha256": content_hash,
                "parser_version": PARSER_VERSION, "format": path.suffix.lower().lstrip("."),
                "tags": derive_tags(Path(relative))}
        started = time.monotonic()
        try:
            data = run(path, output / "previews", asset_id, timeout)
            row = {**base, **data, "status": "ok", "duration_seconds": time.monotonic() - started}
        except Exception as error:
            row = {**base, "status": "error", "error": str(error), "previews": {},
                   "duration_seconds": time.monotonic() - started}
        metadata_by_id[asset_id] = row
        progress_rows.append({"asset_id": asset_id, "relative_path": relative, "status": row["status"],
                              "duration_seconds": row["duration_seconds"]})
        previous[asset_id] = {"content_sha256": content_hash, "parser_version": PARSER_VERSION,
                              "metadata": row}
        processed_now += 1
        latest_counts = persist()
    observer = write_observer
    write_observer = None
    persist()
    write_observer = observer
    return latest_counts if latest_counts is not None else persist()


def query_metadata(metadata: Path, *, asset_type: str | None = None, tag: str | None = None,
                   min_vertices: int | None = None, max_vertices: int | None = None,
                   min_triangles: int | None = None, max_triangles: int | None = None) -> list[dict]:
    rows = _read_jsonl(Path(metadata))
    return [row for row in rows
            if (asset_type is None or row.get("format", "").lower() == asset_type.lower())
            and (tag is None or tag in row.get("tags", []))
            and (min_vertices is None or row.get("vertex_count", -1) >= min_vertices)
            and (max_vertices is None or row.get("vertex_count", -1) <= max_vertices)
            and (min_triangles is None or row.get("triangle_count", -1) >= min_triangles)
            and (max_triangles is None or row.get("triangle_count", -1) <= max_triangles)]
