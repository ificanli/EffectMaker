# VFX 多特效训练与迁移策略

## 目的

系统的目标是学习可迁移的 VFX 制作与筛选能力，而不是把刀光案例、材质参数或单次人工偏好直接套到火焰、雷电和护盾上。迁移只能传递已经被相同证据类型支持的能力；每个特效族仍必须在目标族中获得独立的结构、运行和人工质量证据。

当前权威运行工程为 `UnityDemo/EffectDemo`，Unity `2022.3.16f1c1`、URP `14.0.9`。已有技术语料包括 MaterialTrajectory R002 的 100 条状态轨迹，以及 Trains R3 的 259 条 Prefab 结构记录；这些不等于跨族审美训练集。

## 2026-09-04 架构校准

首次完整 Prompt 试生成证明，当前刀光、雷电和爆炸族生成器的核心仍是“固定拓扑 + 固定资产 + 窄参数采样”。Prompt 主要被保存为元数据，尚未实际控制主体形体、Shader 功能、材质参数、贴图通道、命中位置和完整时序。现有专业 Teacher 和窄轴模型能证明单条受控规则可以迁移，但不能证明一批候选中存在合格成品。

因此训练主线改为：

```text
Prompt / 参考证据
  -> 可学习 Planner
  -> TopologyPlan + ShaderPlan + TexturePlan + ParameterPlan + TimingPlan
  -> 能力注册表检索与角色兼容性门禁
  -> 族操作子组合
  -> PrefabGraph / Unity 执行
  -> 技术门 + 局部 Teacher 约束 + 整体绝对质量门
  -> 正样本或负样本回流
```

`MaterialPlan` 的“路径存在、可编译、贴图回读一致”只是技术存活门。正式提案还必须联合验证 Shader 功能、Material 关键字与参数、Texture 语义与通道、Renderer 模式、Mesh UV 以及 Particle vertex streams。不得再用“无洋红/有像素”代替“Shader 选型正确”。

### 生成失败如何分流

| 失败类型 | 默认动作 | 是否改架构 |
|---|---|---|
| 候选可表达、可正确执行，但整体质量差 | 保留为负样本，用于 Judge/Ranker/Planner 训练 | 否 |
| Planner 没有所需形体、层职责、资产或时序操作 | 扩展通用操作子或族操作子，不针对单样本打补丁 | 是，但必须是可复用能力 |
| PrefabGraph/Unity 不能表达 Shader property、keyword、MPB、vertex stream 或上下文 | 扩展执行契约并做 API 回读回归 | 是，属于执行层能力 |
| 局部 Teacher 与整体人工/专业证据冲突 | 局部 Teacher 保留原轴有效性，禁止它批准整体成品 | 修正聚合和门禁，不改单轴事实 |
| 编译、依赖、空帧或镜头失败 | 进技术错误路由，不作审美负例 | 只修工具或资产闭包 |

一次普通生成质量失败不应触发手工重写生成器。只有失败证明了通用动作空间或执行契约缺失，才允许进入架构修正。

## 任务分层

| 层级 | 可跨族共享 | 必须按特效族独立学习 |
|---|---|---|
| 摄入与资产闭包 | Prefab/Material/Texture/Mesh/Shader GUID 闭包、`m_Texture` 完整性、CustomEditor 状态、许可和来源 | 特定游戏业务脚本、角色挂点、UI 容器、战斗触发器 |
| 技术结构 | PrefabGraph、ParticleSystem 模块、Renderer/Mesh/Material 槽、时长采样、MaterialPropertyBlock/Keyword/Texture Swap 记录 | 刀光弧线控制点、火焰体积与上升流、雷电分叉图、护盾曲面/碰撞关系 |
| 自动筛选 | 空帧、缺失 Asset、Material GUID 重复、截图缺失、资源泄漏、固定相机主体过小 | “主体是否像一记攻击”“火焰是否有温度”“雷电是否有冲击”“护盾是否有防护感” |
| 人工偏好 | 评价表结构、风格词表、Core/Support/Hit/Residual 字段、保存与回溯格式 | 各族的质量分、可复用层、审美排序和下一轮变异理由 |
| 候选生成 | provenance、seed、VFXSpec、Renderer 目标绑定、Unity 回放与硬过滤 | 形体拓扑、层职责、时序模板、镜头关系、材质参数范围和风格约束 |

## SlashArc 迁移条件

`SlashArc-Pref-001` 的偏好数据只能在以下条件满足后作为辅助先验迁移到 Fire、Lightning、Shield：

1. 目标族每个候选都有目标 Prefab/Layer、Material/Shader/Texture 和运行证据，不能只用名称或截图相似度匹配。
2. 目标族已通过技术路由：缺失 Script、源缺失、上下文依赖、固定镜头不可见与可独立播放必须分开记录。
3. 共享的输入只限于通用字段，例如主体占画面比例、峰值时间、持续时间、Renderer/Particle 数、亮度/饱和度变化、材质槽角色和已验证的失败码。
4. 任何“好看/不好看”“主体明确”“命中有效”“节奏自然”的排序，必须由目标族人工反馈产生。Slash 的标签不能替代 Fire、Lightning 或 Shield 的标签。
5. 目标族至少达到训练标准中的 smoke 门槛前，迁移只能生成检索候选或规则优先级，不能训练/发布跨族排序权重。

当前状态下，刀光的偏好训练不应迁移为 Fire、Lightning、Shield 的审美权重；可迁移的是候选格式、技术筛选、资源闭包和回放验证流程。

## 失败标签边界

以下失败码可跨族共享并用于自动路由：

- `missing_m_texture`、`wrong_texture_asset_type`、`duplicate_material_guid`
- `missing_shader`、`missing_frame`、`runtime_resource_leak`
- `source_missing_dependency`、`runtime_context_required`
- `fixed_camera_subject_too_small`、`background_only_frame`

其中最后两项只说明当前独立预览不足，不说明特效质量差。缺失 Script、UI/角色上下文和镜头不适配必须进入技术标签，不得写入审美拒绝。

以下标签不得直接跨族迁移：

- Slash 的主体弧、拖尾长度、出刀方向、命中切面与残留节奏。
- Fire 的燃烧层次、热扰动、上升流、明灭频率与烟雾关系。
- Lightning 的分叉密度、跳点、脉冲、链路目标与瞬时可读性。
- Shield 的曲面覆盖、轮廓闭合、受击涟漪、厚度和防护反馈。
- 任一目标族的风格匹配、总体质量、Core/Support/Hit/Residual 评价与可复用层。

## 三阶段路线

### 阶段 1：合成与技术语料

使用已验证的 Prefab 结构、Particle 参数、MaterialTrajectory、Texture tags 和技术失败路由，按特效族生成受控变异或检索候选。输出只能是 `feature-only`、技术对账结果和候选联系表；不训练审美权重。

### 阶段 2：目标族人工偏好

同一 Prompt 在同一目标族中生成 4 到 8 个可重放候选，由人工记录中文固定选项、风格、层职责、问题和备注。每条反馈必须追溯到 spec、seed、Prefab、材质时间线和真实播放证据。AI 草案只能预填表单，不能成为人工标签。

### 阶段 3：轻量排序与受控搜索

达到训练标准的候选数、偏好对和独立 run 后，先使用可解释的 pairwise ranker 或规则搜索。模型只负责从同族候选池排序，人工复核 Top K 后才生成下一轮 VFXSpec/MutationSpec。跨族仅共享特征抽取器、技术过滤器和 adapter 接口，不共享未经目标族验证的权重。

## 生成器库

`workspace.tools.vfx_generation.generator_registry` 定义候选空间而不伪造实现状态：

- 已实现：`slash` 的 `curve_mesh` adapter，入口为 `slash_arc_generator`。
- 计划 adapter：`fire`（体积流动粒子）、`lightning`（分叉路径）、`shield`（曲面/环/受击）、`smoke`（软体积粒子）、`explosion`（径向冲击/碎片）。

每个 family 都声明输入参数、输出资产、适用特效与失败模式。新增 family 只需要添加自己的 adapter 和 Unity executor，不需要改写 Prompt、证据、自动路由、人工反馈或训练门禁。

## 当前门槛

- MaterialTrajectory：状态监督可用；图像任务仍受 Shader group 失衡和上下文可见性限制。
- Trains Prefab：126 条可独立播放、94 条上下文依赖、37 条无效；可用于结构和技术路由，不自动升级为审美正例。
- WebGL 材质时间线首批：3 条候选已有动态回放和 AI 草案，但人工反馈为 0，不能生成 `human_feedback` 或训练偏好模型。

因此下一次能真正推进到“生成效果更好”的操作，不是扩大数据量，而是完成目标族的人类确认，再让排序结果指导同族的下一批 Unity 候选。
