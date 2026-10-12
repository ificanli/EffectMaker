# SRC-2026-VFXLIB-001 索引

## 当前阶段

- 状态：`experimental`
- 当前阶段：连续画面视觉复核已暂停，等待显示宿主恢复后继续
- 暂停任务：`vfx-2i7`（暂停：VFX.library连续画面视觉复核）
- 已完成分页任务：`vfx-430`（VFX.library 分页视觉索引与媒体证据详情；仅代表分页索引完成）
- 恢复入口：`workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json`

## 机器产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 媒体清单 | `workspace/data/resource_index/vfx_library/manifest.jsonl` | 每个支持媒体一条记录，含路径、大小、哈希和探测字段 |
| 重复报告 | `workspace/data/resource_index/vfx_library/duplicates.json` | 内容哈希重复组与规范化文件名提示组 |
| 扫描摘要 | `workspace/data/resource_index/vfx_library/scan_summary.json` | 输入、支持媒体、跳过、字节数和错误统计 |
| 证据点 | `workspace/data/resource_index/vfx_library/evidence_manifest.jsonl` | 后续抽帧/联系表的确定性起点 |
| 自动复核报告 | `workspace/data/resource_index/vfx_library/review/review_report.json` | 8,707/8,798 个证据点成功；失败命令和回退记录 |
| 分页媒体总览 | `workspace/data/resource_index/vfx_library/review/overview/index.json` | 1,463 个 canonical 媒体，按每页 64 个媒体分页 |
| 分页主题候选 | `workspace/data/resource_index/vfx_library/review/themes/index.json` | 13 个文件名关键词候选主题，含 `unclassified` |
| 单媒体详情 | `workspace/data/resource_index/vfx_library/review/media/` | 每个 canonical 媒体的多时间点联系表 |
| 第一批候选视觉包 | `workspace/data/resource_index/vfx_library/visual_package_batch1/visual_package.json` | 30 个按 SHA 去重样本，6 个主题候选，仅供参考，不代表审美标准 |
| 第一批批次证据 | `workspace/data/resource_index/vfx_library/visual_package_batch1/evidence_manifest.jsonl` | 150 个多时间点证据点，待连续画面复核 |
| 第一批客观量化报告 | `workspace/data/resource_index/vfx_library/visual_package_batch1/triage/triage_report.json` | 147 张成功帧的尺寸、透明度、亮度等筛选信号；仅用于排序和异常定位，不是质量评分 |
| 第一批视觉复核队列 | `workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json` | 30 个样本、6 个候选主题；按证据完整性安排查看顺序，不是质量或审美排序 |

## 证据规则

每条观察必须引用 `relative_path`、`sha256`、代表帧或时间点。探测失败、下载不完整和来源不明条目只能标记为待审，不得直接进入稳定规范。展示画面默认只支持审美观察，不支持制作步骤推断。

## 后续关联

- 审美知识卡片：待聚类后建立 `AESTHETIC-*`
- 制作知识卡片：仅对存在明确操作/参数证据的条目建立 `CRAFT-*`
- Unity 验证实验：待跨条目或跨来源规律形成后建立 `EXP-*`
