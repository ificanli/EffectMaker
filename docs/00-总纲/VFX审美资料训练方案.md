# VFX 审美资料训练方案

## 方案定位

本文是 `vfx-2df.29` 的跨特效审美训练方案，负责回答：审美点评、参考视频、课程卡片、Unity 连续帧和人工反馈，如何变成可以训练的 Judge、偏好排序器和 Controller 监督数据。

本文不把“资料已经被索引”写成“模型已经学会”，也不把“技术上能播放”写成“审美上合格”。审美资料的正确作用顺序是：

```text
专业审美资料
  -> 专业来源与授权核验
  -> 可定位的动态帧/时间码
  -> 专家明确规则、成品/过程对照
  -> Unity复刻交叉验证
  -> 专业Teacher标签与成对偏好
  -> VFX Judge / Preference Ranker
  -> Controller 的约束和监督
  -> 下一轮 VFXSpec / MutationSpec
```

当前状态：`in_progress`。用户明确不是专业特效师，只负责判断特效用途和是否可播放，不提供主体、层次、节奏、材质、构图、风格或 A/B 审美真值。历史 47 条非专业多维评价和其训练出的 Judge 仅保留为实验记录，不再用于正式晋级。新审美教师由专业视频、教程、专家点评、成品/过程对照和 Unity 复刻证据构建；AI 判断在专业数据门禁通过前只能标记为假设。

## 2026-09-03 训练边界修订

- 非专业用户：只标注 `effect_function`、`playability` 和备注。
- 专业资料教师：负责 quality、style、core_readability、layer_separation、rhythm、material、composition 和偏好。
- 教程字幕：只能作为定位和规则候选，不能直接成为质量分。
- 专业成品：只能作为正向参考分布，不能仅因来源知名就标记为高分。
- 专家明确点评或前后对比：绑定动态帧和时间码后可成为 Teacher 候选。
- Unity 复刻：验证规则在目标 Unity 2022/URP 工程中的可迁移性；复刻失败不能自动证明规则错误。
- 模型晋级：必须使用与训练隔离的专业回归集，语义用途标签不能替代审美回归。

## 一、训练对象分工

审美训练不是一个模型承担所有工作，而是拆成三个训练产品和一个知识层：

| 对象 | 输入 | 输出 | 训练资料 | 当前边界 |
|---|---|---|---|---|
| 审美知识层 | 点评文字、视频讲解、知识卡片、前后对照 | 规则、问题类型、适用条件、失败模式 | 有来源和时间点的资料 | 先作为结构化先验，不直接作为画面质量标签 |
| VFX Judge | Prompt、风格、Prefab摘要、Unity连续帧 | 多维质量、风格匹配、问题和置信度 | 专家规则、教程前后对比、专业参考和验证过的Unity复刻 | 非专业用户不提供审美标签 |
| Preference Ranker | 同Prompt同族候选对、特征差异 | 候选排序、偏好原因和下一轮方向 | 专家明确偏好、教程前后对比和验证过的专业Teacher对 | 只在可比候选之间排序，不能替代最终验收 |
| VFX Controller | Prompt、资源上下文、审美规则、Judge和偏好结果 | VFXSpec、MutationSpec、Tool Plan | 已验证成功候选和偏好对 | 只规划结构和工具调用，不直接写Unity资产 |

审美资料本身不能直接训练 Mesh、Texture、Shader 或 Prefab 生成器。它们为这些生成器提供目标风格、质量约束和筛选奖励；资产生成仍由特效族适配器、专用生成器和 Unity 执行器负责。

## 二、资料如何转成训练数据

### 1. 原始资料层

输入包括：

- `knowledge/sources/` 中的点评视频、参考视频、字幕、抽帧和视觉复核记录；
- `knowledge/cards/` 中的 `AESTHETIC-*` 审美卡片；
- `knowledge/experiments/` 中的 Unity 复现和失败实验；
- `workspace/data/vfx_generation/runs/` 中的真实连续帧、自动评价和运行证据；
- 人工评价页面保存的风格、质量、层职责、问题、备注和候选偏好。

这一层只说明资料来源，不产生训练标签。文件名、字幕、单张截图、文件存在、来源 Prefab 的目录名都不能单独证明质量。

### 2. 证据层

每条可用证据必须至少绑定以下信息：

```json
{
  "evidence_id": "stable-id",
  "source_kind": "course_review|reference_video|unity_run|human_feedback",
  "source_path": "knowledge/sources/...",
  "sha256": "when_media_is_available",
  "effect_family": "slash|fire|lightning|shield|smoke|explosion|...",
  "style_family": "realistic|cartoon|anime|stylized|...",
  "timecodes": ["00:10-00:20"],
  "frame_paths": ["..."],
  "visibility_status": "visible|not_visible|blocked_environment",
  "evidence_status": "observed|inferred|unverified|verified"
}
```

`not_visible`、`blocked_environment`、没有独立画面和无法稳定定位的内容只能保留为排除或待复核记录，不能作为审美正例或审美负例。

### 3. 结构化观察层

审美点评需要拆成“画面事实”和“评价解释”：

```json
{
  "observation_id": "obs-001",
  "evidence_id": "stable-id",
  "observation": "主体轮廓在峰值前已经清晰建立",
  "rule_candidate": "主体先成立，亮边和命中层延后出现",
  "axes": ["core_readability", "rhythm", "layer_separation"],
  "positive_or_negative": "positive_example|negative_example|neutral",
  "confidence": "high|medium|low",
  "requires_unity_validation": true,
  "status": "observation_only"
}
```

“规则候选”不是“模型标签”。只有当画面证据、人工判断和 Unity 复现互相支持后，规则才可以升级为可迁移知识。

### 4. 专业 Teacher 标签层

专业资料中的专家明确结论、成品/过程对照和 Unity 复刻验证是审美监督核心。质量字段继续沿用统一结构，但必须增加专业来源、时间码、证据等级和复刻状态；非专业用途反馈不进入这些字段：

```text
style_family
style_keywords
quality_score
core_readability
layer_separation
rhythm
material
composition
layer_roles
reusable_layers
issues
summary
notes
```

训练时还要区分三种状态：

| 状态 | 是否进入审美正向训练 | 说明 |
|---|---:|---|
| 专家明确结论绑定动态证据 | 可以作为 Teacher 候选 | 仍需来源和跨项目验证 |
| 教程明确前后对比 | 可以形成偏好候选 | 前后画面、时间码和修改项必须对应 |
| 未保存 AI 草稿 | 不可以 | 只能作为界面草稿，不能当人工结论 |
| 无法判断/不可见 | 不可以 | 进入排除或待复核，不作为质量负例 |
| 技术失败/上下文缺失 | 不可以作为审美负例 | 进入技术路由，例如缺失脚本、挂点或镜头不适配 |

## 三、审美标签体系

### 通用质量维度

所有特效族共享评价字段结构，但每个族必须用自己的画面定义和人工标签：

| 字段 | 范围 | 判断问题 |
|---|---:|---|
| `core_readability` | 0-5 | 主体是否一眼可读，轮廓、方向和焦点是否成立 |
| `layer_separation` | 0-5 | Core、Support、Hit、Residual 是否各司其职 |
| `rhythm` | 0-5 | 起势、峰值、持续、残留和消散是否有节奏差异 |
| `material` | 0-5 | 贴图、Shader、遮罩、流动、溶解和亮度是否服务形体 |
| `composition` | 0-5 | 占屏、空间位置、镜头和场景关系是否合理 |
| `quality_score` | 1-5 | 综合质量，只能来自专业 Teacher 或隔离后的专业模型推理 |

这些维度可以共享字段、评价顺序和数据格式，但不能把刀光的“主体弧好坏”直接迁移成火焰的“温度感”，也不能把一个族的风格标签当作另一个族的质量标签。

### 风格维度

风格是条件，不是质量的同义词。至少分别记录：

```text
target_style_profile      Prompt要求的风格
observed_style_profile    画面实际呈现的风格
style_match_decision      match / partial / mismatch / unlabeled
```

可用风格族包括 `realistic`、`stylized`、`cartoon`、`anime`、`fantasy_painterly`、`ui_graphic` 和 `mixed`。连续轴可记录写实程度、图形化程度、纹理细节、饱和度、边缘清晰度、Glow夸张度和运动夸张度。

必须允许以下结论同时成立：

```text
功能符合，但风格不符合
风格符合，但整体质量不足
技术可播放，但无法判断审美
局部层可复用，但整体不应作为正例
```

### 问题标签

问题标签应解释“为什么不合格”，用于 Judge 分类和下一轮变异：

```text
core_unclear
wrong_direction
weak_peak
flat_rhythm
support_overpowers_core
hit_arrives_too_early
residual_too_long
material_texture_missing
uv_flow_wrong
dissolve_wrong_direction
overexposed
dirty_color
composition_too_small
style_mismatch
```

技术问题另设命名空间，例如 `missing_shader`、`missing_m_texture`、`runtime_context_required`、`fixed_camera_subject_too_small` 和 `runtime_resource_leak`，不能与审美问题混用。

## 四、成对偏好数据

单个质量分数告诉模型“这个候选大概几分”，成对偏好告诉模型“在同一个目标下应该选谁”。因此每个 Prompt 需要生成 4-8 个同族、同镜头、可比较的候选：

```json
{
  "pair_id": "pair-001",
  "prompt_id": "prompt-001",
  "effect_family": "fire",
  "candidate_a": "run-a/candidate-01",
  "candidate_b": "run-a/candidate-02",
  "preference": "a|b|tie|not_comparable",
  "reason_codes": ["core_readability", "weak_peak"],
  "human_note": "A的爆炸峰值更集中，B的残留太长",
  "evidence": {
    "a_frames": ["..."],
    "b_frames": ["..."],
    "same_prompt": true,
    "same_family": true,
    "same_camera": true
  }
}
```

`not_comparable`、不可见候选和技术失败候选不进入 pairwise 审美训练。平局可以保留作分析，但不生成胜负标签。

现有 [vfx_training_features.py](../../workspace/tools/vfx_training_features.py) 已能从 Unity 连续帧和 Spec 提取可解释特征，现有 [vfx_preference_ranker.py](../../workspace/tools/vfx_preference_ranker.py) 已能训练轻量 pairwise 排序器。审美方案需要补齐的是：把人工评价统一成 `preference_pairs.jsonl`，而不是重新发明排序算法。统一记录到训练文件的入口是 [aesthetic_record_exporter.py](../../workspace/tools/vfx_generation/aesthetic_record_exporter.py)，记录与特征的分组组装入口是 [aesthetic_training_dataset.py](../../workspace/tools/vfx_generation/aesthetic_training_dataset.py)。

## 五、训练阶段与产物

### 阶段 0：审美证据盘点

输入：现有 `knowledge/`、VFX.library 视觉资料、Unity runs 和评价记录。

输出：

- 每条资料的来源、授权、时间点和可见性状态；
- `reference_observations.jsonl`；
- 课程规则与参考资料的 `observation_only` 记录；
- 技术失败、无法判断和上下文依赖排除表；
- 按特效族和风格的覆盖统计。

当前已知底座约有 57 张 `AESTHETIC-*` 卡片和 207 条 `visual_review` 类记录，但它们还不是统一的审美训练集。VFX.library 当前仍按 `reference_only`、`experimental` 或 `partial` 管理，不能自动升级为高质量正例。

### 阶段 1：专业资料 Teacher 构建

输入：专业视频、教程、专家点评、真实可见连续帧、Prompt、Prefab/材质摘要和技术状态。

输出：

- `aesthetic_feedback.jsonl`；
- `reference_observations.jsonl`；
- `preference_pairs.jsonl`；
- 风格 Profile；
- 多维质量分；
- Layer roles、可复用层和问题标签；
- 人工备注和下一轮修改方向；
- 每条记录的 `confirmation_mode` 和完整 trace。

验收重点：每条审美结论必须能回到专家原话、动态帧/时间码、前后对比或 Unity 复刻；不能从来源名称、字幕关键词或 AI 草稿推断质量。

### 阶段 2：审美 Judge 数据集

输入：阶段 1 人工标签、连续帧特征、Prefab/Material/Shader 摘要。

输出：

- `aesthetic_feedback.jsonl`；
- `aesthetic_feature_matrix.jsonl`；
- `preference_pairs.jsonl`；
- `judge_dataset_manifest.json`；
- train/validation/test 分组清单；
- 标签分布、缺失统计和泄漏审计。

切分必须按内容哈希、Prefab 来源组、Material/Shader 共享组、Prompt 组和独立 Unity run 隔离，不能把同一个 Prefab 的复制品放到不同 split。

`.29.2` 的标准化导出入口为：

```powershell
python -m workspace.tools.vfx_generation.aesthetic_record_exporter `
  --knowledge-input knowledge/sources `
  --knowledge-input knowledge/cards `
  --knowledge-input knowledge/experiments `
  --human-feedback workspace/data/vfx_generation/reviews/<review>/human_label_overlays.jsonl `
  --technical-exclusion workspace/data/vfx_generation/reviews/<review>/technical_exclusions.jsonl `
  --output-dir workspace/data/vfx_generation/datasets/<dataset_id> `
  --dataset-id <dataset_id>
```

当前真实标准化批次为：

```text
workspace/data/vfx_generation/datasets/aesthetic_records_r006/
```

结果为 `2651` 条资料 observation、`47` 条人工质量记录、`47` 条 Judge 资格记录、`218` 条技术/不可见排除，`0` 条偏好记录。组合评价的 `prompt_composition_human_label_overlay.v1` 已纳入解析，Unity 自动评价为 reject 的人工记录也会排除；Prompt 条件反馈仍保持独立，不会变成审美质量标签。

当前特征对齐产物为：

```text
workspace/data/vfx_generation/datasets/aesthetic_features_r002/
```

其中 `47/47` 条 Judge 标签已经对齐真实连续帧特征；Prefab 41 条合并已有 runtime 结构/图像特征，组合 6 条直接从 11 帧连续截图提取图像特征，缺失帧为 `0`。Prefab review 使用 `trains_fx_*`，runtime 使用 `source_prefab_*`，对齐器保留两个 ID，不通过字符串猜测替换。

`.29.3` 的真实训练组装审计位于：

```text
workspace/data/vfx_generation/datasets/aesthetic_training_r006/
```

该批次包含 `2698` 条统一记录和 `2869` 条审计排除，`47` 个 Judge 候选已经有匹配特征，Judge 训练文件为 `47` 条；由于偏好训练文件仍为 `0` 条，整体数据集门禁为 `blocked_insufficient_labels`。它同时生成 `aesthetic_feedback.jsonl`、`preference_pairs.jsonl`、`judge_training.jsonl`、`preference_training.jsonl` 和 `split_assignments.jsonl`，因此后续只需补 A/B 偏好并重建，不需要重新扫描原始资料。

### 阶段 3：VFX Judge 基线

第一版采用可解释的轻量模型：

```text
连续帧视觉特征 + Prompt条件 + 风格Profile + 结构摘要
  -> 多任务分类/回归头
  -> 质量分、风格匹配、问题标签、置信度
```

先验证每个评价维度是否有足够标签；已满足门禁的任务头独立训练，未满足的任务头继续阻塞且不写权重。训练输出必须包含：

- 特征 Schema；
- 每个任务的训练样本数量和类别分布；
- 按 run、Prefab 和来源分组的交叉验证；
- metrics；
- 误判样本和失败原因；
- Model Card；
- 明确的 `experimental` 状态。

后续如果轻量特征基线稳定，再考虑冻结视觉编码器加 Projector，或使用小型视频/图像编码器。当前不从零训练大型视频模型。

当前 Judge 基线入口为：

```powershell
python -m workspace.tools.vfx_generation.aesthetic_judge audit `
  --judge-training workspace/data/vfx_generation/datasets/aesthetic_training_r006/judge_training.jsonl `
  --output workspace/data/vfx_generation/datasets/aesthetic_training_r006/judge_preflight.json

python -m workspace.tools.vfx_generation.aesthetic_judge train `
  --judge-training workspace/data/vfx_generation/datasets/aesthetic_training_r006/judge_training.jsonl `
  --output-dir workspace/data/vfx_generation/models/aesthetic_judge_<id>

python -m workspace.tools.vfx_generation.aesthetic_judge evaluate-regression `
  --model workspace/data/vfx_generation/models/aesthetic_judge_<id>/aesthetic_judge.joblib `
  --input workspace/data/vfx_generation/regression/<freeze_id>/judge_regression_rows.jsonl `
  --output workspace/data/vfx_generation/regression/<freeze_id>/judge_regression_evaluation.json `
  --minimum-samples 24
```

历史 r006 的预检结果为 `row_count=47`，但这些多维评分来自非专业人工，现已从正式审美训练边界移除。相关模型只保留为历史实验，不接入当前复核页，不参与专业 Judge 的训练、回归或晋级。当前 `course_knowledge_r003` 有 2651 条资料记录，但满足全部专业 Teacher 门禁的样本为 0，下一步不是降低门槛，而是补齐专业来源、动态证据、明确结论和 Unity 复刻。

回归冻结 `prefab_regression_gold_r002` 只取得 2 条 Capture v2 human gold，并发现它们都曾进入旧 r006 Judge 输入。系统因此导出 45 条隔离训练输入，训练 `aesthetic_judge_partial_r004_regression_isolated` 后再对 2 条回归记录评估；训练重叠为 0，但回归集少于最低 24 条且风格头阻塞，所以仅记录实验 MAE，禁止模型晋级。

### 阶段 4：Preference Ranker

使用同 Prompt、同族、同镜头的人工成对偏好训练排序器：

```text
feature(winner) - feature(loser)
  -> pairwise preference probability
  -> candidate ranking
  -> failure contribution
  -> next mutation proposal
```

当前 smoke 门槛沿用已有排序器：至少 20 个非平局比较、8 个独立候选、2 个独立运行组。正式跨族使用前，建议每个特效族积累 300-1000 个以上成对偏好、至少 5 个独立 run，并保留独立人工回归集。

排序器只能用于同族候选排序。跨族可以共享数据格式、特征抽取和技术过滤，但不能直接共享“好看”的权重。

当前规范化偏好排序入口为：

```powershell
python -m workspace.tools.vfx_generation.aesthetic_preference_ranker audit `
  --preference-training workspace/data/vfx_generation/datasets/aesthetic_training_r006/preference_training.jsonl `
  --output workspace/data/vfx_generation/datasets/aesthetic_training_r006/preference_preflight.json

python -m workspace.tools.vfx_generation.aesthetic_preference_ranker train `
  --preference-training workspace/data/vfx_generation/datasets/aesthetic_training_r006/preference_training.jsonl `
  --output-dir workspace/data/vfx_generation/models/aesthetic_preference_<id>
```

真实 r006 的偏好预检为 `0` 个可比较训练对，因而训练被拒绝且没有写入排序权重。现阶段缺的不是排序算法，而是同一 Prompt/特效族下的真实 A/B 人工比较。

用户已明确：仅凭当前静态图片无法可靠完成 A/B，因此 `aesthetic_preference_review_r001` 的 15 对保留为待真实 Unity 动态播放复核的数据，不再阻塞完整 Prefab 生成主线。结构、资产路由和 Unity 编译验证继续使用 `ai_hypothesis` 与技术指标，但这些结果不进入人工审美监督，也不冒充质量正例。

当前真实 A/B 待评价批次为：

```text
workspace/data/vfx_generation/reviews/aesthetic_preference_review_r001/
```

该批次来自同一“卡通蓝色能量冲击，快速爆发，不要长拖尾” Prompt、同一爆炸族和同一来源 Prefab 的 6 个技术通过变异候选，含 11 帧连续画面和 15 个待人工比较对；r008 技术失败候选已排除。评价页已启动于 [http://127.0.0.1:8795/](http://127.0.0.1:8795/)，只提供 `A更好`、`B更好`、`差不多`、`无法比较` 以及中文原因和备注。当前 15 个 pair 均未填写，不能从已有质量分数推导偏好。

人工完成后，使用页面的保存结果并调用 `/api/finalize`，生成 `preference_records.jsonl`；只有选择 `A更好` 或 `B更好` 的可比较记录进入 preference training，`差不多` 和 `无法比较` 进入排除。

Controller 审美指导入口为：

```powershell
python -m workspace.tools.vfx_generation.vfx_controller_aesthetic_guidance `
  --prompt "卡通火焰爆发" `
  --effect-family fire `
  --style-family cartoon `
  --judge-prediction <judge-predictions.json> `
  --preference-ranking <ranking.json> `
  --output workspace/data/vfx_generation/runs/<run_id>/aesthetic_guidance.json
```

指导输出只包含 `goals`、`preserve`、`change`、`rationale` 和证据版本；`approval_required=true`，并且所有训练资格均为 false。Unity 执行和人工确认完成后，才能将最终 MutationSpec 送入后续 Controller 数据集。

当前爆发 Prompt 的安全降级 smoke 产物为：

```text
workspace/data/vfx_generation/datasets/aesthetic_training_r003/controller_aesthetic_guidance_r001.json
```

由于真实 Judge/Ranker 尚无权重，该产物只保留 Prefab 依赖闭包、材质/贴图/Shader 绑定和 Unity provenance，并给出“等待更多可见人工评价和偏好比较”，没有自动指定变异参数。

跨族/风格晋级审计入口为 [aesthetic_model_promotion.py](../../workspace/tools/vfx_generation/aesthetic_model_promotion.py)，当前真实报告为：

```text
workspace/data/vfx_generation/reports/aesthetic_promotion_r002.json
```

报告确认 `998` 个分组、`0` 个跨 split 泄漏，Judge 训练候选为 `47`、偏好训练对为 `0`，Judge/Ranker/Controller 模型均未达到发布状态，回归集缺失，因此晋级决策为 `blocked`。该结论表示发布门正常工作，不表示特征或排序代码失败。

### 阶段 5：Controller 接入

Controller 输入增加：

```text
Prompt
target_style_profile
effect_family
可用Prefab/Material/Texture/Shader摘要
课程审美规则
Judge版本和评分
Preference Ranker版本和偏好原因
历史失败标签
```

Controller 输出增加可追溯的：

```text
目标层职责
材质/贴图/Shader选择理由
时序和参数变异目标
预期视觉问题修复
Unity工具调用计划
```

只有通过 Unity 技术门禁、拥有完整连续帧、资源审计干净、Prompt 条件已人工确认且整体为“符合”的样本，才进入 Controller 正向 SFT。课程审美规则可以作为输入先验，但不能直接成为成功输出。

## 六、训练门禁

### 硬排除

以下记录永远不能进入审美正向训练：

- `无法判断`、`not_visible`、`blocked_environment`；
- 没有连续帧或只有文件存在证据；
- 缺失脚本、上下文依赖、固定镜头不可见等技术/环境失败；
- 未保存的 AI 草稿；
- 只有字幕、文章或文件名，没有画面核对；
- 未确认授权的外部素材作为可生成资产的标签；
- 来源 Prefab 的人工标签直接套到变异候选；
- 课程里的 `unverified_assumption` 直接升级为教程事实或正例。

### 训练门槛

| 模型 | 首轮 smoke | 正式晋级要求 |
|---|---|---|
| Prompt 条件评分器 | 每条件有基本类别和至少两个评价组 | 多族、多风格、独立留出集和校准置信度 |
| Judge | 每任务标签足够，分组交叉验证可运行 | 各族/风格独立指标、误判复核和人工采纳率 |
| Preference Ranker | 20比较、8候选、2运行组 | 每族300-1000+偏好对、5+ run、独立回归集 |
| Controller SFT | 32个正向样本、2个特效族 | 结构、资源、风格和运行证据均有独立留出集 |
| Controller DPO/偏好 | 有可靠chosen/rejected计划对 | 不同Prompt、族、风格和来源均无泄漏 |

达到 smoke 门槛不等于可以自动采纳。模型状态分为 `smoke`、`experimental`、`candidate` 和 `promoted`，必须带 metrics、数据版本、依赖版本、命令和 Model Card。

## 七、任务顺序和交付物

Beads 主任务：`vfx-2df.29`，标题为“建立跨特效审美资料训练闭环”。

```text
vfx-2df.29.1 建立审美证据与标签Schema
        |
vfx-2df.29.2 实现审美资料标准化导出与人工评价
        |
vfx-2df.29.3 组装审美Judge与偏好训练数据集
       / \
vfx-2df.29.4  多任务VFX Judge基线
       |       \
vfx-2df.29.5  跨Prompt成对偏好排序器
       \       /
vfx-2df.29.6 将Judge与偏好结果接入Controller
        |
vfx-2df.29.7 跨特效族与风格评估及模型晋级
```

每个阶段至少交付：

```text
代码或配置
Schema
真实数据样本
测试
输入/输出命令
数据和模型 manifest
失败与排除清单
指标和 Model Card
Beads 阶段 note
```

## 八、当前工程接入点

已存在、可以复用的入口：

- [课程资料适配器](../../workspace/tools/vfx_generation/course_knowledge_adapter.py)：课程证据到 VFXSpec prior；
- [Controller 数据集导出器](../../workspace/tools/vfx_generation/vfx_controller_dataset.py)：生成候选到 Controller 审计；
- [连续帧特征提取器](../../workspace/tools/vfx_training_features.py)：Unity run 到可解释特征；
- [偏好排序器](../../workspace/tools/vfx_preference_ranker.py)：成对反馈到轻量排序模型；
- [多任务 VFX Judge](../../workspace/tools/vfx_generation/aesthetic_judge.py)：质量维度和风格分类的轻量基线，按任务单独执行标签门禁；
- [审美偏好排序适配器](../../workspace/tools/vfx_generation/aesthetic_preference_ranker.py)：规范化 A/B 偏好到现有 pairwise ranker，并阻止不可比较或缺少特征的训练；
- [Controller 审美指导器](../../workspace/tools/vfx_generation/vfx_controller_aesthetic_guidance.py)：将 Judge、Ranker 和人工问题转换为需要批准的 MutationSpec 指导；
- [Prompt 条件评分器](../../workspace/tools/vfx_generation/prompt_condition_scorer.py)：风格、主色、类别、节奏和负向条件的独立监督。
- [专业 Teacher 复刻器](../../workspace/tools/vfx_generation/professional_teacher_reproduction.py)：将专家明确规则变成只改一个变量的 Unity 动态对照，并经编译、贴图、Prefab API 和像素门禁晋级 Teacher。
- [专业 Teacher 引导器](../../workspace/tools/vfx_generation/professional_teacher_guided_generation.py)：将已验证规则限定在目标特效族/评价轴中迁移到候选 Graph，再与同种子基线重捕对比。
- [爆炸核心窄轴模型](../../workspace/tools/vfx_generation/professional_core_rule_model.py)：将通过迁移的 pair 按组隔离，用 PyTorch 成对梯度下降训练仅限 `explosion/core_readability` 的排序头。
- [爆炸残留窄轴模型](../../workspace/tools/vfx_generation/professional_residual_rule_model.py)：只学习 `explosion/residual_persistence`，使用晚段活跃、面积与最后可见时间，不评价烟雾材质美感。
- [爆炸冲击波消融](../../workspace/tools/vfx_generation/professional_shockwave_ablation.py) 与 [冲击波窄轴模型](../../workspace/tools/vfx_generation/professional_shockwave_rule_model.py)：用固定正交成对差异隔离外扩环，并强制同一捕获协议后才允许推理。

尚需要完成的入口：

- `reference_observations` 与 `aesthetic_feedback` 到正式 Judge/偏好数据集的分组切分导出；
- 现有人工反馈到 `preference_pairs` 的成对比较采集；
- Judge 数据集的特征补齐、多任务训练和误判复核；
- Judge/Ranker 版本结果接入 Controller 的 MutationSpec 规划。

当前已有 15 条专业 Teacher-ready 规则和 16 个 PyTorch 窄轴 checkpoint。爆炸族覆盖六轴，刀光族具备五轴模型。雷电族已完成 `main_branch_hierarchy`、`impact_focus` 与 `instant_pulse` 三个模型轴；`residual_persistence` Teacher 已 verified，待 8 对迁移和模型训练。下一阶段完成余电收尾和雷电多轴融合；火焰和护盾随后推进。

Unity 运行证据必须标明工程版本和渲染管线。当前 Trains/WebGL 复核使用 Unity 2022 兼容工程 `UnityDemo/EffectDemo`；正式制作工程 `UnityDemo/EffectDemo6.0` 不与兼容工程混用。跨工程导入仍须保留 Prefab 依赖闭包、材质、贴图、Shader `.meta` GUID 和本地 include 链。

## 九、第一轮实际执行建议

第一轮不追求一次性训练大模型，按以下顺序落地：

1. `.29.1-.29.7` 的工具底座和当前 A/B 批次继续保留，但不要求用户仅凭静态联系表完成标注。
2. 完成 `vfx-2df.34` 的 PrefabGraph、Grammar 约束解码、AssetPlan、Unity 编译器和结构预训练，不消费人工审美标签。
3. 使用 Unity 动态播放、重播和必要的参数对比恢复可靠人工反馈。
3. AI 根据资料规则和 Unity 运行指标产生 `ai_hypothesis`，只用于候选搜索和技术调试，不写入 `human_feedback`。
4. 真实人工数据到达门槛后，再训练 Judge/Ranker 并与结构生成主线合流。

本方案的第一阶段成功标准不是“已经生成漂亮特效”，而是：对于一个新候选，系统能够说明它是否可见、技术是否通过、主体/层级/节奏/材质/构图具体哪里有问题，以及下一轮应该修改哪一个可解释变量。

## 关联文档

- [生成式 VFX 训练标准](../30-操作指南/生成式VFX训练标准.md)
- [VFX Controller 训练基线](../30-操作指南/VFX%20Controller训练基线.md)
- [VFX 多特效训练与迁移策略](VFX多特效训练与迁移策略.md)
- [资料投喂与吸收模型](../10-解释/资料投喂与吸收模型.md)
- [工程结构总览](工程结构总览.md)
