# VFX.library 分页视觉索引实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 生成覆盖 canonical 媒体的总览分页、文件名主题候选分页和单媒体多时间点详情。

**Architecture:** 复用现有 FFmpeg 抽帧结果，在 `review.py` 中先聚合媒体详情，再按 canonical 媒体分页生成 JPEG 与 JSON 索引。保留旧平面结果字段和单页联系表，主题分页直接调用既有文件名关键词分类。

**Tech Stack:** Python 标准库、FFmpeg、Pillow、`unittest`、Beads。

**Spec:** `docs/superpowers/specs/2026-08-25-vfx-library-paged-visual-index-design.md`

## Global Constraints

- 外部 `E:/BaiduNetdiskDownload/VFX.library` 只读。
- 不把文件名主题写成视觉事实。
- 保留 91 个失败证据点及旧报告字段。
- 不新增第三方依赖，不扩展抽帧时间点。
- 不执行 commit、push 或 Dolt 同步。

## Task 1: 报告聚合与分页数据契约

**Files:**
- Modify: `workspace/tools/vfx_library_index/review.py`
- Test: `workspace/tests/test_vfx_library_review.py`

- [ ] 写临时 manifest/evidence/PNG fixture，覆盖同 SHA 别名、失败时间点、候选主题和 unclassified。
- [ ] 先运行聚焦测试，确认缺少 `media_details`、`overview_pages`、`theme_pages` 时失败。
- [ ] 实现 `build_media_details`、`canonicalize_media`、`paginate`，并保持平面 `results`。
- [ ] 运行聚焦测试，验证分页不拆媒体、失败点留痕、别名合并和稳定排序。

## Task 2: 联系表产物

**Files:**
- Modify: `workspace/tools/vfx_library_index/review.py`
- Test: `workspace/tests/test_vfx_library_review.py`

- [ ] 将每媒体成功时间点组成详情联系表。
- [ ] 生成 `overview/`、`themes/`、`media/` 下的 JPEG 与 JSON 索引。
- [ ] 保留旧 `contact_sheet.jpg`。
- [ ] 测试非空输出、主题候选字段、unclassified 页和详情图路径。

## Task 3: CLI 参数

**Files:**
- Modify: `workspace/tools/vfx_library_index/review_cli.py`
- Create: `workspace/tests/test_vfx_library_review_cli.py`

- [ ] 增加 `--page-size`，默认 64，拒绝非正整数。
- [ ] 测试参数透传、stdout JSON 和 ready/partial/blocked 退出码。

## Task 4: 文档和真实验收

**Files:**
- Modify: `docs/30-操作指南/VFX.library视觉知识吸收流程.md`
- Modify: `docs/00-总纲/VFX.library阶段总结与下一阶段入口.md`
- Modify: `knowledge/sources/SRC-2026-VFXLIB-001/README.md`
- Modify: `knowledge/sources/SRC-2026-VFXLIB-001/index.md`

- [ ] 记录分页入口、候选主题边界和真实产物路径。
- [ ] 使用 `--page-size 64` 运行真实 CLI。
- [ ] 验证 canonical 覆盖、页大小、失败点和输入快照。
- [ ] 运行 `python -m unittest discover -s workspace/tests -p 'test_*.py'`。
- [ ] 仅在所有门禁通过后关闭 Beads 任务 `vfx-430`。
