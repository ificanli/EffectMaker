# Unity VFX 初版制作流程规范

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
- 一份参数记录，包含版本、管线、资源依赖和性能结果。
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
→ 运行、截图和性能验证
→ 复盘与资产归档
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

## 四、验证门槛

### 视觉验证

- 正常速度、0.25 倍速和逐帧检查。
- 远景、中景、近景至少各检查一次。
- 单独关闭 Core、Impact、Support、Detail、Ground，确认每层职责清楚。
- 检查主体是否被辅助光、Bloom、雾效或细碎粒子抢走。
- 检查快入慢出、方向性溶解、残留时长和地面反馈是否连续。

### 工程验证

- `unity projects verify` 通过。
- Prefab 可独立打开，不依赖隐藏场景对象。
- 材质、贴图、模型、Timeline 和脚本引用无丢失。
- 参数记录与实际 Inspector 值一致。
- Unity 2022.3 和 Unity 6 的差异单独记录，不混写为同一结论。

### 性能验证

至少记录目标设备或编辑器中的：

- 帧率和 GPU/CPU Frame Time。
- 最大粒子数和每层粒子数。
- Draw Calls、透明 Overdraw 和材质数量。
- 纹理显存、Shader 变体和后处理成本。
- 是否需要 LOD、距离裁剪、对象池或合批。

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
