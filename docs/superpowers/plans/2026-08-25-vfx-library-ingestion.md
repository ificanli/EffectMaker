# VFX.library 视觉参考媒体入库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一个只读、可复现、可追溯的 GIF/视频特效参考媒体索引，并登记来源 `SRC-2026-VFXLIB-001`。

**Architecture:** 在现有 `resource_index` 旁增加面向动画媒体的扫描能力，复用 `workspace/tools/media.py` 的 ffprobe 逻辑。扫描输出 JSONL 清单、重复关系和摘要到独立目录；知识库来源记录只引用这些产物，不复制原始媒体。后续聚类、知识卡片与 Unity 验证通过 Beads 子任务继续推进。

**Tech Stack:** Python 3 标准库、现有 ffprobe/ffmpeg 工具发现逻辑、unittest、Markdown/JSONL。

**Spec:** `docs/superpowers/specs/2026-08-25-vfx-library-design.md`

## Global Constraints

- 输入目录固定为 `E:/BaiduNetdiskDownload/VFX.library`，扫描必须只读。
- 不复制、移动、改名、删除或覆盖输入目录中的文件。
- 不能把 `(1)` 文件名直接当作内容重复；内容哈希是强重复依据，规范化名称仅作提示关系。
- 未确认的作者、平台、原始 URL、授权状态标记为 `unknown`，不得猜写。
- 复用现有媒体探测工具和工程测试入口；当前环境优先使用 `python -m unittest`，不临时引入 pytest。
- 任何完成声明前必须运行测试、检查输出和 `git status`；不自动提交或推送。

---

### Task 1: Define animation-media metadata and classification

**Files:**
- Modify: `workspace/tools/resource_index/models.py`
- Modify: `workspace/tools/resource_index/classify.py`
- Modify: `workspace/tools/resource_index/metadata.py`
- Test: `workspace/tests/resource_index/test_classify.py`
- Test: `workspace/tests/resource_index/test_metadata.py`

**Interfaces:**
- `classify_extension()` recognizes `.gif`, `.mp4`, `.mov`, `.webm`, `.avi` as `animation` without changing existing image/model classifications.
- `AssetRecord` gains optional animation fields: `duration_seconds`, `fps`, `frame_count`, `loop_count`, and `media_probe_status`; existing record construction remains backward-compatible.
- Metadata extraction returns normalized numeric fields and an explicit unavailable value when ffprobe cannot provide one.

- [ ] **Step 1: Write failing classification tests** for GIF and video extensions and regression tests for PNG/FBX.
- [ ] **Step 2: Run `python -m unittest workspace.tests.resource_index.test_classify workspace.tests.resource_index.test_metadata -v` and confirm the new cases fail.
- [ ] **Step 3: Implement the minimal enum/model/metadata additions, preserving existing JSON serialization keys and defaults.
- [ ] **Step 4: Run the focused tests and confirm all pass.
- [ ] **Step 5: Run the existing resource-index model/store tests to catch schema compatibility regressions.

### Task 2: Add read-only VFX library scanner

**Files:**
- Create: `workspace/tools/vfx_library_index/__init__.py`
- Create: `workspace/tools/vfx_library_index/models.py`
- Create: `workspace/tools/vfx_library_index/scanner.py`
- Create: `workspace/tools/vfx_library_index/cli.py`
- Test: `workspace/tests/vfx_library_index/test_scanner.py`
- Test: `workspace/tests/vfx_library_index/test_cli.py`

**Interfaces:**
- `scan_library(root: Path, output: Path, source_id: str, probe_media: bool = True) -> ScanSummary`.
- `ScanSummary` contains input file count, supported media count, skipped count, byte total, content duplicate group count, normalized-name duplicate group count, and error count.
- Each JSONL record contains `media_id`, `source_id`, `relative_path`, `extension`, `media_type`, `size_bytes`, `sha256`, `modified_time`, probe fields, `license_status`, `license_notes`, `status`, and `errors`.
- CLI command: `python -m workspace.tools.vfx_library_index.cli scan --root <path> --output <path> --source-id SRC-2026-VFXLIB-001 [--no-probe]`.

- [ ] **Step 1: Write failing tests using a temporary directory containing one GIF-like fixture, one MP4-like fixture or mocked probe response, an unsupported file, and a duplicate byte copy.
- [ ] **Step 2: Run the focused scanner tests and confirm missing module/behavior failures.
- [ ] **Step 3: Implement deterministic path ordering, chunked SHA-256 hashing, safe ffprobe invocation through existing tool discovery, and JSONL output without touching inputs.
- [ ] **Step 4: Implement duplicate reports keyed by SHA-256 and a normalized filename report that strips only terminal numeric download suffixes such as `(1)`.
- [ ] **Step 5: Implement CLI argument validation and a machine-readable `scan_summary.json`.
- [ ] **Step 6: Run focused tests and verify a second scan produces stable IDs and equivalent records for unchanged fixtures.

### Task 3: Generate representative evidence pointers

**Files:**
- Modify: `workspace/tools/vfx_library_index/scanner.py`
- Create: `workspace/tools/vfx_library_index/evidence.py`
- Test: `workspace/tests/vfx_library_index/test_evidence.py`

**Interfaces:**
- `select_evidence_points(duration_seconds: float | None, frame_count: int | None, media_type: str) -> list[EvidencePoint]` returns deterministic start/middle/end points when duration is known and a bounded fallback for GIFs without duration.
- `write_evidence_manifest(records, output_dir) -> Path` writes pointers only; extraction failures are recorded per item and do not abort the entire scan.

- [ ] **Step 1: Write tests for short, long, unknown-duration, and invalid-duration media.
- [ ] **Step 2: Run the evidence tests and confirm they fail before implementation.
- [ ] **Step 3: Implement deterministic evidence-point selection and manifest writing, reusing existing frame extraction only when ffmpeg is available and explicitly requested.
- [ ] **Step 4: Run evidence tests and verify failure isolation for one bad media item.

### Task 4: Register source and document first-stage outputs

**Files:**
- Create: `knowledge/sources/SRC-2026-VFXLIB-001_source.md`
- Create: `knowledge/sources/SRC-2026-VFXLIB-001/index.md`
- Create: `knowledge/sources/SRC-2026-VFXLIB-001/README.md`
- Modify: `knowledge/index.md`
- Create: `knowledge/inbox/SRC-2026-VFXLIB-001-probe.json`

**Interfaces:**
- Source record documents absolute input path, acquisition date, media scope, internal-use restriction, unknown provenance policy, lifecycle status, scan command, output paths, and explicit non-goals.
- Source index links each generated manifest/report and defines the future clustering/card/experiment entry points without claiming those stages are complete.
- Main knowledge index adds one traceability row for `SRC-2026-VFXLIB-001` with status `screened` after successful scan.

- [ ] **Step 1: Write the source and inbox probe files from the approved design, using `unknown` for unverified provenance/license fields.
- [ ] **Step 2: Add the source row to `knowledge/index.md` without rewriting unrelated rows.
- [ ] **Step 3: Run a Markdown/link/path consistency check using repository search and JSON parsing.

### Task 5: Run the real library scan and quality gates

**Files:**
- Create: `workspace/data/resource_index/vfx_library/manifest.jsonl`
- Create: `workspace/data/resource_index/vfx_library/duplicates.json`
- Create: `workspace/data/resource_index/vfx_library/scan_summary.json`
- Create: `workspace/data/resource_index/vfx_library/evidence_manifest.jsonl`

**Interfaces:**
- Real scan uses the CLI from Task 2 against the exact external root and the stable source ID.
- Output records remain outside `knowledge/sources` as generated machine data; source docs link to them.

- [ ] **Step 1: Capture an input-directory file-state snapshot of supported media paths, sizes, and mtimes.
- [ ] **Step 2: Run the real scan with deterministic ordering and record the exact command in the source README.
- [ ] **Step 3: Run the evidence-manifest generation and inspect summary counts, probe errors, duplicate groups, and representative records.
- [ ] **Step 4: Re-run the scan in resume/idempotent mode or to a second output and compare counts and hashes.
- [ ] **Step 5: Compare the post-scan input snapshot with the pre-scan snapshot to prove the source tree was not modified.
- [ ] **Step 6: Run `python -m unittest discover -s workspace/tests -p 'test_*.py'` and the relevant CLI smoke commands.
- [ ] **Step 7: Run `git status --short`, inspect generated paths, update Beads with remaining clustering/card/validation work, and report results without committing or pushing.

## Follow-up Work Split

After Task 5, create dependent Beads tasks for:

1. Metadata-assisted visual clustering and contact sheets.
2. Aesthetic reference cards with evidence levels and temporal observations.
3. Craft cards only for media that expose reproducible implementation details.
4. Unity experiments for high-value, cross-source patterns.
5. Optional extension of the shared resource index/vector retrieval once the media schema proves stable.
