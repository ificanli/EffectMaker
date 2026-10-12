# VFX.library 分页视觉索引设计

## 目标

将 VFX.library 的单一、按帧截断的联系表扩展为覆盖全库 canonical 媒体的分页浏览入口，并保留每个媒体的多时间点证据详情。该层只改善浏览和证据定位，不生成视觉事实、制作参数或授权结论。

## 数据边界

- 外部目录 `E:/BaiduNetdiskDownload/VFX.library` 只读。
- 输入来自 `manifest.jsonl`、`evidence_manifest.jsonl` 和现有代表帧 PNG。
- 主题由既有 `classify_title(relative_path)` 提供，字段命名为 `candidate_theme`，依据固定为 `filename-keyword-candidate`。
- `start`、`middle`、`end` 及失败时间点全部保留；本任务不扩展抽帧时间点。

## Canonical 媒体

媒体聚合键按优先级选择：`media_id`，否则 `sha256`，否则 `relative_path`。同键记录按相对路径字典序选择 canonical 路径，其余路径进入 `aliases`。总览页面只显示 canonical 媒体，避免重复下载副本占用页面，但详情保留别名和全部证据结果。

## 产物契约

`review_report.json` 保留原有 `results`、`contact_sheet` 和统计字段，新增：

- `media_details`：每项包含 `media_id`、`relative_path`、`aliases`、`sha256`、`media_type`、候选主题字段、`timepoints` 和可选 `detail_output`。
- `overview_pages`：每页包含 `page`、`item_count`、`relative_paths`、`media_ids`、`output`。
- `theme_pages`：每页额外包含 `candidate_theme`，其余字段与总览页一致。

输出目录：

- `overview/page-NNN.jpg`、`overview/index.json`
- `themes/<theme>/page-NNN.jpg`、`themes/index.json`
- `media/<safe-id>.jpg`

默认页大小为 64 个 canonical 媒体，CLI 可通过 `--page-size` 覆盖。

## 视觉与证据边界

分页图和主题页只用于筛选样本。文件名关键词不能证明画面主题；代表帧不能单独证明完整动画规律；展示画面不能推出唯一 Unity 制作方式。失败证据点必须在 `media_details.timepoints` 中保留。

## 验收

- 页面以媒体为边界，不拆散同一媒体的时间点。
- canonical 媒体覆盖所有有复核结果的媒体，别名不额外占总览格。
- `unclassified` 主题页存在。
- 页面和详情图非空，报告仍准确记录 8,798/8,707/91 的机器统计。
- 完整 unittest 通过，输入目录快照不变。
