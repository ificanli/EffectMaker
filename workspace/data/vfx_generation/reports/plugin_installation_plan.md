# AI 式 VFX 生成辅助插件调研与安装记录

日期：2026-08-27  
对应 Beads：`vfx-2df.14`  
状态：首批项目级 skills 已安装，Unity 工程内 UPM 包未在本轮新增

## 结论

本轮选择的不是“帮 Unity 自动生成成品特效”的黑盒插件，而是一组支撑生成式 VFX 闭环的 agent skills。它们分别覆盖：

```text
Unity CLI/UPM 操作
  -> Shader Graph / URP / Render Graph 实现约束
  -> VFX 视觉可读性规则
  -> OpenCV 画面特征提取
  -> 数据集加载
  -> 轻量偏好模型训练
```

这些 skills 只能作为辅助能力，不能直接等同于已经验证过的 Unity 生产能力。每次真正用于 Unity 制作时，仍然必须留下 VFXSpec、候选、渲染截图、反馈、命令日志和人工视觉判断。

## 调研范围

本轮调研覆盖两类来源：

- Skills CLI 搜索：`unity vfx`、`vfx graph unity`、`unity shader`、`shader graph custom node`、`urp postprocessing`、`unity cli`、`unity package management`、`opencv computer vision`、`dataset loader`、`scikit learn machine learning`。
- GitHub 来源仓库：`unity-technologies/skills`、`mengto/skills`、`josiahsiegel/claude-plugin-marketplace`、`tondevrel/scientific-agent-skills`、`jeremylongshore/tons-of-skills-marketplace`、`eyadsibai/ltk`。

搜索结果中也出现了 Unreal Niagara、Roblox VFX、Pika 视频 VFX、Blender/Three.js VFX 和额外 Unity MCP/Editor 桥接类项目。它们暂不进入首批安装，原因见下方“暂缓安装”。

参考来源：

- [Unity-Technologies/skills](https://github.com/Unity-Technologies/skills)
- [IvanMurzak/Unity-MCP](https://github.com/IvanMurzak/Unity-MCP)
- [MengTo/Skills - create-game-vfx](https://github.com/MengTo/Skills/tree/main/agent-skills/game-development/create-game-vfx)
- [tondevrel/scientific-agent-skills](https://github.com/tondevrel/scientific-agent-skills)
- [JosiahSiegel/claude-plugin-marketplace](https://github.com/JosiahSiegel/claude-plugin-marketplace)
- [jeremylongshore/tons-of-skills-marketplace](https://github.com/jeremylongshore/tons-of-skills-marketplace)
- [eyadsibai/ltk](https://github.com/eyadsibai/ltk)

## 首批安装清单

| 顺序 | skill | 来源 | 用在生成式 VFX 闭环中的位置 | 本轮判断 |
|---:|---|---|---|---|
| 1 | `unity-cli` | `unity-technologies/skills` | Unity CLI、Editor 连接、构建、测试、日志、Pipeline/MCP 配置入口 | 必装。项目规则已要求优先 Unity CLI，它应排在所有 Unity 操作前面。 |
| 2 | `unity-package-management` | `unity-technologies/skills` | 非交互式管理 UPM 包，弥补 Unity CLI 不直接管理 UPM 的空缺 | 必装。以后添加 VFX Graph、Shader Graph、Recorder 等包时需要先走包管理规范。 |
| 3 | `shader-graph-create-custom-node` | `unity-technologies/skills` | 将 HLSL 函数封装为 Shader Graph 自定义节点 | 必装。Mask、Dissolve、Flow、Shard 等材质训练会需要可复用节点。 |
| 4 | `unity-shaders-rendering` | `josiahsiegel/claude-plugin-marketplace` | Shader Graph、ShaderLab、URP/HDRP、VFX Graph 和渲染管线参考 | 必装。覆盖范围比单一 Shader Graph 节点更宽，适合做材质和渲染实现审查。 |
| 5 | `urp-postprocessing` | `unity-technologies/skills` | URP Volume、Bloom、Tonemapping、Color Adjustments、Motion Blur 等 | 必装。完整特效节奏最终会牵涉镜头、峰值亮度、残留和后处理。 |
| 6 | `validate-urp-render-graph-renderer-feature` | `unity-technologies/skills` | 校验 Unity 6+ URP Render Graph Renderer Feature | 必装。AI 生成自定义 Renderer Feature 时容易出现资源接线和材质绑定错误。 |
| 7 | `create-game-vfx` | `mengto/skills` | 游戏特效可读性、触发、命中、持续、清理、性能边界 | 必装。它不是 Unity 专用，但能给 VFXSpec 和人工反馈表提供设计维度。 |
| 8 | `opencv` | `tondevrel/scientific-agent-skills` | 截图/视频的轮廓、边缘、面积、运动、光强、帧间差分析 | 必装。用于把“看着像不像”拆成可训练特征。 |
| 9 | `dataset-loader-creator` | `jeremylongshore/tons-of-skills-marketplace` | 将 runs、feedback、contact sheet 和特征表整理成训练输入 | 必装。支撑 `datasets/` 下的偏好对和训练样本索引。 |
| 10 | `scikit-learn` | `eyadsibai/ltk` | 训练首批轻量判断器、排序器、回归/分类 baseline | 必装。适合小样本阶段，不急着上深度学习大模型。 |

## 安装命令

如果需要在干净环境中重建首批 skills，按以下顺序执行：

```powershell
npx skills add unity-technologies/skills@unity-cli -y --copy
npx skills add unity-technologies/skills@unity-package-management -y --copy
npx skills add unity-technologies/skills@shader-graph-create-custom-node -y --copy
npx skills add josiahsiegel/claude-plugin-marketplace@unity-shaders-rendering -y --copy
npx skills add unity-technologies/skills@urp-postprocessing -y --copy
npx skills add unity-technologies/skills@validate-urp-render-graph-renderer-feature -y --copy
npx skills add mengto/skills@create-game-vfx -y --copy
npx skills add tondevrel/scientific-agent-skills@opencv -y --copy
npx skills add jeremylongshore/tons-of-skills-marketplace@dataset-loader-creator -y --copy
npx skills add eyadsibai/ltk@scikit-learn -y --copy
```

本轮实际安装时，`unity-technologies/skills` 源仓库内有一个无关的 `physics-3d-collision` skill 出现 YAML 解析警告；目标 skills 均显示安装成功。后续如果要安装该 physics skill，应单独处理其元数据问题。

## 安装验证

验证命令：

```powershell
npx skills ls --json
```

当前项目级 skills 应包含：

```text
beads
create-game-vfx
dataset-loader-creator
opencv
scikit-learn
shader-graph-create-custom-node
unity-cli
unity-package-management
unity-shaders-rendering
urp-postprocessing
validate-urp-render-graph-renderer-feature
```

锁定文件：

```text
skills-lock.json
```

skills 实体目录：

```text
.agents/skills/
```

## 暂缓安装

| 候选 | 暂缓原因 | 重新考虑条件 |
|---|---|---|
| Unreal Niagara 相关 skills | 引擎不匹配，概念可参考但不能直接落到 Unity 资产 | 需要专门研究 Niagara 表达方式并迁移到 Unity VFX Graph 时 |
| Roblox VFX/Animation skills | 平台和资源管线不匹配 | 只有当我们要抽象跨平台特效语法时再看 |
| Pika/Seedance/视频 VFX skills | 偏视频生成，不会直接产出 Unity 可编辑的 Prefab、Material、Shader 或 VFXSpec | 需要做参考视频或动态概念稿时 |
| Blender VFX/mesh/export skills | 对 Mesh/碎片/模型生成可能有价值，但不是首批闭环阻塞点 | `Shard`、破碎、几何轨迹和 mesh bake 成为主任务时 |
| Three.js procedural VFX skills | 有 Web 交互原型价值，但与 Unity 生产资产不同 | 需要先做浏览器可视化模拟器时 |
| 额外 Unity MCP/Editor 桥接 | 项目已有 Unity CLI/MCP 边界，重复安装可能造成配置冲突 | Unity CLI/Pipeline 无法覆盖必要实时编辑器操作，且确认不会破坏现有配置时 |
| 更重的深度学习/ComfyUI/训练框架 | 当前缺少足量人工偏好数据，上深度模型会先增加复杂度 | `datasets/` 中已有稳定样本、特征表和可复现实验后 |

## 使用规则

1. 先用 `unity-cli` 做 Unity 版本、项目、构建、测试、日志和 Editor/Pipeline 可用性检查。
2. 需要新增或调整 Unity UPM 包时，先用 `unity-package-management` 形成去重包清单，再通过 Unity Package Manager API 执行，不手改 `Packages/manifest.json`。
3. 生成材质、溶解、流动、切片、遮罩、拖尾等节点时，优先调用 `shader-graph-create-custom-node` 和 `unity-shaders-rendering` 的规则。
4. 涉及 Bloom、Tonemapping、Color Adjustments、Depth of Field、Motion Blur 或峰值残留时，使用 `urp-postprocessing` 做前置检查。
5. 生成自定义 URP Renderer Feature 后，用 `validate-urp-render-graph-renderer-feature` 做代码审查，再进 Unity。
6. 每个候选的审美/玩法意图先用 `create-game-vfx` 拆成 trigger、owner、duration、silhouette、color hierarchy、cleanup 和 performance cap。
7. 截图/视频进入训练前，用 `opencv` 抽取可度量特征，例如主体面积、边缘连贯性、亮度峰值、帧间运动和遮挡关系。
8. 训练样本进入 `datasets/` 前，用 `dataset-loader-creator` 梳理 loader、schema、split 和 provenance。
9. 小样本阶段用 `scikit-learn` 训练 baseline，优先做可解释的偏好排序/分类，不急着训练大模型。
10. 每次插件能力实际介入 Unity 制作，都要在对应 run 或 Beads 备注中记录输入、命令、输出、失败和人工结论。

## 与当前训练路线的关系

这批插件服务的是通用闭环，不只服务刀光主体弧：

| 训练模块 | 主要依赖 |
|---|---|
| 跨类型 VFXSpec 与适配器 | `create-game-vfx`、`unity-shaders-rendering` |
| Slash/Fire/Lightning/Shield 等候选生成 | `unity-cli`、`unity-package-management`、`shader-graph-create-custom-node` |
| 材质和贴图生成约束 | `shader-graph-create-custom-node`、`unity-shaders-rendering`、`opencv` |
| 画面可读性与自动特征 | `opencv`、`create-game-vfx` |
| 人工反馈数据集 | `dataset-loader-creator` |
| 首批偏好判断器 | `scikit-learn` |
| 完整节奏、峰值、残留和镜头关系 | `urp-postprocessing`、`validate-urp-render-graph-renderer-feature`、`opencv` |

## 下一步

插件安装完成后，不应继续扩大安装范围。`vfx-2df.10` 的跨特效 adapter 契约已完成；当前真正瓶颈是 `vfx-2df.18` 的 source Prefab 实际渲染、`capture_manifest.json`、联系表和人工反馈。只有这些真实样本暴露出具体工具缺口时，再补第二批插件。

## GitHub 参考库快照（2026-08-28）

公开 GitHub 页面星标、许可证与归档状态已记录在 [`github_vfx_reference_snapshot_2026-08-28.json`](github_vfx_reference_snapshot_2026-08-28.json)。这些项目默认用于阅读源码、样例和设计思路，不是本项目的批准安装清单。

当前优先级：

1. `Unity-Technologies/Graphics`：研究与主工程 URP `17.5.0` 对应的 SRP、Shader Graph 和 VFX Graph 源码；不要整库嵌入。
2. `mob-sakai/ParticleEffectForUGUI`：只有出现 UI 粒子需求时才单独做兼容性试验。
3. `keijiro/NoiseShader`、`Cyanilux/URP_ShaderGraphCustomLighting`：只选择单个函数或节点，在 Unity `6000.5.9f1` / URP `17.5.0` 下单独验证后再移植。
4. `Kino`、`Klak`、`StableFluids`、`BoatAttack`：当前作为研究材料，不安装，不改变现有 Unity MCP、CLI、URP 或渲染链。
