# Workspace Map

This folder holds the non-Unity support side of the workspace.

## Maintained Guide

- `vfx_generation_architecture.html`: 生成式 VFX 阶段汇报与架构导览；默认汇报视图展示累计建设、阶段进展、真实闪电帧回放和下一步里程碑，`#architecture`、`#tools`、`#status` 保留原架构入口。汇报文稿与证据口径见 `../docs/00-总纲/2026-09-07_VFX阶段汇报.md`。
- `vfx_guide_assets/`: 原参考截图、汇报样式与帧播放器、附授权的本地图标。实录直接引用 `data/vfx_generation/generated/` 的捕获记录与原始 PNG，不复制或伪造 Unity 帧。
- `data/vfx_generation/intake/prefab_batches/`: 上千个训练 Prefab 的批次登记入口；只保存来源和授权信息，不保存原始资源本体。
- `data/vfx_generation/corpora/`: 多来源 Prefab 的增量语料索引、防泄漏切分和失败记录。

## Main areas

- `tools/`: media, indexing, review, and verification scripts.
- `data/`: generated indexes, caches, and experiment data.
- `progress/`: status, blockers, acceptance records, and project routing.
- `tests/`: regression and contract tests for the tooling layer.
- `unity-verification/`: isolated Unity sandbox for batch verification.
- `previews/`: local HTML preview and review pages.
- `bin/`: local CLI wrappers.
- `boards/`: local task-board helpers.
- `windows/`: reserved for Windows-specific helpers if needed.

## Rule of thumb

Keep reusable code in `tools/`, generated state in `data/`, human-readable status in `progress/`, and temporary visual review pages in `previews/`.
