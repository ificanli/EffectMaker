# VFX.library 阶段总结与下一阶段入口

## 1. 任务目标

将 `E:/BaiduNetdiskDownload/VFX.library` 中的 GIF/视频资料纳入特效学习知识库，使其未来可以作为视觉灵感、设计参考和 Unity 实验候选，而不是简单复制或逐个复刻。

由于这是第一次处理纯特效 GIF/视频资料，本任务采用独立于课程点评的媒体证据链：先扫描和索引，再自动抽取代表帧，最后通过连续画面复核建立视觉知识。

## 2. 已完成工作

### 媒体扫描和索引

- 发现输入文件：20,350 个。
- 支持的 GIF/视频媒体：2,934 个。
- 总大小：29,428,894,935 字节。
- 内容哈希重复组：1,461。
- 规范化名称重复组：1,169。
- 探测错误：0。
- 输入目录扫描前后快照一致。
- 外部目录保持只读，未发生复制、移动、改名、删除或修改。

### 自动代表帧复核

自动流程读取现有 `manifest.jsonl` 和 `evidence_manifest.jsonl`，使用 FFmpeg 批量生成代表帧和联系表。

最终结果：

```text
evidence_count: 8798
successful_evidence_count: 8707
failed_evidence_count: 91
status: partial
```

产物：

- 报告：`workspace/data/resource_index/vfx_library/review/review_report.json`
- 代表帧：`workspace/data/resource_index/vfx_library/review/frames/`
- 联系表：`workspace/data/resource_index/vfx_library/review/contact_sheet.jpg`

自动流程具备：

- 单线程 PNG 输出，规避部分 GIF 的 MJPEG 编码失败。
- `end` 时间点失败时使用 `-sseof -0.1` 回退。
- 成功输出复用，支持增量重跑。
- 逐条记录命令、返回码、输出路径和失败原因。
- 单张坏图跳过，不阻断联系表生成。

### 测试和任务管理

- 完整 Python 测试：77 项通过。
- 复核门禁：通过，结果为 `partial 8707 91`。
- 自动化任务 `vfx-6xl` 已关闭。
- 新阶段任务 `vfx-344` 已创建并认领。

## 3. 当前知识状态

来源：`SRC-2026-VFXLIB-001`

- 来源状态：`experimental`
- 当前实验：`EXP-2026-067`
- 实验状态：`partial`
- 现有卡片：`AESTHETIC-2026-057`，仅作为文件名关键词候选的低证据参考。

当前自动结果只证明：

- 文件存在或可被索引。
- 指定时间点部分可被抽取。
- 代表帧和失败原因可以被机器记录。

当前自动结果不能证明：

- 文件名关键词与实际画面一致。
- 某个效果确实属于火焰、水、雷电或其他主题。
- 画面存在稳定的形体、层级、节奏、颜色或空间规律。
- 可以从展示画面直接推出唯一的 Unity 制作方法或参数。
- 外部素材具备可再分发授权。

## 4. 为什么需要下一阶段

代表帧流水线解决了“能不能批量读取和留证”的问题，但还没有完成“从画面归纳知识”的问题。

下一阶段必须把分析对象从单个文件改成去重后的视觉样本组，并对高价值样本保留起始、中段和结束等多个时间点。机器可以提出候选描述，但只有连续画面复核后，才允许写入高置信度审美规律。

## 5. 下一阶段任务

任务 ID：`vfx-344`

任务标题：`VFX.library视觉知识吸收第一批复核`

执行顺序：

1. 按内容哈希、规范化名称和候选聚类压缩视觉样本。
2. 从每个优先样本生成 `start/quarter/middle/three-quarter/end` 多时间点证据包。
3. 对高价值主题生成机器候选描述。
4. 对候选样本进行连续画面核对，确认主题、形态、层级、节奏、颜色和空间。
5. 形成绑定 `relative_path`、`sha256`、时间点和置信度的审美观察。
6. 记录反例、失败点和授权未知项。
7. 对达到 `high` 置信度且与 Unity 学习交集明确的规律，另建最小实验。
8. 只有实验支持后，才将知识升级为 `verified`；跨样本稳定且已沉淀后才考虑 `absorbed`。

第一批优先主题：火焰、雷电、水、刀光、烟雾、能量爆发。第一批不追求覆盖全部媒体，而追求验证流程和建立可复用的高质量样例。

## 6. 第一批执行结果

第一批已按内容 SHA-256 去重，从 `fire`、`lightning`、`water`、`slash`、`smoke`、`energy` 六个候选主题各选最多 5 个样本：

- 去重样本：30 个
- 多时间点证据：150 个
- 成功抽帧：147 个
- 失败抽帧：3 个
- 批次状态：`partial`
- 参考声明：`reference_only=true`

批次产物：

- `workspace/data/resource_index/vfx_library/visual_package_batch1/visual_package.json`
- `workspace/data/resource_index/vfx_library/visual_package_batch1/evidence_manifest.jsonl`
- `workspace/data/resource_index/vfx_library/visual_package_batch1/review/review_report.json`
- `workspace/data/resource_index/vfx_library/visual_package_batch1/review/frames/`
- `knowledge/sources/SRC-2026-VFXLIB-001/visual_review_batch1.md`

3 个失败点已保留原始命令和回退命令，没有作为连续画面证据使用。

## 7. 视觉标准边界

VFX.library 中的效果不一定制作得好，也不应被当作审美标准、质量标准、风格目标或正确实现。它们只作为参考、灵感和反例来源。后续每条观察都要区分：

- 哪个局部结构可以借鉴。
- 哪些部分不适合当前目标。
- 是否存在明显粗糙、失衡或不完整之处。
- 这个素材与当前项目需求有什么差异。

不能因为素材被收录，就默认它值得追随；也不能因为素材完成度低，就否定其中可能有用的局部节奏、形体或层级。

## 8. 当前视觉复核阻塞

第一批 PNG 已生成，但当前会话中的直接图像读取和本地浏览器截图均未返回可供可靠判读的画面内容。因此尚未确认：

- 文件名主题是否与画面一致。
- 起始、中段、结束之间发生了什么视觉变化。
- 哪些形体、层级、节奏、颜色或空间特征可以跨样本归纳。
- 哪些部分应当明确记录为不采用或反例。

当前不能创建新的高置信度 `AESTHETIC-*` 卡片，也不能启动基于这些样本的 Unity 实验。连续画面视觉复核任务 `vfx-2i7` 当前暂停，来源保持 `experimental`，批次保持 `partial`。已关闭的 `vfx-430` 仅代表分页视觉索引与媒体证据详情完成，不代表连续视觉知识吸收完成。

## 11. 当前暂停状态

根据最新 Agents/Beads 规范，真正的连续画面视觉复核暂时暂停，不关闭来源、不删除产物、不修改外部目录。

- 暂停任务：`vfx-2i7`（暂停：VFX.library连续画面视觉复核）
- 已完成分页索引任务：`vfx-430`，已关闭
- 已完成：全库分页媒体索引、候选主题页、单媒体多时间点详情、第一批 30 样本/150 时间点证据包、复核队列、本地复核插件。
- 已验证：FFmpeg 抽帧、Pillow 首帧读取、HTTP `/api/manifest`、首帧 URL、`/health` 健康检查、插件测试 8/8。
- 暂停原因：当前会话浏览器 WebView 返回 `browser guest not attached (webview not ready)`，无法可靠呈现画面；不能用文件存在性、HTTP 成功或客观统计替代视觉判读。
- 当前状态：来源 `experimental`，批次 `partial`；未创建新的高置信度 `AESTHETIC-*`，未启动 Unity 实验，未升级 `verified/absorbed`。

恢复入口：

`workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json`

恢复时启动本地服务并从队列首项开始，观察必须绑定 `relative_path`、`sha256`、时间标签、可借鉴点、局限、反例和置信度。素材继续只作为参考、灵感和反例，不作为审美标准。

在视觉读取工具恢复稳定前，已增加一层客观量化筛选：对第一批 147 张成功 PNG 记录尺寸、透明比例、RGB 均值、亮度均值和样本内亮度范围，产物为：

`workspace/data/resource_index/vfx_library/visual_package_batch1/triage/triage_report.json`

该报告状态为 `triage-only`，只用于发现抽帧异常、安排后续查看顺序和筛选需要重点检查的样本。它不产生审美评分、不判断素材好坏、不评价原创性，也不把任何素材设为审美标准。

基于该量化报告和批次抽帧结果，已生成视觉复核队列：

`workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json`

队列状态为 `review-queue`，包含 30 个去重样本和 6 个文件名候选主题。优先级只反映失败证据、缺失时间点、亮度变化信号和主题覆盖入口，用于安排连续画面查看顺序，不是质量排名、审美排名或推荐列表。

## 10. 分页视觉索引阶段

为解决旧版 `contact_sheet.jpg` 只展示前 256 个成功帧、无法覆盖全库的问题，已建立分页视觉索引任务 `vfx-430`，并完成真实数据运行。

- canonical 媒体：1,463 个；同内容别名不重复占总览格。
- 媒体总览：23 页，入口为 `workspace/data/resource_index/vfx_library/review/overview/index.json`。
- 文件名主题候选：31 页，入口为 `workspace/data/resource_index/vfx_library/review/themes/index.json`，包含 13 个候选主题和 `unclassified`。
- 单媒体详情：`workspace/data/resource_index/vfx_library/review/media/`，保留成功与失败时间点。
- 页大小：每页最多 64 个 canonical 媒体。
- 机器统计保持不变：8,798 个证据点、8,707 个成功、91 个失败，报告状态仍为 `partial`。
- 输入目录前后快照一致，外部来源保持只读。

分页索引只用于浏览、去重和选择后续复核样本。文件名主题仍是候选标签，不是画面事实；本阶段没有创建新的高置信度审美卡片，没有启动 Unity 实验，也没有把来源升级为 `verified` 或 `absorbed`。

下一步应从主题候选页和 `unclassified` 页中选择高价值样本，核对连续画面并记录 `relative_path`、`sha256`、时间点、可借鉴点、局限、反例和置信度。
