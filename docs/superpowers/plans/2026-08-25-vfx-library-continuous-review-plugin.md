# VFX.library连续画面复核插件实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一个本地、可无人值守运行的连续画面复核插件，将 VFX.library 批次媒体标准化为稳定可浏览的帧流，并保存绑定证据的视觉观察记录。

**Architecture:** 插件分为三层：媒体读取层负责按确定性时间点生成标准 PNG 帧；本地 HTTP 服务层提供队列、帧导航和静态文件访问；观察记录层保存主题判断、可借鉴点、局限、不采用理由和反例。浏览器只查看插件生成的标准化帧，不直接依赖原始 GIF/视频渲染。

**Tech Stack:** Python 3 标准库、现有 FFmpeg 9.0.1、Pillow、`http.server`、JSON/JSONL、现有 `review_queue.json`。

**Spec:** 本次对话中已批准的“本地标准化媒体流 + 浏览器复核界面”设计。

## Global Constraints

- 外部目录 `E:/BaiduNetdiskDownload/VFX.library` 只读，不复制、移动、改名、删除或修改。
- 文件名主题、机器统计和单帧均只能作为候选或筛选信号，不能直接升级为视觉事实。
- 复核结果必须绑定 `relative_path`、`sha256`、时间标签和证据帧。
- UI 和报告不得生成质量评分、审美排名、原创性排名或推荐列表。
- 所有产物保持 `reference_only=true`；视觉读取失败时保持 `experimental`/`partial`。
- 不得将 `EXP-2026-067` 标记为 `verified`，不得在没有连续画面证据时创建高置信度规律。
- 默认不执行 commit、push 或 Dolt sync。

---

### Task 1: 建立标准化连续帧读取器

**Files:**
- Create: `workspace/tools/vfx_library_index/continuous_reader.py`
- Test: `workspace/tests/test_vfx_library_continuous_reader.py`

**Interfaces:**
- Produces `build_frame_plan(duration_seconds: float | None, labels: tuple[str, ...]) -> list[tuple[str, float | None]]`。
- Produces `extract_evidence_frames(source_root: Path, sample: dict, output: Path, runner: Callable[[list[str]], int] | None = None) -> dict`。
- Output includes `status`, `reference_only`, `relative_path`, `sha256`, `frames`, `failed_count`, and per-frame `command`, `output`, `returncode`, `error`.

- [ ] **Step 1: Write failing tests**

```python
def test_build_frame_plan_has_five_deterministic_labels():
    plan = build_frame_plan(2.0, ("start", "quarter", "middle", "three-quarter", "end"))
    assert [label for label, _ in plan] == ["start", "quarter", "middle", "three-quarter", "end"]
    assert plan[0][1] == 0.0
    assert plan[2][1] == 1.0


def test_extract_evidence_frames_records_failed_frame_without_losing_other_frames(tmp_path):
    sample = {"relative_path": "fire.gif", "sha256": "abc", "duration_seconds": 2.0}
    calls = []
    def runner(command):
        calls.append(command)
        return 1 if len(calls) == 5 else 0
    result = extract_evidence_frames(tmp_path, sample, tmp_path / "frames", runner=runner)
    assert result["status"] == "partial"
    assert result["failed_count"] == 1
    assert len(result["frames"]) == 5
    assert result["frames"][4]["status"] == "failed"
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m unittest workspace.tests.test_vfx_library_continuous_reader`

Expected: FAIL because the reader module and functions do not exist.

- [ ] **Step 3: Implement minimal deterministic extraction**

Use FFmpeg PNG output with `-threads 1`, `-frames:v 1`, and `-sseof -0.1` for the end point. Reuse existing successful output only when the file exists and has non-zero size. Never alter the source path.

- [ ] **Step 4: Run focused tests and verify pass**

Run: `python -m unittest workspace.tests.test_vfx_library_continuous_reader`

Expected: PASS, including failure retention and deterministic labels.

---

### Task 2: 建立本地 HTTP 复核服务

**Files:**
- Create: `workspace/tools/vfx_library_index/review_server.py`
- Create: `workspace/tools/vfx_library_index/static/review.html`
- Test: `workspace/tests/test_vfx_library_review_server.py`

**Interfaces:**
- `load_review_queue(path: Path) -> dict` validates `status == "review-queue"` and `reference_only is True`.
- `build_server_manifest(queue: dict, frame_root: Path) -> dict` returns samples, frame URLs, labels, hashes and candidate themes.
- `serve_review_server(queue_path: Path, frame_root: Path, observation_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None` serves the local UI and JSON endpoints.

- [ ] **Step 1: Write failing tests**

```python
def test_load_review_queue_rejects_non_reference_report(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text(json.dumps({"status": "review-queue", "reference_only": False}), encoding="utf-8")
    with self.assertRaises(ValueError):
        load_review_queue(path)


def test_build_server_manifest_exposes_frame_urls_without_quality_fields(tmp_path):
    queue = {"status": "review-queue", "reference_only": True, "items": [{
        "relative_path": "fire.gif", "sha256": "abc", "theme_candidate": "fire"
    }]}
    manifest = build_server_manifest(queue, tmp_path)
    payload = json.dumps(manifest)
    self.assertIn("fire.gif", payload)
    self.assertNotIn("quality_score", payload)
    self.assertNotIn("aesthetic_score", payload)
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m unittest workspace.tests.test_vfx_library_review_server`

Expected: FAIL because the service module does not exist.

- [ ] **Step 3: Implement local-only server**

Use `ThreadingHTTPServer` bound by default to `127.0.0.1`. Serve a static HTML page, `/api/manifest`, `/api/observations`, and `/frames/...` only below the configured frame root. Reject path traversal and reject queue reports that are not reference-only.

- [ ] **Step 4: Implement browser controls**

The page must provide queue next/previous, five time labels, play/pause, single-frame step, and observation fields for `theme_status`, `borrowable_points`, `limitations`, `do_not_use_reason`, and `counterexample`. Display the candidate theme as a candidate, not as a fact. Do not display scores or rankings.

- [ ] **Step 5: Run focused tests and verify pass**

Run: `python -m unittest workspace.tests.test_vfx_library_review_server`

Expected: PASS.

---

### Task 3: 保存绑定证据的视觉观察

**Files:**
- Create: `workspace/tools/vfx_library_index/observations.py`
- Modify: `workspace/tools/vfx_library_index/review_server.py`
- Test: `workspace/tests/test_vfx_library_observations.py`

**Interfaces:**
- `validate_observation(payload: dict, queue: dict) -> dict` validates path/hash/label membership.
- `append_observation(path: Path, payload: dict, queue: dict) -> dict` appends one JSONL record atomically enough for local use.
- Observation fields: `relative_path`, `sha256`, `label`, `theme_status`, `borrowable_points`, `limitations`, `do_not_use_reason`, `counterexample`, `confidence`, `reference_only`.

- [ ] **Step 1: Write failing tests**

```python
def test_observation_requires_queue_bound_evidence(tmp_path):
    queue = {"items": [{"relative_path": "fire.gif", "sha256": "abc"}]}
    payload = {"relative_path": "other.gif", "sha256": "abc", "label": "middle"}
    with self.assertRaises(ValueError):
        validate_observation(payload, queue)


def test_append_observation_preserves_reference_boundary(tmp_path):
    queue = {"items": [{"relative_path": "fire.gif", "sha256": "abc"}]}
    payload = {"relative_path": "fire.gif", "sha256": "abc", "label": "middle", "theme_status": "pending", "confidence": "low"}
    result = append_observation(tmp_path / "observations.jsonl", payload, queue)
    assert result["reference_only"] is True
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m unittest workspace.tests.test_vfx_library_observations`

Expected: FAIL because observation functions do not exist.

- [ ] **Step 3: Implement validation and JSONL persistence**

Only accept evidence keys present in the queue. Normalize missing textual fields to empty strings or `pending`; constrain confidence to `low`, `medium`, or `high` and never infer it automatically. Reject score-like fields.

- [ ] **Step 4: Connect UI save action**

The browser save action posts JSON to the local server. The server validates it against the queue and appends it to the configured JSONL file. Return the saved record and a clear validation error on failure.

- [ ] **Step 5: Run focused tests and verify pass**

Run: `python -m unittest workspace.tests.test_vfx_library_observations workspace.tests.test_vfx_library_review_server`

Expected: PASS.

---

### Task 4: 接入第一批队列并更新流程文档

**Files:**
- Create: `workspace/tools/vfx_library_index/review_server_cli.py`
- Modify: `docs/30-操作指南/VFX.library视觉知识吸收流程.md`
- Modify: `knowledge/sources/SRC-2026-VFXLIB-001/index.md`
- Modify: `knowledge/sources/SRC-2026-VFXLIB-001/visual_review_batch1.md`
- Modify: `docs/00-总纲/VFX.library阶段总结与下一阶段入口.md`
- Modify: `workspace/progress/ERROR_LOG.md`
- Test: `workspace/tests/test_vfx_library_review_server_cli.py`

**Interfaces:**
- CLI accepts `--queue`, `--frames`, `--observations`, `--host`, and `--port`.
- CLI validates the queue, builds the server manifest, and starts the local server without touching the external source directory.

- [ ] **Step 1: Write failing CLI smoke test**

```python
def test_cli_help_and_reference_queue_validation():
    result = subprocess.run([
        sys.executable, "-m", "workspace.tools.vfx_library_index.review_server_cli", "--help"
    ], check=False, capture_output=True, text=True)
    self.assertEqual(result.returncode, 0)
    self.assertIn("--queue", result.stdout)
```

- [ ] **Step 2: Implement CLI and safe path checks**

Use the existing batch queue and frame directory as inputs. The CLI must not copy or modify `E:/BaiduNetdiskDownload/VFX.library`; it only reads generated batch artifacts and writes observations below the workspace output directory.

- [ ] **Step 3: Add documentation and error record**

Document startup, endpoints, review fields, and the fact that visual observations remain experimental until independently reviewed. Record the prior browser screenshot failure and the new standardization workaround in `ERROR_LOG.md` with command, error, root cause, repair, verification, and prevention.

- [ ] **Step 4: Run all quality gates**

Run:

```bash
python -m unittest workspace.tests.test_vfx_library_continuous_reader
python -m unittest workspace.tests.test_vfx_library_review_server
python -m unittest workspace.tests.test_vfx_library_observations
python -m unittest discover -s workspace/tests -p 'test*.py'
python -m py_compile workspace/tools/vfx_library_index/continuous_reader.py workspace/tools/vfx_library_index/review_server.py workspace/tools/vfx_library_index/observations.py workspace/tools/vfx_library_index/review_server_cli.py
```

Expected: all tests pass and compilation succeeds. Keep `vfx-344` in progress until an actual continuous-frame review has produced evidence-bound observations.

---

## Verification and Handoff

After implementation, start the server on a free localhost port, verify `/api/manifest` and one frame URL, and record the command and result. Do not claim visual knowledge absorption until the frames are actually inspected and observations are saved. Report changed files, test results, server URL, and remaining visual review work. Do not commit, push, or synchronize Dolt data without explicit authorization.
