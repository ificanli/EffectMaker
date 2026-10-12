# EXP-2026-109 MaterialTrajectory Curriculum R001

> 状态：R001 已完成 smoke 验证，但全量执行发现 `.mat` 历史 YAML 包含 Shader API 已删除的属性。R001 保留作失败证据；经 Material Binding Audit r3 过滤后的 `material_trajectory_curriculum_r002` 才是当前执行基线，详见 EXP-2026-110。

## 目标

在逐帧 Material timeline 已验证后，使用 EffectDemo 2022 中真实导入的 Material、Shader、Texture 绑定和 Texture tags，生成第一批可执行的材质动态 Curriculum 规格。此阶段只生成规格，不把未运行的 JSON 当成训练样本。

## 输入

- Unity 工程：`UnityDemo/EffectDemo`
- Prefab cases：`workspace/data/vfx_generation/datasets/trains_fx_all_001/prefab_cases.jsonl`
- Material API 审计：`UnityDemo/EffectDemo/Library/VFXSourceIngest/material-binding-audit.json`
- Texture tags：`workspace/data/vfx_generation/datasets/trains_fx_all_001/texture_tags.jsonl`
- Material 参数：Unity `.mat` YAML 的 `m_Floats`、`m_Ints`、`m_Colors` 和 `m_ValidKeywords`
- Schema：`workspace/data/vfx_generation/schemas/material_trajectory.schema.json`

生成器使用 PyYAML 解析 Unity Material 结构；Shader 名称和贴图槽来自 Unity Material API 审计，不从文件名猜测绑定关系。

## 输出

- Curriculum：`workspace/data/vfx_generation/curricula/material_trajectory_curriculum_r001`
- Seed：`20260828`
- Material 候选：`642`
- Texture 候选：`480`
- Spec：`100`
- Schema errors：`0`
- Shader groups：`3`
- Material groups：`94`

## 配额

| Category | Count |
|---|---:|
| dissolve | 20 |
| flow_distortion | 15 |
| emission_alpha | 15 |
| mpb | 15 |
| texture_swap | 10 |
| keyword_material | 10 |
| negative | 15 |

标签为 `85 positive / 15 negative`。控制范围分布：

| Scope | Count |
|---|---:|
| renderer_mpb | 38 |
| material | 36 |
| slot_mpb | 26 |

## 预期信号

| Signal | Count |
|---|---:|
| material_property_changed | 29 |
| renderer_property_block_changed | 28 |
| dissolve_parameter_changed | 26 |
| slot_property_block_changed | 15 |
| texture_changed | 16 |
| negative_trajectory | 15 |
| material_instance_replaced | 8 |
| shader_keywords_changed | 2 |

## 负例

负例变异：

- `abrupt_jump`：3
- `overshoot`：2
- `incompatible_texture`：6
- `no_op`：2
- `late_peak`：2

不兼容贴图负例使用 Texture tags 反向筛选，刻意选择不共享 slot/role/semantic 标签的贴图；正常 Texture Swap 优先选择标签兼容贴图。

负例变异必须与可执行操作一致：只有参数轨迹可使用 `abrupt_jump / overshoot / no_op / late_peak`，Texture Swap 负例统一标记为 `incompatible_texture`。`overshoot` 会清除轨迹 clamp，否则超范围值会在执行时被截断而失去负例语义。

`no_op` 不产生 runtime Material delta，因此两条 `no_op` 规格只期待 `negative_trajectory`，不再错误声明 scope 或 dissolve 变化。执行器必须从“轨迹已按规格执行但值未变化”确认该负例，而不能伪造 timeline delta。

## 无泄漏分组

每条规格记录：

```text
split_group.shader_group
split_group.material_group
```

后续训练/验证划分必须按这些 group 切分。同一 Material 的不同 seed 和参数轨迹不能同时出现在训练集与验证集。

## 边界

这些规格尚未经过 Unity 执行，因此当前状态只能是 `curriculum_spec`，不能作为正向监督或偏好训练数据。下一阶段必须实现 MaterialTrajectorySpec Unity 执行器，并逐条验证：

```text
spec expected_signals
  == executor projected actual signals
```

其中 projected actual signals 必须逐项有 raw material timeline 证据；`negative_trajectory` 由已执行的负例变异确认。贴图变化在 raw timeline 中还会伴随 scope provenance 信号，Material Replace 也可能带来材质属性差异；这些保留在 `raw_timeline_signals` / `incidental_timeline_signals`，不混入规格的主监督信号。

只有截图有效、时间线有效、预期信号命中且人工评价通过的规格，才能晋级为训练样本。
