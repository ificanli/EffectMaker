# VFX Resource Index Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, incremental local index for the VFX resources under `resource/`, with SQLite, JSONL, image metadata, thumbnails, path tags, license status, duplicate detection, and CLI queries.

**Architecture:** A focused Python package under `workspace/tools/resource_index/` separates classification, metadata extraction, thumbnail generation, persistence, scanning, and CLI concerns. The resource tree is treated as immutable input; all generated state lives under `workspace/data/resource_index/`. Tests use the Python standard library `unittest` and temporary directories.

**Tech Stack:** Python 3.14, standard library (`sqlite3`, `hashlib`, `argparse`, `dataclasses`, `unittest`), Pillow 12.3.

**Spec:** `docs/superpowers/specs/2026-08-24-vfx-resource-index-design.md`

## Global Constraints

- Never create, modify, move, rename, or delete files under `resource/`.
- Default authorization status is exactly `unknown`; path names and local possession never grant redistribution rights.
- Generated data must stay under `workspace/data/resource_index/`.
- Do not extract archives or Unity packages.
- A corrupt or unsupported asset records an error and does not abort the scan.
- Use repository Beads task `vfx-kkm` for durable status; do not create markdown TODO lists.
- Do not commit or push unless explicitly requested.

---

### Task 1: Asset types and classification

**Files:**
- Create: `workspace/tools/resource_index/__init__.py`
- Create: `workspace/tools/resource_index/models.py`
- Create: `workspace/tools/resource_index/classify.py`
- Test: `workspace/tests/resource_index/__init__.py`
- Test: `workspace/tests/resource_index/test_classify.py`

**Interfaces:**
- Produces: `AssetRecord`, `ScanConfig`, `classify_asset(path: Path) -> str`, `derive_tags(relative_path: Path) -> list[str]`, `infer_license(relative_path: Path) -> tuple[str, list[str]]`.

- [ ] Write tests proving extension classification, bilingual path tag normalization, stable tag ordering, and conservative `unknown` licensing.
- [ ] Run `python -m unittest workspace.tests.resource_index.test_classify -v` and verify failure before implementation.
- [ ] Implement frozen configuration and mutable asset-record dataclasses with JSON-safe serialization.
- [ ] Implement explicit extension maps and normalized tag vocabulary for slash, fire, ice, magic-circle, mask, noise, distortion, flipbook, trail, water, smoke, lightning, shield, portal, ground, UI, and model categories.
- [ ] Implement license hint collection without automatically upgrading `license_status`.
- [ ] Re-run the classification tests and verify all pass.

### Task 2: Hash and image metadata extraction

**Files:**
- Create: `workspace/tools/resource_index/metadata.py`
- Test: `workspace/tests/resource_index/test_metadata.py`

**Interfaces:**
- Consumes: `AssetRecord` from Task 1.
- Produces: `sha256_file(path: Path, chunk_size: int = 1048576) -> str`, `read_image_metadata(path: Path) -> dict[str, object]`, `extract_metadata(path: Path, asset_type: str) -> dict[str, object]`.

- [ ] Write tests using generated RGB and RGBA PNG fixtures, identical-content files, and a corrupt image.
- [ ] Run the metadata test module and verify it fails because the module is absent.
- [ ] Implement streaming SHA-256 without loading whole files into memory.
- [ ] Implement Pillow-backed width, height, mode, channel count, animation frame count, and image error capture.
- [ ] Ensure non-image assets return empty image fields rather than attempting Pillow decode.
- [ ] Re-run tests and verify identical files share hashes while corrupt images return an error record.

### Task 3: Thumbnail generation

**Files:**
- Create: `workspace/tools/resource_index/thumbnails.py`
- Test: `workspace/tests/resource_index/test_thumbnails.py`

**Interfaces:**
- Produces: `thumbnail_relative_path(asset_id: str) -> Path`, `create_thumbnail(source: Path, destination_root: Path, asset_id: str, size: int = 256) -> tuple[str | None, str | None]`.

- [ ] Write tests proving aspect ratio preservation, deterministic output path, RGBA-to-RGB-safe JPEG/PNG output, unsupported file error capture, and no source directory writes.
- [ ] Run the thumbnail tests and observe expected import failure.
- [ ] Implement thumbnail generation with Pillow `thumbnail`, a transparent checkerboard background, and PNG output.
- [ ] Ensure the function returns an error string instead of raising for unsupported or corrupt assets.
- [ ] Re-run tests and verify generated files exist only under the supplied destination root.

### Task 4: SQLite storage and JSONL export

**Files:**
- Create: `workspace/tools/resource_index/store.py`
- Test: `workspace/tests/resource_index/test_store.py`

**Interfaces:**
- Consumes: `AssetRecord`.
- Produces: `ResourceIndexStore(db_path: Path)`, methods `initialize()`, `upsert_assets(records)`, `get_by_path(relative_path)`, `mark_missing(seen_paths, scan_id)`, `query(...)`, `duplicates(limit)`, `stats()`, and `export_jsonl(path)`.

- [ ] Write tests for schema creation, idempotent upsert, tag persistence, missing-file marking, duplicate hash groups, filtered queries, and JSONL row-count equality.
- [ ] Run the store tests and verify failure before implementation.
- [ ] Implement tables `assets`, `asset_tags`, and `scans`, with indexes on path, type, SHA-256, license, dimensions, status, and tags.
- [ ] Store tags relationally while exposing them as sorted lists.
- [ ] Implement parameterized filters for type, tag, license, minimum width/height, and result limit.
- [ ] Implement deterministic JSONL export ordered by relative path.
- [ ] Re-run store tests and verify all pass.

### Task 5: Incremental read-only scanner

**Files:**
- Create: `workspace/tools/resource_index/scanner.py`
- Test: `workspace/tests/resource_index/test_scanner.py`

**Interfaces:**
- Consumes: classification, metadata, thumbnails, and store modules.
- Produces: `scan_resources(config: ScanConfig) -> dict[str, int | str]`.

- [ ] Write an integration test fixture with one image, duplicate image, model placeholder, document, unsupported file, and corrupt image.
- [ ] Snapshot the fixture source tree before scanning and assert the snapshot is byte-for-byte unchanged after scanning.
- [ ] Test first scan counts, second unchanged scan reuse, added file, modified file, and removed file status.
- [ ] Run the scanner tests and verify failure before implementation.
- [ ] Implement deterministic recursive traversal, stable asset IDs derived from normalized relative paths, incremental reuse by size and mtime, batched persistence, thumbnail generation, error counting, and JSON summary output.
- [ ] Ensure symlinks are not followed and generated output cannot resolve beneath the source root.
- [ ] Re-run scanner tests and verify all pass.

### Task 6: Command-line interface and documentation

**Files:**
- Create: `workspace/tools/resource_index/cli.py`
- Test: `workspace/tests/resource_index/test_cli.py`
- Create: `docs/30-操作指南/VFX本地资源索引使用指南.md`
- Modify: `docs/README.md`

**Interfaces:**
- Produces commands `scan`, `stats`, `query`, and `duplicates` runnable via `python -m workspace.tools.resource_index.cli`.

- [ ] Write CLI tests invoking `main(argv)` for scan, JSON stats, filtered JSON query, and duplicate output.
- [ ] Run CLI tests and verify failure before implementation.
- [ ] Implement non-interactive argparse commands with root/output defaults resolved from repository root.
- [ ] Add `--json`, `--limit`, `--type`, `--tag`, `--license`, `--min-width`, `--min-height`, `--no-thumbnails`, and `--force-hash` options.
- [ ] Write the operator guide with initial scan, incremental scan, common VFX queries, output layout, authorization warnings, backup guidance, and failure recovery.
- [ ] Add the guide link to `docs/README.md`.
- [ ] Run all resource-index tests with `python -m unittest discover -s workspace/tests/resource_index -v`.

### Task 7: Full resource scan and acceptance verification

**Files:**
- Generate: `workspace/data/resource_index/assets.sqlite3`
- Generate: `workspace/data/resource_index/assets.jsonl`
- Generate: `workspace/data/resource_index/scan_summary.json`
- Generate: `workspace/data/resource_index/thumbnails/`
- Modify: Beads issue `vfx-kkm` with results.

**Interfaces:**
- Consumes: completed CLI.
- Produces: searchable local index for the 22,223+ resource library.

- [ ] Record pre-scan source file count and a read-only source-tree fingerprint made from relative path, size, and mtime.
- [ ] Run `python -m workspace.tools.resource_index.cli scan --root resource --output workspace/data/resource_index --json`.
- [ ] Run `stats`, sample texture/model queries, and duplicate listing.
- [ ] Confirm SQLite active asset count equals JSONL line count and the source-tree fingerprint is unchanged.
- [ ] Re-run the scan and confirm unchanged assets are reused rather than fully reprocessed.
- [ ] Record counts, failures, unsupported formats, duplicate groups, output size, and elapsed time in Beads `vfx-kkm`.
- [ ] Keep the issue open if image formats or files require follow-up; close only when all acceptance criteria are evidenced.
