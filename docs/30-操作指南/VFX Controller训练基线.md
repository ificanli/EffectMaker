# VFX Controller 训练基线

## 定位

VFX Controller 是神经网络式 VFX 系统的规划层。它读取 Prompt、Prefab 结构、材质与 Shader 摘要、Unity 运行证据和人工反馈，输出受 Schema 约束的 `VFXSpec`、`MutationSpec` 或工具调用计划。

它不直接输出未经验证的 `.prefab`、Unity YAML、Mesh、Texture 或 Shader 文件。资产生成仍由特效族适配器、程序化生成器、专用生成模型和 Unity 执行器负责。

## MiniMind 参考边界

可借鉴：

- Pretrain、SFT、LoRA、DPO 和自动奖励的阶段划分；
- JSONL 数据加载、checkpoint、断点续训、DDP 和训练日志；
- `chosen/rejected` 偏好训练思想；
- MiniMind-V 的冻结视觉编码器、Projector 和部分语言层微调模式。

不可直接照搬：

- 文本 `chosen/rejected` 不能替代 Unity 候选、连续帧和依赖证据；
- MiniMind-V 是图像理解到文本，不是 VFX 资产生成；
- 技术执行通过不能成为审美或 Prompt 正例；
- “无法判断”不能成为负例或默认正例。

## 数据层

### Prefab Corpus

`workspace.tools.vfx_generation.vfx_prefab_corpus` 读取一个或多个摄入后的 `source_manifest.json`，生成：

- `prefab_records.jsonl`；
- `split_assignments.jsonl`；
- `failures.jsonl`；
- `corpus_manifest.json`。

切分使用 Prefab 内容哈希作为优先分组键。相同 Prefab 即使来自不同批次，也必须进入同一 train / validation / test split，防止内容泄漏。

### Controller Dataset

`workspace.tools.vfx_generation.vfx_controller_dataset` 将 Unity 组合或变异结果与人工 Prompt 条件标签合并，生成：

- 带完整 provenance 的 `controller_examples.jsonl`；
- MiniMind-compatible `minimind_sft.jsonl`；
- `controller_exclusions.jsonl`；
- `controller_dataset_manifest.json`。

### 课程资料接入

课程视频、字幕、视觉观察、知识卡片和制作实验先经过
`workspace.tools.vfx_generation.course_knowledge_adapter`，再通过
`--course-adapter-manifest` 接入 Controller 数据集。课程资料在这里扮演的是
**可追溯的制作先验**，不是生成结果标签：

```text
knowledge/sources + knowledge/cards + knowledge/experiments
  -> course_knowledge_index.json
  -> vfxspec_priors.jsonl / controller_candidates.jsonl
  -> vfx_controller_dataset --course-adapter-manifest
  -> controller_examples.jsonl
```

典型命令：

```powershell
python -m workspace.tools.vfx_generation.course_knowledge_adapter index `
  --input knowledge/sources `
  --input knowledge/cards `
  --input knowledge/experiments `
  --output-dir workspace/data/vfx_generation/course_knowledge/course_knowledge_<id> `
  --index-id course_knowledge_<id>

python -m workspace.tools.vfx_generation.course_knowledge_adapter export `
  --index workspace/data/vfx_generation/course_knowledge/course_knowledge_<id>/course_knowledge_index.json `
  --output-dir workspace/data/vfx_generation/course_knowledge/course_controller_adapter_<id> `
  --adapter-id course_controller_adapter_<id>

python -m workspace.tools.vfx_generation.vfx_controller_dataset `
  --course-adapter-manifest workspace/data/vfx_generation/course_knowledge/course_controller_adapter_<id>/course_controller_adapter_manifest.json `
  --output-dir workspace/data/vfx_generation/datasets/course_controller_<id> `
  --dataset-id course_controller_<id>
```

接入后的课程样本会以 `source_kind=course_prior` 进入 Controller 审计，保留课程记录、原文摘录、来源文件、行号、时间码和
先验 VFXSpec 路径；它们会明确写入排除清单，不会进入 `minimind_sft.jsonl`。课程先验要变成正向 Controller 样本，仍必须有
对应 Unity 复现、真实连续帧、干净的技术审计、人工 Prompt 条件评价和人工整体质量结论。课程中的
`unverified_assumption`、`无法判断`、未完成复现和只有静态文件证据的内容不能绕过这道门禁。

当前已生成的课程适配底座位于：

```text
workspace/data/vfx_generation/course_knowledge/course_knowledge_r003/
workspace/data/vfx_generation/course_knowledge/course_controller_adapter_r003/
workspace/data/vfx_generation/datasets/course_controller_r003/
```

其中 r003 只保留 `EXP-2026-004` 的烟花分层工程映射作为待复现先验；`EXP-2026-105` 的刀光审计因“不是已验证模板、尚未完成复现”进入排除清单。课程资料仍不能直接宣称模型已经学会课程。

只有同时满足以下条件的样本才进入 Controller SFT：

1. Unity 技术执行通过；
2. 有真实连续帧；
3. 资源审计干净；
4. Prompt 每个条件都有人类明确判断；
5. 人工“整体”结论为“符合”；
6. `positive_generation_supervision=true`。

“部分符合”“不符合”“无法判断”以及未保存反馈均不进入正向 SFT。它们可以保留为诊断、条件监督或未来偏好对来源，但不能作为成功输出教给 Controller。

## 训练门禁

`workspace.tools.vfx_generation.vfx_controller_train` 提供训练预检。当前默认门槛：

- 至少 32 个完整人工确认的正向 SFT 样本；
- 至少覆盖 2 个特效族；
- 数据集 manifest 的训练门禁必须为 `ready`。

门槛不满足时，命令只写 `training_preflight.json`，返回失败且不写任何模型权重。

这只是首轮 smoke 门槛，不是正式发布门槛。正式模型还必须按来源、Prefab 内容、Material/Shader 共享组和独立 Unity run 分组评估。

## Prompt 条件评分器

`workspace.tools.vfx_generation.prompt_condition_scorer` 是独立的 VFX Judge 条件评分器基线。它从真实多帧截图提取可解释序列特征，分别为风格、主色、特效类别、节奏、无长拖尾和整体训练分类器。

```powershell
python -m workspace.tools.vfx_generation.prompt_condition_scorer build `
  --overlay <prompt-condition-overlay.jsonl> `
  --output-dir workspace/data/vfx_generation/datasets/vfx_prompt_condition_scorer_<id> `
  --dataset-id vfx_prompt_condition_scorer_<id>

python -m workspace.tools.vfx_generation.prompt_condition_scorer train `
  --dataset-manifest <scorer_dataset_manifest.json> `
  --output-dir workspace/data/vfx_generation/models/vfx_prompt_condition_scorer_<id>
```

每个条件默认至少需要三个类别（符合、部分符合、不符合）各 4 条样本，并来自至少 2 个独立评价组。`无法判断` 被完全排除，不是一个训练类别。评分器输出只能作为候选排序和人工复核辅助，不能替代人工结论或 Unity 运行验证。

## 模型分工

```text
Prompt / 历史证据
  -> VFX Controller / Planner
  -> VFXSpec / MutationSpec / Tool Plan
  -> 特效族适配器
  -> Mesh / Texture / Shader / Particle 生成
  -> Unity 真实运行
  -> VFX Judge + 技术门禁
  -> 人工反馈
  -> 下一轮训练
```

Controller、视觉评分器、Mesh/Texture/Shader 生成器和 Unity 执行器是不同模块，不应强行合并为一个小语言模型。
