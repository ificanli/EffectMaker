# Unity VFX 初版制作流程规范

> 本规范的教学复现阶段、参考视频证据和 Unity 截图验证统一维护于：[教学复现与 Unity 特效验证规范](教学复现与Unity特效验证规范.md)。本文保留通用资源、分层、材质和工程制作规则；阶段状态以统一入口文档为准。

## 适用范围

本规范用于当前 Unity VFX 学习工程的第一版生产流程，目标环境为 Unity 6、URP 和现有 `com.unity.pipeline` 自动化线。Unity 2022.3 工程仍作为基线保留；若两个工程的渲染结果、包版本或 Inspector 字段不同，必须在效果记录中标明版本。

本规范不是某一个效果的最终参数表。它规定资源如何组织、效果如何分层、参数如何记录、实验如何验收。具体数值先作为推荐起点，经过 Unity 场景验证后才能升级为稳定规则。

## 一、标准交付物

每个可复用效果至少包含：

```text
Assets/Art/VFX/<EffectId>/
  Textures/Source/
  Textures/Processed/
  Meshes/
  Materials/
  Shaders/
  ParticleSystems/
  Prefabs/
  Scenes/
  Timelines/
  Documentation/
```

交付对象：

- 一个根 Prefab：`VFX_<Category>_<EffectName>`。
- 一个验证场景：`VFX_Test_<EffectName>`。
- 一个完整播放 Timeline，或一个明确的触发入口。
- 一份参数记录，包含版本、管线、资源依赖和当前验证结果；性能字段在对外发布阶段补齐。
- 一份复盘记录，说明视觉目标、已验证结论、失败方案和未解决问题。

## 二、生产流程

```text
需求与镜头约束
→ 参考和证据拆解
→ 形体/颜色/节奏草图
→ 灰盒模型与基础材质
→ 主体层与冲击层
→ 支撑、残留和地面反馈
→ Shader/UV/溶解细化
→ Timeline 与触发逻辑
→ Prefab 封装
→ 运行、截图和参数回读验证
→ 复盘与资产归档
→ 对外发布前性能验证
```

每一步只解决当前阶段的问题，不在灰盒阶段堆叠纹理和后处理。

### 1. 需求与镜头约束

先记录用途、镜头距离、目标屏幕占比、持续时间、触发方式、背景、目标平台和性能预算。效果必须先回答“观众应该先看到什么”，再决定技术组合。

### 2. 参考和证据拆解

至少拆分：

- 主轮廓和识别点。
- 前摇、爆发、峰值、收束和残留。
- 主色、辅助色、明暗层级和高亮位置。
- 运动方向、空间层次、镜头关系和地面反馈。
- 可观察事实、推测参数和待验证假设。

视频或外部资料没有连续音画和工程证据时，只能作为参考入口，不能直接生成稳定制作规则。

### 3. 灰盒阶段

先用无纹理或极简纹理实现：

- 主体形体和方向。
- 尺寸、Pivot、空间位置。
- 生命周期和节奏曲线。
- 主层与冲击层的时序。

灰盒通过条件：静态轮廓可读、动作方向明确、完整播放后有收束，且不依赖高 HDR 或后处理才能看清主体。

### 4. 分层制作

推荐按职责拆成以下层，而不是把所有内容放进一个粒子系统：

| 层 | 职责 | 常见实现 |
|---|---|---|
| Core | 主轮廓、核心亮部、主要识别点 | Mesh、Particle System 或 VFX Graph |
| Body | 主体体量、宽度、形态变化 | Mesh、Flipbook、粒子 |
| Impact | 命中、爆发、接触反馈 | Burst、圆环、碎片、短时高亮 |
| Support | 灰/暗支撑、空间层次、慢速残留 | 低亮度 Mesh、粒子、噪声 |
| Detail | 星线、细碎片、局部纹理 | 子粒子、Flipbook、局部材质 |
| Ground | 地面滑痕、扰动、阴影或范围反馈 | 地面 Mesh、Decal 或投影方案 |
| Camera | 镜头震动、景深、曝光等 | Timeline、Cinemachine 或后处理 |

层级必须能单独关闭，便于 AI 和人工做 A/B 对照。

### 5. 材质和 Shader 阶段

先确定深度和混合行为，再调整颜色：

1. Blend：Alpha、Premultiply 或 Additive。
2. Cull：通常为 Back，双面效果才使用 Off。
3. ZWrite：透明效果默认关闭，需写深度时必须记录原因。
4. ZTest：默认遵循场景深度，特殊穿透效果必须单独验证。
5. 排序：使用 Renderer 队列、Sorting Layer 或粒子排序，避免依赖偶然层级。
6. HDR/Emission：先保证轮廓可读，再增加局部高亮，禁止用持续过曝代替形体。

Shader 参数按以下组记录：

- Shape：宽度、长度、半径、边缘柔和度。
- Color：主色、辅助色、边缘色、颜色插值。
- Alpha：整体透明度、软边、深度淡出。
- UV：方向、速度、缩放、平铺、Offset。
- Dissolve：Mask、阈值、边缘宽度、推进方向。
- Motion：顶点偏移、噪声尺度、强度、速度。
- Lighting：Emission、辅助光、受环境影响的部分。

### 6. Timeline 和触发

每个效果至少定义以下时间段：

```text
Prewarm/Anticipation → Build → Burst/Impact → Sustain → Dissolve/Residual
```

推荐先建立一个可读的时间基线，再调整重叠：

- 前摇：约 0.05–0.25 秒。
- 主体建立：约 0.10–0.40 秒。
- 冲击峰值：短于主体持续时间。
- 残留：比冲击慢，负责可读性和空间反馈。
- 收束：优先使用定向溶解、缩小或降低密度，避免整层同时消失。

这些数值是实验起点，不是跨项目硬规则。必须在目标镜头和完整播放中复核。

## 三、资源初版基线

### 贴图

- 文件名：`T_VFX_<内容>_<用途>`，例如 `T_VFX_Noise_Dissolve`。
- Base Color、Emissive 等颜色数据使用 sRGB；Mask、Noise、Ramp、Normal 等数据纹理按用途关闭 sRGB。
- Mask 通道必须写入文档，例如 `R=主体、G=边缘、B=溶解、A=透明度`。
- 记录分辨率、压缩、MipMap、Wrap、Filter、是否序列帧、UV 方向和预乘 Alpha。
- 序列帧必须记录行列数、播放帧率、循环方式和首尾是否无缝。
- 默认先从 512 或 1024 宽度开始；只有主体占屏大、近景或细节确有收益时才提升分辨率。

### 模型

- 平面：刀光、贴片、局部纹理和屏幕朝向效果。
- 弧面/带厚度网格：需要空间轮廓、侧面或视角变化的主体。
- 地面网格：滑痕、范围反馈、局部扰动和投影替代方案。
- 记录面数、法线、Pivot、UV0、UV1、顶点色和是否允许负缩放。
- UV0 服务主纹理，UV1 仅在烘焙/光照/特殊空间映射需要时使用；不可无记录地复用。
- 模型必须在目标镜头下检查拉伸、接缝、背面剔除和边缘消失。

### 材质

- 材质名：`M_VFX_<主体>_<层用途>`，例如 `M_VFX_Blade_Core`。
- 每个材质记录 Shader、Blend、Cull、ZWrite、ZTest、Queue、主纹理、Mask 和关键数值。
- 主层、支撑层、冲击层和地面层尽量使用独立材质实例，便于单层调试。
- 材质参数分为“根控制参数”和“层局部参数”，整体强度、整体时长和主题色优先集中管理。

### Particle System

粒子系统名使用 `PS_<EffectName>_<Layer>`。至少记录：

- Duration、Loop、Start Delay、Start Lifetime。
- Start Speed、3D Start Size、3D Start Rotation。
- Start Color、Emission Rate、Burst 数量和时间。
- Shape、Simulation Space、Scaling Mode、Gravity。
- Size over Lifetime、Color over Lifetime、Rotation over Lifetime。
- Noise、Collision、Trails、Sub Emitters 和 Renderer 设置。
- Max Particles、材质、排序、软粒子和目标平台限制。

推荐起点不是固定答案：

- Core：少量、高可读、短生命周期。
- Impact：短 Burst、较大尺寸差异、局部高亮。
- Support：低速、低亮度、较长生命周期。
- Detail：数量受控、尺寸错位、不能覆盖主体轮廓。
- Ground：速度和扩散慢于主冲击，避免整片同时溶解。

### 资源类型处理原则

贴图和模型只是外部输入的一部分。材质、Shader、UnityPackage、资料文档、压缩包以及 Unity 工程内的 Prefab、Scene、Timeline、脚本和 Volume 配置必须分别处理：

- `texture`：验证尺寸、通道、sRGB、Alpha、压缩、序列帧和 UV；缺失时可用程序纹理或纯色占位。
- `model`：验证轴向、单位、Pivot、法线、UV、材质槽和动画；缺失时可用内置几何体或程序网格占位。
- `material`：检查 Shader 和贴图依赖；外部 `.mat` 不直接视为 URP 可用材质，必要时在目标工程重建。
- `shader`：检查 Unity 版本、URP/HDRP/Built-in 依赖、编译和参数；缺失时用官方 URP Shader、Shader Graph 或最小自有 Shader 占位。
- `package`：不自动解压或导入 `.unitypackage`；先做来源、版本、授权和隔离工程验证。
- `document`：作为来源、授权、参数和证据输入，进入资料/知识流程，不当作运行时资产。
- `archive`：只记录包本身；解包必须在隔离目录进行，解包结果重新索引后才能使用。
- Unity 工程资产：Prefab、Scene、Timeline、脚本和 Volume 由 Unity 工程管理，必须通过 `.meta`、`projects verify`、Pipeline 回读和 Play Mode 验证。
- 其他资产：音频、字体、UI 图集、配置和外部插件先登记格式、授权和运行时依赖，找不到时可禁用可选功能或使用占位，不得静默引入未登记依赖。

这些类别的共同规则是：未命中时先复核查询；能用占位继续验证就标记 `asset_status: placeholder` 和 `visual_fidelity: experimental`；需要正式资产时创建生成或获取任务；新文件必须重新索引并获得 `asset_id` 后再进入正式 Unity manifest。

### 7. 样本资源到 Unity 的最小闭环

资源库中的素材不能直接凭文件名使用。先从 `E:\Unity特效人工智能学习\resource` 选择少量样本，记录来源、SHA-256、授权状态和目标用途，再复制到当前 Unity 工程的专用目录：

```text
Assets/Art/VFX/<EffectId>/
```

当前 Unity 6 ResourceSmoke 样本采用：

```text
Assets/Art/VFX/Samples/ResourceSmokeTest/
  Meshes/
  Textures/
  Materials/
  Prefabs/
  Timelines/
  ResourceSmokeTest_manifest.json
```

最小步骤：

0. 先查询结构化资源索引；记录 `asset_id`、`relative_path`、`sha256`、`license_status` 和目标用途。若未命中，按《新资源加入与扫描验收指南》的资源缺口分支处理：先复核查询，再使用占位资源继续逻辑验证，或创建生成/授权获取任务；新生成、转换或获取的资源必须重新扫描并获得稳定 `asset_id` 后才能进入正式 Unity 资产清单。
1. 导入少量 FBX、贴图并等待 `.meta` 生成。
2. 用 `unity projects verify` 检查项目结构。
3. 创建根对象和职责明确的层级，例如 `VFX_ResourceSmoke/Core/Impact/Residue`。
4. 给各层添加 `ParticleSystem`，设置生命周期、Burst、速度、尺寸和颜色。
5. **先执行视觉轮廓门禁：** 用纯色、不透明、双面材质和程序化/稳定 Mesh 只显示主体层；在目标相机和目标位置截图，确认刀光/主体轮廓清晰可辨、占据预期画面区域。门禁失败时停止，不进入贴图、Bloom、暗层或细节制作。
6. 创建 URP 粒子材质，绑定 `_BaseMap`、`_EmissionMap`、颜色和深度/混合参数。主体 Mesh 材质与粒子材质必须分开，不能用带不确定透明度的粒子贴图承担主体轮廓。
7. 将材质绑定到每层 `ParticleSystemRenderer`，再回读 `m_Materials[0]` 确认引用没有丢失。
8. 保存根对象 Prefab，创建 60 FPS Timeline，并添加 Activation 或其他需要的轨道。
9. 进入 Play Mode 前确认 Editor 状态为 `playing`；对 `playOnAwake=false` 的系统显式触发播放；在主体爆发窗口采集至少两个时间点的截图。
10. 视觉截图必须同时检查：主体轮廓可辨、主体占用区域、背景对比、辅助层是否抢主体、两个时间点是否有可解释变化。文件存在、PNG 可解码或少量像素变化都不能单独作为视觉通过。
11. 通过轮廓门禁后，再按 A/B 顺序逐层加入材质、暗层、色彩层、亮层、运动和溶解；每一步截图不通过就回退。
12. 将结果写入实验记录；未经过完整验证的结论保持 `experimental`。

正式 Unity manifest 至少保存以下追踪字段：

```json
{
  "asset_id": "<resource-index-id>",
  "source": "<original-source-path>",
  "index_relative_path": "<resource-relative-path>",
  "target": "<unity-project-path>",
  "sha256": "<source-or-target-content-hash>",
  "license_status": "unknown"
}
```

复制到 Unity 后应重新计算目标文件 SHA-256，并与索引和 manifest 比对；不一致时停止材质绑定和正式验证，先查明复制或转换原因。占位资源必须在记录中标记 `asset_status: placeholder` 和 `visual_fidelity: experimental`，不能冒充正式资产。

示例验证结果（只作证据，不是跨项目硬参数）：

- `M_VFX_ResourceSmoke_Core` 使用 `Universal Render Pipeline/Particles/Unlit`。
- `_BaseMap=T_Dissolve_04.png`，`_EmissionMap=T_Spark16A.png`。
- `Core`、`Impact`、`Residue` 均绑定同一材质并完成回读。
- 生命周期为 Core `1.0s`、Impact `0.45s`、Residue `1.8s`。
- 已生成 Prefab、Timeline、Activation 轨道和 1280×720 运行截图。

该样本闭环先验证资源导入、材质、粒子、Prefab、Timeline、运行和截图；不要求在学习阶段完成目标设备性能测试。

### 8. 常见自动化错误排查

- `CliCommandAttribute` 或 `CliCommand` 找不到：检查 Editor 脚本是否包含 `using Unity.Pipeline.Commands;`，然后执行 `unity command recompile`，轮询 `recompile_status`。
- `Pipeline server` 超时：先检查 FBX/贴图是否仍在导入、Editor 是否 ready；不要在同一个 Editor 上并发执行写操作。
- 以 `/VFX_ResourceSmoke/Core` 传递层级路径时被 Git Bash 转成 Windows 路径：改用 Pipeline 返回的 `globalId`。
- `.meta` 缺失：等待 Unity 完成导入后再次执行 `unity projects verify`，不要手工伪造 GUID。
- 日志里仍有旧错误：结合最新 `recompile_status`、当前命令注册和实际执行结果判断，不能只看历史 `Editor.log`。

## 四、验证门槛

### 视觉验证

- **轮廓门禁优先于工程门禁：** 纯色主体必须先在目标相机中可辨，再加入贴图、发光、暗层和细节。
- 正常速度、0.25 倍速和逐帧检查。
- 远景、中景、近景至少各检查一次。
- 至少采集主体建立、爆发峰值、收束三个时间点；对照版本至少比较两个不同时间点。
- 单独关闭 Core、Impact、Support、Detail、Ground，确认每层职责清楚。
- 检查主体是否被辅助光、Bloom、雾效或细碎粒子抢走。
- 检查快入慢出、方向性溶解、残留时长和地面反馈是否连续。
- 截图验证必须保留人工视觉判断；自动像素指标只能辅助定位，不能替代“这是不是目标效果”的判断。

### 工程验证

- `unity projects verify` 通过。
- Prefab 可独立打开，不依赖隐藏场景对象。
- 材质、贴图、模型、Timeline 和脚本引用无丢失。
- 参数记录与实际 Inspector 值一致。
- Unity 2022.3 和 Unity 6 的差异单独记录，不混写为同一结论。

### 对外发布前性能验证

性能不是当前学习闭环的阻塞条件。效果完成视觉、工程和运行验证后，先标记为 `experimental` 或内部可用；只有准备对外发布、交付或进入目标设备时，才必须补齐：

- 目标设备帧率和 GPU/CPU Frame Time。
- 最大粒子数和每层粒子数。
- Draw Calls、透明 Overdraw 和材质数量。
- 纹理显存、Shader 变体和后处理成本。
- 是否需要 LOD、距离裁剪、对象池或合批。

编辑器中的性能统计只能作为开发基线，不能替代目标设备测试，也不能提前把编辑器数据写成通用预算。

## 五、AI 自动化边界

AI 可以负责：

- 按模板创建目录、Prefab、场景和基础层级。
- 创建和修改已命名的 GameObject、Particle System、材质和参数。
- 读取 Inspector、运行状态、Console、日志和截图。
- 执行对照实验并保存前后参数和结果。

AI 不应自动决定：

- 未经验证的视觉规则是否升级为规范。
- 是否接受明显过曝、轮廓丢失或性能超预算的效果。
- 外部 GitHub 插件的许可证、维护状态和安全性。
- 破坏基线工程、升级 Unity 版本或覆盖原始资源。

每次自动修改必须留下：目标路径、修改前状态、修改后状态、Unity 版本、命令/工具、日志、截图和人工判断。命令成功不等于效果正确。

## 六、插件策略

初版只依赖 Unity 官方组件和当前项目包：URP、Shader Graph、Particle System、Timeline，以及 Unity 6 工程中的 Pipeline package。Visual Effect Graph、Cinemachine、Addressables 只有在需求明确时加入。

GitHub 插件采用白名单制：必须有明确能力缺口、版本兼容说明、许可证记录、源码来源、回滚方式和最小验证场景。没有这些信息时，不把插件加入项目基础依赖。
