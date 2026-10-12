# VFX 制作教程 ProcedureSpec 训练方案

## 目标

特效制作教程是生成 Planner 的主要因果监督之一。它负责教系统“按什么顺序做、为什么这样做、哪些参数需要联动、失败时怎样修正”。Prefab 负责提供真实工程结构和资产分布，不再被当成唯一的生成监督。

```text
Prompt / 参考图
  + 制作教程 ProcedureSpec
  + 真实 Prefab 结构与资产分布
  + 专业点评 Teacher / 前后对照
  -> ProposalPlan
  -> Unity 执行与回读
  -> 整体质量验证
  -> Planner / Judge / Ranker 训练数据
```

## 为什么不能只用 Prefab

| Prefab 能提供 | Prefab 通常不能提供 |
|---|---|
| 最终层级、组件、参数和资产引用 | 创建顺序和中间版本 |
| Material / Shader / Texture / Mesh 真实绑定 | 为什么选这个 Shader 或贴图通道 |
| 粒子、动画、材质的最终状态 | 参数调整时的意图和联动关系 |
| 资产分布和工程约束 | 失败方案、修正方向和判断标准 |
| 可回放的最终动态 | 哪一层先做、哪一层只用于支撑 |

只用 Prefab 训练，很容易学到共现关系：“这种贴图经常和这种材质一起出现”。制作教程才能补上因果关系：“为了让外刃锋利，需要什么形体、遮罩和溶解方式”。

## ProcedureSpec 记录内容

每条教程流程必须保存：

- 来源路径、教程类型、时间码和关键帧。
- 适用特效族、特效类型、风格和元素。
- Unity 版本、渲染管线、工具与资产前置条件。
- 有序制作步骤：创建层、配置粒子、选 Shader、绑贴图、排时序、组合、回放、视觉验收和性能检查。
- 每步的目标层、参数范围、Shader 功能要求、Texture 语义标签和证据状态。
- 层组合顺序、时序关系、运行信号、质量信号和已知限制。
- 原教程验证状态与当前目标工程验证状态。

严格 Schema 见 `workspace/data/vfx_generation/schemas/procedure_spec.schema.json`。

## 证据分级

| 状态 | Planner 如何使用 | 训练资格 |
|---|---|---|
| `inferred` | 仅作待验证候选，不能变成硬约束 | 禁止 Controller SFT 和正向生成监督 |
| `tutorial_fact` | 可用于检索、步骤顺序和参数候选 | 必须经目标 Unity 工程复现才能升级 |
| `unity_verified` | 可作为 Planner 制作约束 | 若版本/管线不同，仍禁止正向 SFT |
| 目标工程复现 + 专业视觉验收 | 可作制作路径与结果联合监督 | 可进入 Planner SFT/Judge/Ranker，仍需分组防泄漏 |

## 与 ProposalPlan 的关系

`ProcedureSpec` 不直接生成 Prefab。Planner 先根据 Prompt 检索匹配教程，然后将已有证据的步骤投影到：

- `TopologyPlan`：需要哪些层，各层使用 Mesh、Billboard、Trail 还是其他承载。
- `ShaderPlan`：每层需要 emission、dissolve、cutout、flow、distortion 还是 fresnel。
- `TexturePlan`：需要 core shape、mask、noise、flow、ramp、hit accent 还是 residual texture。
- `ParameterPlan`：参数合法区间、相对大小、速度、数量和颜色层级。
- `TimingPlan`：起势、峰值、扩散、残留和消散顺序。

当前 `ProposalPlan` 对每个特效族都要求教程上下文。没有匹配教程时状态为 `missing`；有教程但未在 EffectDemo 2022 复现时为 `candidate`；只有在当前工程实际复现后才是 `verified`。

## 当前第一条 ProcedureSpec

`procedure_fireworks_layered_lifecycle_r001` 来自 `EXP-2026-004`，已结构化为九个制作与验证步骤，包含 Launch、AscentTrail、ExplosionCore、RadialBranches 和 Residue 的参数与时序关系。

该实验在 Unity `6000.5.9f1` / URP `17.5.0` 已验证，但当前训练工程是 Unity `2022.3.16f1c1` / URP `14.0.9`，因此现阶段只能约束 Planner，不得进入 Controller 正向 SFT。

第二条 `procedure_lightning_shape_lifecycle_r001` 直接来自《雷之呼吸 03 闪电制作》的字幕时间码与 30 秒连续画面。已提取闪电贴图特征、光柱/黑边/锐边层次、复制反转与偏移制造粗细变化、缩短生命周期、Color over Lifetime 闪动和 Mask 边缘虚化等步骤。由于自动转写存在识别误差，且精确 Inspector 数值尚未逐帧核对，它当前是 `partially_verified`，可检索、可约束，但不进入 SFT。

## 后续资料处理顺序

1. 优先处理完整实战制作教程，不优先处理只有成品展示的视频。
2. 先抽取过程、参数、Shader/贴图用途和失败修正，再做美学 Teacher。
3. 每条高价值 ProcedureSpec 都要在 EffectDemo 2022 做最小复现。
4. 复现通过后生成“Prompt + ProcedureSpec -> ProposalPlan -> PrefabGraph -> 运行证据”训练样本。
5. 制作路径正确但整体视觉不合格时，保留为过程正例 + 结果负例，不混成一个标签。
