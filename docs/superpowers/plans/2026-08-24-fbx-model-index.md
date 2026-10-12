# FBX/OBJ Model Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a small, resumable Blender 5.0 headless prototype that indexes FBX/OBJ geometry and renders multi-angle previews without modifying local resources.

**Architecture:** A pure-Python orchestration package discovers and hashes assets, skips valid checkpoint entries, invokes Blender with a generated temporary script, validates structured JSON results, and atomically writes JSONL/JSON artifacts. Blender performs import, mesh aggregation, metadata extraction, camera setup, and PNG rendering; one asset failure is recorded and processing continues.

**Tech Stack:** Python 3 standard library, `unittest`, Blender 5.0 headless Python API, PNG output from Blender.

**Spec:** Approved vfx-v29 design in chat.

## Global Constraints

- `resource/` is read-only.
- Asset IDs are SHA-256 of POSIX relative paths; content hashes are SHA-256 of bytes.
- The prototype processes a bounded sample via `build-sample --limit 5` and supports resume.
- Blender failures are per-model records and never abort the batch.
- No uploads, commits, pushes, or Beads status mutations.

### Task 1: Pure contracts and orchestration tests

**Files:** Create `workspace/tools/model_index/__init__.py`, `workspace/tools/model_index/core.py`, `workspace/tools/model_index/cli.py`; Test `workspace/tests/model_index/test_core.py`, `workspace/tests/model_index/test_cli.py`.

- [ ] Write failing tests for POSIX path/content hashes, extension discovery and limit, checkpoint skip on matching content/parser version, schema fields, and per-file failure continuation using a fake Blender runner.
- [ ] Run `python -m unittest workspace.tests.model_index.test_core workspace.tests.model_index.test_cli -v` and verify failures.
- [ ] Implement dataclasses/helpers, JSONL append/atomic JSON writes, checkpoint validation, and CLI argument parsing.
- [ ] Run focused tests and verify pass.

### Task 2: Blender adapter and script contract

**Files:** Create `workspace/tools/model_index/blender_runner.py`, `workspace/tools/model_index/blender_script.py`; Test `workspace/tests/model_index/test_blender_runner.py`.

- [ ] Test generated command/script inputs, structured stdout parsing, nonzero exit errors, and required metadata/preview paths.
- [ ] Implement temporary script invocation via `subprocess.run`, JSON result marker parsing, and Blender 5-compatible import/render script for FBX/OBJ.
- [ ] Run adapter tests.

### Task 3: Documentation and integration

**Files:** Modify `workspace/tools/model_index/cli.py` if needed and `README.md`; Create `docs/30-操作指南/FBX几何索引与预览原型使用指南.md`.

- [ ] Document prerequisites, commands, output schemas, resume semantics, read-only/licensing boundaries, and troubleshooting.
- [ ] Add README link.
- [ ] Run focused and full unittest suites.

### Task 4: Acceptance and report

**Files:** Create `E:/Unity特效人工智能学习/.superpowers/sdd/2026-08-24-fbx-model-index/report.md`.

- [ ] Detect installed Blender 5.0 executable and select 1-2 real assets without editing them.
- [ ] Run a real headless sample and verify metadata, progress, manifest, checkpoint, and nonblank PNG outputs.
- [ ] Record tests, backend, acceptance results, concerns, and changed files in the report.
- [ ] Run `git status --short` and leave Beads/Git untouched.
