# Source Ingestion

本目录用于登记 Unity 特效源文件包，并把它们转换为可追溯的训练样本输入。这里保存的是小型元数据、索引、示例和抽取结果；大量原始贴图、FBX、视频、截图和 Unity 导出默认只保留在本地。

系统总览与四类输入的角色见 [`workspace/vfx_generation_architecture.html`](../../../vfx_generation_architecture.html#inputs)。

## 输入资料的角色

| 输入 | 在体系中形成什么 | 最主要用途 | 不能单独证明 |
|---|---|---|---|
| 给定 Unity Prefab / 源工程 | `SourceAssetSpec` | 追溯层级、材质、Shader、贴图、Mesh、时间资产；提供可复用来源和渲染候选 | 画面好看、适合目标风格、可直接成为新设计 |
| 优秀特效视频 | `ReferenceSpec` | 定义目标轮廓、层次、节奏、镜头、风格和关键时间点 | 原始资产、Shader、完整参数和项目结构 |
| 制作教程 | `ProcedureSpec` | 提炼层级职责、参数关系、制作顺序和 adapter / Unity 实现规则 | 教程原工程的全部数值或当前版本必然可复现 |
| 特效评价课程 | `CritiqueRubric` | 定义人工审核字段、失败标签、排序与奖励模型的质量语言 | 具体资源、具体实现和某个候选已经通过视觉验收 |

四类输入必须与 Unity 实际渲染、运行状态和人工反馈结合，才能形成 `ApprovedExample`。当前最缺的是这种对齐样本，而不是更多未渲染的源资产。

## 为什么需要源文件摄入

截图和视频只能说明“画面长什么样”。源文件可以补上制作证据：

- Prefab 层级和组件职责。
- ParticleSystem、VFX Graph、Animation 和 Timeline 的时间结构。
- Material、Shader、Shader Graph、贴图和 mesh 的依赖关系，以及可训练的 shader / texture tag / slot role 组合。
- Unity GUID、`.meta`、包版本、URP 设置和场景上下文。
- 真实参数与渲染结果之间的联系。

源文件不能单独当训练真相。一个可训练样本至少还要关联渲染采样、人工反馈和授权状态。

## 目录建议

```text
sources/
  README.md
  ingest_rules.md
  examples/
    <source_id>/
      source_manifest.json
      source_sample.json
      derived_vfxspec.json
      training_example.json
```

## 数据流

```text
Unity source package
  -> source_manifest.json
  -> dependency_index / parameter extraction
  -> source_sample.json
  -> derived_vfxspec.json
  -> Unity render run
  -> human feedback
  -> training_example.json
```

## 可以摄入的文件

| 文件 | 价值 | 注意 |
|---|---|---|
| `.prefab` | 层级、组件、粒子系统、Renderer、材质引用 | 必须保留 `.meta` 才能追 GUID |
| `.unity` | 场景、相机、灯光、后处理、测试锚点 | 不能把场景效果误当 Prefab 自身效果 |
| `.mat` | Shader、颜色、贴图槽、Blend、Queue、材质参数 | 需要记录 Shader 和贴图依赖 |
| `.shader` / `.hlsl` | 溶解、流动、遮罩、Fresnel、扭曲等核心逻辑 | 大文件只索引关键函数和参数 |
| `.shadergraph` / `.shadersubgraph` | 节点图和可复用材质模块 | 节点结构要抽取为参数摘要 |
| `.vfx` | GPU 粒子、Spawner、Output、事件关系 | 需要记录 Unity/URP/VFX Graph 版本 |
| `.png` / `.tga` / `.dds` / `.exr` | Mask、Noise、Ramp、Dissolve、FlowMap | 默认本地保存，授权不明不得提交 |
| `.fbx` / `.obj` / `.asset` | 弧形 mesh、碎片、护盾壳、冲击波 | 记录导入设置和 mesh 用途 |
| `.anim` / `.controller` / `.playable` | 起势、峰值、残留、消散和镜头关系 | 需要与渲染时间点对齐 |

## 授权状态

每个源文件包和关键文件都必须标记授权状态：

```text
unknown              未确认，不进入训练
local_reference_only 本机参考，可分析不可提交原件
redistributable      可随工程分发
trainable_internal   可进入内部训练集
trainable_public     可进入公开训练集
blocked              不允许继续使用
```

默认策略：本地资源即使存在，也不能自动认为可提交、可发布或可训练。

## 最小门禁

源文件进入训练前至少满足：

1. `source_manifest.json` 能说明来源、Unity 版本、URP/管线版本、文件列表、GUID/meta、授权状态。
2. `source_sample.json` 能说明抽取到的层级、材质选择摘要、时间和结构摘要。
   其中 `material_selection` 应尽量区分 shader 候选、贴图候选、贴图标签和 slot role，而不是只保留数量；如果没有显式提供纹理标签索引，摄入步骤会在样本输出目录生成本地 `texture_tags.jsonl`，再把它写回样本和训练例。
3. 至少有一个 `derived_vfxspec.json` 作为系统可生成/可比较的结构化表达。
4. 至少关联一个 render run 或明确标记 `needs_render`。
5. 至少关联人工反馈或明确标记 `needs_feedback`。

## 批量渲染复核

`python -m workspace.tools.vfx_source_render prepare` 会从 `source_sample.json` 中读取 Prefab，按 `source_manifest.json` 的依赖边只选出该 Prefab 实际使用的材质，再从 `training_example.json` 保留每个材质对应的 Shader、贴图标签和 slot role。它会写出候选 `spec.json` 和 Unity 渲染请求，但不会把“依赖已解析”标成视觉通过。

Unity 完成多时刻截图后，`python -m workspace.tools.vfx_source_render finalize` 会复用 run pipeline 生成 `run_manifest.json`、`auto_eval.jsonl`、联系表和空的 `feedback.jsonl`。只有人工反馈写入后，候选才可转为训练标签。

## 边界

- 不把 Unity YAML、Shader 全文或贴图文件直接当训练真相。
- 不提交授权不明的大体积原始资源。
- 不用源文件字段替代真实渲染观察。
- 不把某个特效族的参数硬塞成所有特效通用字段。
- 不丢 `.meta`，否则依赖关系和 GUID 追踪会断。
