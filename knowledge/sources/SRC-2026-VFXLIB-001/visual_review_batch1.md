# VFX.library 第一批视觉证据包记录

## 批次定位

- 任务：`vfx-344`
- 来源：`SRC-2026-VFXLIB-001`
- 批次：第一批视觉知识吸收候选
- 生成日期：2026-08-25
- 参考声明：本批素材仅作为参考、灵感和反例来源，不代表制作质量、审美标准、风格目标或正确实现。

## 样本范围

按候选主题从 `assignments.jsonl` 选择样本，并按 `sha256` 去重：

- `fire`
- `lightning`
- `water`
- `slash`
- `smoke`
- `energy`

每个主题最多 5 个样本，共 30 个去重样本。每个样本优先生成：

- `start`
- `quarter`
- `middle`
- `three-quarter`
- `end`

## 产物

- 候选包：`workspace/data/resource_index/vfx_library/visual_package_batch1/visual_package.json`
- 批次证据清单：`workspace/data/resource_index/vfx_library/visual_package_batch1/evidence_manifest.jsonl`
- 批次抽帧报告：`workspace/data/resource_index/vfx_library/visual_package_batch1/review/review_report.json`
- 批次 PNG：`workspace/data/resource_index/vfx_library/visual_package_batch1/review/frames/`

## 机器结果

```text
样本数：30
证据点：150
成功：147
失败：3
状态：partial
reference_only：true
```

失败证据点：

1. `images/KF6ZLKO1PAMIO.info/mark-khalil-smoke-01(1).gif` 的 `end`
2. `images/KDPOJBVLILA6K.info/Flash FX Animation 10 Energy Strikes(1).gif` 的 `three-quarter`
3. `images/KDPOJBVLILA6K.info/Flash FX Animation 10 Energy Strikes(1).gif` 的 `end`

失败项保留原始命令、回退命令和错误，不作为连续画面证据使用。

## 当前可得结论

- 已经建立了第一批去重样本的多时间点观察入口。
- 147 个时间点可以被机器抽取并定位到 `relative_path`、`sha256`、主题候选和时间标签。
- 文件名主题仍然只是候选标签，尚未确认与画面一致。
- 还没有完成连续画面的视觉判读，因此尚未形成高置信度审美规律。
- 还没有从这些素材推出 Unity 参数或唯一制作方法。

## 参考边界

本批素材不用于建立审美排名，也不作为“做得好”的标准。某个素材可以同时作为：

- 形体或节奏的灵感来源。
- 可拆解的结构样例。
- 失败、粗糙或不适合当前目标的反例。
- 用来比较取舍的对照样本。

后续观察必须分别记录：

- 可借鉴的局部结构。
- 不适合采用的部分。
- 与当前项目目标的差异。
- 观察置信度和证据范围。

## 客观量化筛选

在视觉画面无法稳定读取的情况下，已对 147 张成功 PNG 生成客观量化报告：

- 报告：`workspace/data/resource_index/vfx_library/visual_package_batch1/triage/triage_report.json`
- 覆盖样本：30
- 可分析帧：147
- 不可用或失败帧：3
- 状态：`triage-only`
- `reference_only=true`

当前记录的信号包括画面尺寸、透明像素比例、非透明像素比例、RGB 均值、亮度均值和样本内亮度范围。这些数据只用于筛选异常、排序后续查看顺序和定位可能的抽帧问题，不用于评价效果质量、审美价值、原创性或是否值得模仿，也不构成审美标准。

## 视觉复核队列

已基于证据完整性和异常信号生成复核队列：

- 队列：`workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json`
- 状态：`review-queue`
- 样本：30
- 候选主题：6
- 排序信号：抽帧失败、时间点缺失、亮度变化异常和主题覆盖入口。

该队列只安排后续查看顺序，不评价效果好坏、质量、原创性或审美价值。文件名主题在连续画面复核前仍只是候选标签。

## 视觉判读状态

量化结果不能替代连续画面观察。文件名主题仍未被画面确认，尚未形成高置信度审美规律，也未启动 Unity 实验。

当前按最新 Agents 规范暂停：

- 暂停任务：`vfx-2i7`（暂停：VFX.library连续画面视觉复核）。
- 已完成分页任务：`vfx-430` 仅代表分页索引与媒体证据详情完成，不代表视觉知识吸收完成。
- 来源保持 `experimental`，本批次保持 `partial`。
- 恢复入口：`workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json`。
- 暂停期间不启动本地复核服务、不生成视觉观察、不创建高置信度 `AESTHETIC-*`、不启动 Unity 实验，也不升级 `verified/absorbed`。
- 恢复时只有在显示通道实际呈现连续画面后，才可按队列记录绑定 `relative_path`、`sha256`、时间标签、可借鉴点、局限、反例和置信度的观察。

