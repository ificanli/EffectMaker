# EXP-2026-108 EffectDemo 逐帧材质状态时间线

## 目标

在 `UnityDemo/EffectDemo`、Unity `2022.3.16f1c1` 的真实 Play Mode 中，把脚本或动画驱动的 Material 实例、贴图、Shader Keyword、MaterialPropertyBlock 和溶解参数记录为逐帧训练真值；截图只用于对齐和人工观察。

## 采集顺序

```text
其他脚本 Update / LateUpdate
  -> EffectDemoRuntimeCaptureController LateUpdate（executionOrder=32000）
  -> 读取 Renderer / Material / MPB
  -> 计算相邻帧 delta
  -> Camera.Render
  -> PNG + material_timeline.json
```

`WaitForEndOfFrame` 在 Unity 2022 `-batchmode` 中不会恢复协程，不能用于自动批量采集。最终使用最高执行顺序的 LateUpdate 屏障，时间线和 capture manifest 分别记录：

- `capture_order=late_update_barrier -> material_snapshot -> camera_render`
- `material_capture_sync=late_update_execution_order_32000`

## 数据结构

每帧记录 Renderer 层级路径、材质槽、运行时 Material 实例、Shader、RenderQueue、Keywords、Shader 声明属性、Renderer MPB、槽级 MPB、贴图身份和语义标签。

相邻帧 delta 分类包括：

- `material_instance_replaced`
- `texture_changed`
- `shader_keywords_changed`
- `material_property_changed`
- `renderer_property_block_changed`
- `slot_property_block_changed`
- `dissolve_parameter_changed`

Unity 公共 API 不能枚举 MPB 中未知 Property ID，因此采集器读取全部 Shader 声明属性，并额外探测常见 Dissolve、Mask、Flow、Distortion、Emission、Alpha 别名；该限制写入每条时间线。

## 受控正例

- Run：`workspace/data/vfx_generation/runs/material_state_probe_r001`
- Prefab 标识：`__effectdemo_material_state_probe__`
- Source fidelity：`source_scripts_captured`
- 采样：`0.0~1.0s`，间隔 `0.1s`
- 截图：`11/11` 有效
- Material timeline：`11` 帧，`30` 条 delta，`9` 个变化帧

捕获结果：

| 信号 | 数量 | 关键时间 |
|---|---:|---:|
| 贴图替换 | 1 | 0.3s |
| Shader Keyword 开关 | 1 | 0.4s |
| Material 实例替换 | 1 | 0.6s |
| 槽级 MPB 变化 | 18 | 0.1~0.9s |
| 溶解参数变化 | 9 | 0.1~0.9s |
| Material 属性变化 | 10 | 0.1~0.9s |

联系表显示画面由蓝色完整面逐步变成橙色溶解条纹，和贴图、Keyword、Material、MPB 时间点一致。`material_timeline.schema.json` 校验为 `0 errors`。

## 真实 Trains 静态材质批次

- Run：`workspace/data/vfx_generation/runs/trains_material_timeline_r001`
- 候选：`FX_BossTips`、`Fx_com_sheilder`、`Fx_Gun_Fire`、`FX_chongneng_jiesuo`、`FX_ui_jiyinsuo_jihuo`
- Source fidelity：全部 `no_ignored_script_dependencies`
- 总截图：`119/119` 有效
- Material timeline：`5/5 ready`
- Dynamic candidates：`0`
- Material delta：`0`

联系表证明这些 Prefab 的粒子、Animator 或 Shader 时间能够产生动态画面，但 Renderer Material、贴图、Keyword 和 MPB 在采样期间保持不变。它们是“视觉动态、材质状态静态”的真实负例，不能被误标为脚本材质轨迹。

## 真实材质 AnimationClip 案例

源 Prefab：`E:/Trains/Unity/Assets/Bundles/Battle/Prefab/Train/TrainEngine_HintTextWrap.prefab`

依赖中 `Ani_TrainEngineGuideText_Show/Hide/Idle.anim` 直接动画：

```text
material._Color.r
material._Color.g
material._Color.b
material._Color.a
```

该 Prefab 已按依赖闭包导入：

```text
Assets/VFXSourceIngest/Trains/Trains_MaterialDriver_001/
```

Run：`workspace/data/vfx_generation/runs/trains_material_animation_r001`

结果为 `11/11` 截图有效、`0` Material delta。日志显示 TMP 和 `TrainEngineHintTextItem` 组件缺失；`source_script_fidelity=source_scripts_excluded`。该案例只能标为 `runtime_context_required`，不能升级为正例。

## 源脚本审计

全量 FX 导入清单有 `151` 条忽略脚本边、`128` 个 Prefab、`8` 个唯一脚本。八个直接依赖脚本中没有脚本调用 `SetPropertyBlock`、`SetTexture`、`SetFloat`、Keyword 或溶解参数；`UIParticle` 只读取 Renderer Material。

源工程其他目录存在以下材质驱动器：

- `uTweenMaterialParam`：使用 MPB `SetFloat`，但未找到 Prefab 引用。
- `uTweenAlpha`：在 7 个 Prefab 中使用，现有引用配置只操作 SpriteRenderer/UI 颜色，不是 MeshRenderer Material。
- `ImageMoveLight`：5 个 UI Prefab 使用，修改 Graphic Material Vector，不属于当前 Renderer 采集范围。
- Battle/Role Render 脚本：包含全局 Shader 和 MPB 变化，但依赖完整战斗上下文，不能安全复制为独立 FX Prefab。

## 结论

采集协议已能可靠区分动态材质正例、静态材质负例和上下文阻塞案例。当前 Trains FX Prefab 集本身缺少可独立运行的脚本材质正例；下一阶段需要用已导入 Material/Shader/Texture 生成受控参数轨迹 curriculum，或在源游戏完整运行上下文中采集角色/场景材质驱动，不得从粒子动态推断材质脚本动态。
