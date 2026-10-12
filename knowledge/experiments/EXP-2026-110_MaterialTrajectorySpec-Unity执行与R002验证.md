# EXP-2026-110 MaterialTrajectorySpec Unity 执行与 R002 验证

## 目标

在 `UnityDemo/EffectDemo`（Unity `2022.3.16f1c1`、URP `14.0.9`）中执行真实 MaterialTrajectorySpec，而不是把课程 JSON 直接当训练样本。每条规格必须经过：

```text
真实 Material / Texture
  -> Play Mode 轨迹执行
  -> LateUpdate 材质快照
  -> Camera.Render 截图
  -> raw timeline 信号
  -> projected actual signals
  -> expected == actual
  -> Schema / 资源 / 视觉证据审计
```

主工程仍是 `UnityDemo/EffectDemo`。由于人工打开的 Editor 占用主工程，全量证据在同步了相同 `Assets/Packages/ProjectSettings` 的隔离工程 `workspace/unity-render-staging/EffectDemoWeb2022R002` 执行；manifest 同时记录权威源码工程与实际执行工程，不混淆两者。

## 实现

- Unity 执行器：`Assets/VFXCapture/EffectDemoMaterialTrajectoryExecutor.cs`
- Editor 启动入口：`Assets/Editor/EffectDemoMaterialTrajectoryBootstrap.cs`
- Unity Material API 审计：`Assets/Editor/EffectDemoMaterialBindingAudit.cs` r3
- Python prepare/finalize：`workspace/tools/vfx_generation/material_trajectory_executor.py`
- PowerShell 入口：`workspace/tools/effectdemo_execute_material_trajectories.ps1`
- Result Schema：`workspace/data/vfx_generation/schemas/material_trajectory_execution_result.schema.json`
- Run Schema：`workspace/data/vfx_generation/schemas/material_trajectory_execution_manifest.schema.json`

执行器支持：

- Scope：`material / renderer_mpb / slot_mpb`
- 值：`float / int / color / vector`
- Curve：`linear / ease_in / ease_out / smoothstep / step / pulse`
- Event：Shader Keyword、Texture Swap、Material Replace
- 资源审计：运行时 Material、截图 Texture2D、共享 RenderTexture 的创建与销毁

当前真实 R002 含 `float 56 / color 10 / vector 8` 条参数轨迹；没有可用的真实 `m_Ints` 候选。因此 int 是代码支持状态，尚不能声明为真实数据运行覆盖。

## 同步顺序

自动采样不使用 batchmode 下会挂起的 `WaitForEndOfFrame`。每个采样点固定执行：

```text
trajectory_apply_at_late_update
  -> material_snapshot
  -> camera_render
```

每条规格采 11 帧，即 10 个等间隔加起点；1 秒轨迹间隔为 0.1 秒。

## 信号对账

`raw_timeline_signals` 保留录制器的完整事实。例如 MPB 贴图替换会同时出现 scope provenance 和 `texture_changed`；Material Replace 可能同时造成大量属性变化。

`actual_signals` 只投影规格声明的主监督操作，但每项都必须在 raw timeline 中存在。`negative_trajectory` 由实际执行的负例变异确认。最终使用严格集合相等：

```text
sorted(spec.expected_signals) == sorted(result.actual_signals)
```

## R001 到 R002

R001 从 `.mat` YAML 读取参数时未核对当前 Shader API。全量在 `Mat_xingzhe_glow._UseUIAlphaClip` 暴露问题：YAML 仍保存该字段，但 `Material.HasProperty` 为 false。

Material Binding Audit r3 使用 Unity `Shader.GetPropertyCount/GetPropertyName/GetPropertyType` 生成：

- Material：730
- Shader API 属性：36,343
- Texture slot：5,136
- 已绑定 Texture slot：1,093

R002 只从 Shader API 仍存在且类型匹配的 YAML 值生成轨迹，并按属性类型区分 Color 与 Vector。R001 保留为失败证据，不覆盖；R002 是当前基线。

## 验证结果

Smoke：`workspace/data/vfx_generation/runs/material_trajectory_r002_smoke_r001`

- 7/7 类别通过
- 77/77 PNG 有效
- 0 Schema error
- 0 runtime resource leak

Full：`workspace/data/vfx_generation/runs/material_trajectory_r002_full_r001`

- 100/100 execution pass
- 1,100/1,100 PNG 文件有效
- 100/100 material timeline 有效
- 0 Schema error
- 0 candidate Material/Texture leak
- 0 run RenderTexture leak
- Scope：Material 36 / Renderer MPB 38 / Slot MPB 26
- Curve：Ease In 15 / Ease Out 4 / Linear 12 / Pulse 18 / Smoothstep 23 / Step 2
- Event：Keyword 2 / Texture Swap 16 / Material Replace 8

完整 manifest：`workspace/data/vfx_generation/runs/material_trajectory_r002_full_r001/run_manifest.json`

## 视觉边界

文件有效不等于图像证据可用。finalize 使用四角背景估计和背景相对可见面积检查：

- Material-state valid：100
- Image-training eligible：72
- Near blank on stable Quad：28
- 可见面积阈值：0.001

28 条近空白候选仍可用于 Material 状态、参数和事件学习，但必须排除出图像条件监督。它们通常需要原 Prefab Mesh、Particle vertex stream、UI canvas 或其他运行上下文；后续应为这些候选增加 context renderer，而不是伪造可见画面。

## 结论

MaterialTrajectorySpec 已从“课程规格”晋级为可运行、可对账的 Material 状态训练证据。当前可以安全使用 100 条状态轨迹学习参数和事件变化；其中只有 72 条可同时用于图像条件监督。尚未加入人工审美标签，也尚未训练模型。

## Context Renderer R030（2026-08-30）

针对 R002 中 28 条 stable Quad 近空白候选，新增隔离上下文重采。权威工程仍为 `UnityDemo/EffectDemo`，实际运行使用 `workspace/unity-render-staging/EffectDemoWeb2022R002`，Unity `2022.3.16f1c1`、URP `14.0.9`；上一轮 R001 保留不覆盖。

### UI/ParticleImage 上下文

两个 UI 候选：

- `mtc_045_emission_alpha_mat_ui_propitem_glow_1` -> `FX_UI_PropItem.prefab`
- `mtc_054_mpb_mat_kapaifenwei_02` -> `FX_ui_kapai_bing.prefab`

staging 使用与 Unity 2022 同版本的 `UnityEngine.UI` 兼容程序集恢复 `ParticleImage` Runtime。执行器不把 UI Graphic 强行当作普通 MeshRenderer：先匹配 Graphic 的实际材质，再保留组件级 `mainTexture`；捕获时使用 ParticleImage 生成的粒子状态建立独立 Mesh 代理，代理不挂在被记录 Prefab 根下，不污染材质时间线。由于 CanvasRenderer 不提供普通 MPB 接口，两个输入规格仍保留原 `control_scope=slot_mpb`，结果额外记录 `effective_control_scope=material`，实际信号为 `material_property_changed`。

### R030 结果

正式批次：`workspace/data/vfx_generation/runs/material_trajectory_context_r030/run_manifest.json`

- 28/28 MaterialTrajectory pass
- 308/308 PNG 有效，28/28 timeline 写出
- 0 Schema error，0 candidate material/texture leak，0 run RenderTexture leak
- 可见候选 10/28，图像监督 eligible 10/28；其余 18 条仍保持 material-state valid 但排除图像监督
- `mtc_045` 最大可见面积约 `0.994`，`mtc_054` 最大可见面积约 `0.0084`，均已从 UI 上下文近空白状态恢复

### 过程弯路

先尝试把 Canvas 挂到 Prefab 根节点并直接读取 `CanvasRenderer.GetMesh()`，但 `-noUpm` 缺少 UGUI 程序集且 CanvasRenderer Mesh 读取受 dirty/rebuild 时序影响；随后临时用标准/纯红材质排查，确认问题不是源纹理或 Shader 输出，最终移除临时材质和诊断日志。真正有效的修复是补齐 staging UGUI 编译闭包、从 ParticleImage 实际粒子状态建立代理，并把相机远裁剪面从 100 提升到 1000。

R030 只提升上下文和图像证据可用性，不把这些截图当成人工审美结论；正式人工评价仍需通过现有 review 页面完成。

## WebGL 材质时间线复核 R005（2026-08-30）

材质时间线的前三条 EffectDemo 2022 候选需要在浏览器中重新播放，不能只依据静态采样帧完成训练评价。复核仍以 `UnityDemo/EffectDemo` 为权威工程；构建在隔离 staging `workspace/unity-render-staging/EffectDemoWeb2022R008` 完成，输出为 `workspace/Builds/WebGL/VfxTrainingPlayer2022MaterialR005`。

### 兼容边界

`-noUpm` staging 不会自动加载内置 `com.unity.ugui`。此前为 `ParticleImage` 复制的 `UnityEngine.UI.dll` 虽能让 Editor 编译，却引用了 `UnityEditor.CoreModule`，在 WebGL linker 触发 `UnityEditor.dll assembly is referenced by user code`。最终仅把 Unity 2022 UGUI 的 `Runtime` 源码及 `UnityEngine.UI.asmdef` 放入 R008 的 `Assets/VFXSourceIngest/Compat/UnityUGUI/Runtime/`，不带 UGUI Editor 源码，也不带旧同名插件 DLL；主工程不改动。

### 构建与网页入口

- `unity projects verify workspace/unity-render-staging/EffectDemoWeb2022R008 --format json`：0 error、0 warning。
- R005 WebGL：`Build Finished, Result: Success`，Unity 退出码 0；3 个 Prefab、3 个训练候选均绑定，capture mode 为 `play_mode_runtime`。
- 构建产物：data 3,087,892 bytes、framework 373,136 bytes、wasm 17,257,982 bytes。
- 新 catalog：`workspace/data/vfx_generation/runs/trains_material_timeline_r001/webgl_catalog_r004.json`，播放器 URL `http://127.0.0.1:8784/`。
- 新评价批次：`workspace/data/vfx_generation/reviews/material_timeline_review_r006/`，页面 `http://127.0.0.1:8786/`。

评价批次从 `effectdemo_prefab_structure_audit_r3.json` 回填真实结构和材质统计，不再显示 `0 / 0`：

| Candidate | 粒子系统 | 材质 | 已绑定贴图 |
| --- | ---: | ---: | ---: |
| `source_prefab_001_fx_bosstips` | 2 | 2 | 2 |
| `source_prefab_002_fx_com_sheilder` | 4 | 3 | 7 |
| `source_prefab_003_fx_gun_fire` | 3 | 2 | 2 |

### 浏览器复验与标签边界

浏览器实际加载 Unity `2022.3.16f1c1`，运行时连接后加载遮罩透明且无事件拦截；切换 `FX_BossTips` 时运行统计为 2 个活动粒子 / 2 个 Renderer，切换 `Fx_com_sheilder` 时为 3 个活动粒子 / 3 个 Renderer，且截图可见蓝色护盾。`Fx_Gun_Fire` 能切换和重播，但固定镜头下只出现很小且很短的枪口火点，不能作为正向图像质量标签。

已生成 `ai_drafts.jsonl`，三条记录均为 `ai_draft_not_human_label`，仅用于预填中文固定选项。`prefab_human_review finalize` 在 0/3 人工保存时按设计拒绝完成，因此 AI 草案不会被误写成 `prefab_human_feedback.v1` 或进入训练偏好数据。人工在页面中确认或修正后，才可保存并最终生成 human label overlay。
