# SRC-2026-VFXLIB-001：VFX.library 特效视觉参考媒体库

## 基本信息

- 资料 ID：`SRC-2026-VFXLIB-001`
- 类型：`visual-reference-library`
- 管道：审美为主；仅在出现可复现制作证据时进入制作候选
- 获取日期：2026-08-25
- 本地路径：`E:/BaiduNetdiskDownload/VFX.library`
- 当前状态：`experimental`
- 作者、平台、原始 URL、发布日期：`unknown`
- 授权状态：`unknown`

## 学习定位

该目录包含 GIF、MP4、MOV、WEBM、AVI 等特效视觉资料，并伴随图片、JSON 和其他下载器元数据。它是视觉参考库，不等同于课程，也不自动提供实现步骤。首轮目标是建立可检索、可去重、可回溯的媒体清单；后续按视觉主题聚类，再提炼审美规律。只有资料明确展示编辑器操作、节点或参数时，才考虑制作管道。

## 使用限制

本地副本仅用于本工程内部学习、检索和分析。原始文件保留在外部目录，不复制、移动、改名或删除；不将其作为可公开分发项目资产。无法由本地证据确认的作者、来源和授权信息保持 `unknown`。

## 第一阶段产物

- 扫描清单：`workspace/data/resource_index/vfx_library/manifest.jsonl`
- 重复关系：`workspace/data/resource_index/vfx_library/duplicates.json`
- 扫描摘要：`workspace/data/resource_index/vfx_library/scan_summary.json`
- 证据点清单：`workspace/data/resource_index/vfx_library/evidence_manifest.jsonl`
- 扫描入口：`python -m workspace.tools.vfx_library_index.cli scan`

## 可复现命令

```bash
python -m workspace.tools.vfx_library_index.cli scan \
  --root E:/BaiduNetdiskDownload/VFX.library \
  --output E:/Unity特效人工智能学习/workspace/data/resource_index/vfx_library \
  --source-id SRC-2026-VFXLIB-001
```

## 状态推进标准

- `inbox`：已登记，尚未完成扫描。
- `screened`：扫描完成，文件完整性、元数据和重复关系已报告。
- `extracted`：已按主题提取视觉观察，并可定位到媒体文件和帧/时间点。
- `experimental`：高价值规律已有 Unity 验证实验。
- `absorbed`：结论已进入知识卡片、规范或可复用效果。

本阶段不得在没有证据的情况下创建 `CRAFT-*` 结论，也不得把展示视频的外观直接解释为实现事实。
