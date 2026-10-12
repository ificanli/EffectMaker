# VFX.library 视觉知识吸收流程

## 目的

将 `E:/BaiduNetdiskDownload/VFX.library` 中的 GIF/视频资料，从机器可读取的媒体索引逐步转化为带证据、可检索、可用于启发和实验的视觉知识。

本流程不要求逐个复刻全部素材，也不把文件名、单帧或机器标签直接当作视觉事实。素材只作为参考、灵感和反例来源，不代表制作质量、审美标准、风格目标或正确实现。目标是先压缩样本，再确认连续画面规律，最后选择少量高价值规律进入 Unity 最小实验。

## 当前输入

- 来源：`SRC-2026-VFXLIB-001`
- 媒体清单：`workspace/data/resource_index/vfx_library/manifest.jsonl`
- 证据清单：`workspace/data/resource_index/vfx_library/evidence_manifest.jsonl`
- 自动复核报告：`workspace/data/resource_index/vfx_library/review/review_report.json`
- 成功代表帧：`workspace/data/resource_index/vfx_library/review/frames/`
- 联系表（兼容入口）：`workspace/data/resource_index/vfx_library/review/contact_sheet.jpg`
- 媒体级总览分页：`workspace/data/resource_index/vfx_library/review/overview/index.json`
- 文件名主题候选分页：`workspace/data/resource_index/vfx_library/review/themes/index.json`
- 单媒体多时间点详情：`workspace/data/resource_index/vfx_library/review/media/`

当前机器复核结果为 8,707/8,798 个证据点成功，91 个证据点失败，报告状态为 `partial`。

## 总体流水线

```text
媒体索引
→ 内容去重与样本组选取
→ 多时间点证据包
→ 机器候选描述
→ 连续画面复核
→ 带证据的审美观察
→ 跨样本归纳
→ Unity 最小实验
→ verified / absorbed
```

## 1. 去重和样本组选取

以内容 SHA-256 为第一层去重依据，以规范化文件名、媒体元数据和候选聚类为第二层归组依据。

每个视觉样本组选择一个主样本，优先级如下：

1. 代表帧抽取成功率高。
2. 时长、帧数和分辨率信息完整。
3. 画面质量较高且没有明显损坏。
4. 能代表该组，而不是只因文件名更醒目。

完全相同的文件不重复进入视觉复核。不同编码、分辨率或下载副本只有在画面可能存在差异时才保留对照。

## 2. 多时间点证据包

对每个入选样本生成固定时间点证据：

- `start`
- `quarter`
- `middle`
- `three-quarter`
- `end`

短 GIF 或无法可靠获得时长的媒体，可以保留 `representative`，但只能支持低置信度观察。

证据包至少包含：

- 代表帧 PNG
- 相对路径
- SHA-256
- 时间点或帧号
- 原始抽帧命令
- 抽帧返回码
- 输出文件大小
- 失败原因或回退命令

## 3. 机器候选描述

机器分析只输出候选，不直接建立稳定知识。候选字段包括：

- 可能主题：火焰、雷电、水、烟雾、能量、刀光等
- 主体形态：球状、带状、环状、柱状、爆炸状、拖尾状
- 视觉层级：亮芯、主体、边缘、烟雾、冲击、残留
- 节奏结构：蓄力、爆发、持续、回缩、消散
- 颜色关系：主色、亮芯色、边缘色、背景对比
- 空间关系：平面、体积、路径运动、地面反馈

候选描述必须绑定证据帧，不能只引用文件名。

## 4. 连续画面复核

高价值候选至少核对起始、中段、结束三处画面。复核重点：

1. 主题是否真的出现在画面中。
2. 主体形态是否在时间过程中保持或有明确变化。
3. 层级是否能在多个时间点观察到。
4. 节奏是否能描述为先后关系，而不是单帧猜测。
5. 颜色和空间关系是否稳定。
6. 是否存在反例、遮挡、循环动画或镜头误导。

观察记录必须引用 `relative_path`、`sha256`、标签和时间点。

## 5. 证据等级

- `low`：只有文件名、聚类或单帧支持。
- `medium`：多帧支持一个候选描述，但样本数量不足或存在明显歧义。
- `high`：连续画面和多个样本支持同一视觉规律，并记录了反例或适用范围。
- `verified`：高置信度视觉规律已经通过 Unity 最小实验验证。
- `absorbed`：规律、限制和实验结果已进入稳定知识库，可用于后续设计检索。

`partial` 是机器处理状态，不等于视觉规律已经成立。

## 6. 建卡规则

### AESTHETIC 卡片

只记录视觉规律，例如：

- 爆发由亮芯、外扩主体和延迟残留组成。
- 刀光由支撑层、主体层和冲击层形成方向节奏。
- 水效果通过前摇、爆发和回落形成时间结构。

每条结论必须包含：

- 规律描述
- 支持样本
- 代表帧和时间点
- 置信度
- 反例或未知项
- 适用范围

### CRAFT 卡片

只有存在明确操作、参数、工程证据或 Unity 实验时才建立。不能从展示画面反推唯一制作方法。

## 7. 第一批执行范围

不要一次分析全部媒体。第一批按候选聚类选择 10 个高价值主题，每个主题选择 5 至 10 个样本，优先选择与现有 Unity 学习内容有交集的：

- 火焰
- 雷电
- 水
- 刀光
- 烟雾
- 能量爆发

第一批的通过条件：

- 每个入选样本有多时间点证据包。
- 每个主题完成连续画面观察。
- 至少形成一批带证据和置信度的 `AESTHETIC-*` 观察。
- 明确记录失败项、反例和授权未知状态。
- 不把未验证内容标记为 `verified` 或 `absorbed`。

## 8. Unity 最小实验

只有当某条视觉规律达到 `high`，并且与当前 Unity 目标环境有明确交集时，才设计实验。

每个实验只验证一个关键假设，例如：

- 三段式爆发节奏是否能由亮芯、外扩层和残留层实现。
- 刀光支撑层、主体层和冲击层是否能形成清晰方向感。
- 雷电主路径、分叉和消散是否能保持视觉层级。

实验记录 Unity 版本、渲染管线、参数、截图、日志、性能数据和失败原因。

## 9. 自动化边界

可以自动化：

- 去重和样本选择候选
- 多时间点抽帧
- 联系表生成
- 颜色、变化幅度和透明区域等统计
- 候选标签生成
- 证据索引和失败队列

不能仅靠自动化确认：

- 画面主题是否与标题一致
- 最终视觉规律是否成立
- 具体 Unity 制作参数
- 规律是否具有跨样本普遍性
- 外部素材的作者、平台和授权状态

## 10. 失败处理

- 抽帧失败：保留原始命令、回退命令和错误，不删除证据点。
- 连续画面不足：状态保持 `low` 或 `medium`。
- 标题与画面不一致：记录为反例，不修改原始文件名。
- 主题无法确认：保留机器候选，禁止升级为事实。
- 授权未知：只记录内部引用和元数据，不对外分发素材。
- Unity 无法验证：记录环境、资源或工具限制，状态保持 `experimental` 或 `无法验证`。

### 视觉展示门禁

本流程的连续画面复核必须遵守统一规范中的“视觉可见性标准”（见《教学复现与 Unity 特效验证规范》）：复核前先用一张已知标准化 PNG 做展示 smoke test；只有展示通道实际呈现画面、当前会话能够描述画面内容、文件和时间点可追溯三项同时成立，才能保存人工观察。浏览器页面加载成功、HTTP 200、文件可解码或机器统计都不能替代观看。展示宿主未附着或图片内容未返回时，状态保持 `blocked_environment`，不得升级为 `verified`，也不得据此开始视觉结论驱动的参数迭代。


当直接图像读取或浏览器截图不稳定时，使用本地复核服务读取已经生成的标准化 PNG，不直接让浏览器解码外部 GIF/视频：

```bash
python -m workspace.tools.vfx_library_index.review_server_cli \
  --queue workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json \
  --review workspace/data/resource_index/vfx_library/visual_package_batch1/review/review_report.json \
  --frames workspace/data/resource_index/vfx_library/visual_package_batch1/review/frames \
  --observations workspace/data/resource_index/vfx_library/visual_package_batch1/observations.jsonl \
  --host 127.0.0.1 --port 8765
```

浏览器访问 `http://127.0.0.1:8765/`。界面提供样本切换、`start/quarter/middle/three-quarter/end` 时间点、播放、逐帧和观察保存。观察字段包括主题状态、可借鉴点、局限、不采用理由、反例和置信度，并绑定队列中的 `relative_path`、`sha256` 和时间标签。

该服务只读取工作区内已生成的队列和帧目录，只向工作区写入观察 JSONL，不修改 `E:/BaiduNetdiskDownload/VFX.library`。服务默认只监听 `127.0.0.1`。界面不提供质量分数、审美排名或推荐字段；观察仍需人工判读后才能形成知识卡片。

## 11. 任务入口

- 已完成分页任务：`vfx-430`，标题为“VFX.library 分页视觉索引与媒体证据详情”。该任务只代表全库分页索引、主题候选页和媒体详情已生成，不代表连续画面视觉知识吸收完成。
- 当前暂停任务：`vfx-2i7`，标题为“暂停：VFX.library连续画面视觉复核”。暂停原因是当前显示宿主无法可靠呈现连续画面。
- 恢复入口：`workspace/data/resource_index/vfx_library/visual_package_batch1/review_queue.json`。

恢复前不启动新的视觉观察或 Unity 实验；恢复后必须先确认浏览器或替代显示通道实际呈现连续帧，再记录绑定 `relative_path`、`sha256`、时间标签和置信度的观察。任务完成前，不关闭来源实验，不把来源状态升级为 `verified`，也不修改外部素材目录。
