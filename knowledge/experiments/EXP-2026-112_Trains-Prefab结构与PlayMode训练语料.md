# EXP-2026-112 Trains Prefab 结构与 Play Mode 训练语料

## 目标

纠正“只训练 MaterialTrajectory、不训练已有 Prefab”的范围偏差。把 EffectDemo 中 `Trains_FX_All_001` 的 Prefab 转成 PrefabGraph、ParticleSystem、Renderer、Material、Mesh、Timing 和真实 Play Mode 图像证据；技术监督与人工审美监督严格分离。

## Unity 审计

- 工程：`UnityDemo/EffectDemo`
- Unity：`2022.3.16f1c1`
- Audit：`EffectDemoPrefabPlayabilityAudit` r2
- 稳定报告：`workspace/data/vfx_generation/audits/effectdemo_prefab_structure_audit_r2.json`
- Schema：`workspace/data/vfx_generation/schemas/prefab_structure_audit.schema.json`

审计 259 个主语料 Prefab：

| 状态 | 数量 |
|---|---:|
| particle_playable | 79 |
| particle_context_required | 141 |
| static_or_contextual | 2 |
| empty_or_invalid | 37 |

提取总量：Particle System 1411、Renderer 1377、Missing Script 288、具有 Particle 结构的 Prefab 220。

每个 Particle System 记录层级、Duration、Loop、Prewarm、Max Particles、Simulation Space、Start Delay/Lifetime/Speed/Size/Rotation、Emission、Burst、Shape、启用模块、Renderer Mode、Material 和 Mesh。

## Prefab Case R002

输出：`workspace/data/vfx_generation/datasets/trains_fx_all_002`

结合 Source Manifest、Material Audit r3、533 条本地 Texture tags 与 Prefab Audit r2：

| 监督状态 | 数量 |
|---|---:|
| needs_render_and_style_annotation | 59 |
| blocked_source_missing | 76 |
| runtime_context_required | 96 |
| empty_or_invalid | 26 |
| static_or_contextual | 2 |

技术训练资格：Prefab structure 259、Particle parameters 220、Play Mode render candidate 59、Blocked/context queue 200。

## Play Mode 渲染

Run：`workspace/data/vfx_generation/runs/trains_prefab_playmode_r002`

- Candidate / Capture Manifest / Material Timeline：59 / 59 / 59
- PNG：1154 / 1154 valid
- Render error：0
- Runtime material delta：0
- Contact sheet：8 页

自动像素门禁：

| 状态 | 数量 | 用途 |
|---|---:|---|
| pass | 2 | 图像 feature-only |
| warn | 34 | 图像 feature-only，等待人工判断 |
| reject / invisible | 23 | 仅保留结构与诊断帧 |

Material timeline 静态不表示 Prefab 没有动态；这 59 条主要通过 Particle System 运动。自动 pass/warn/reject 不是审美标签。

## 正式 TrainingExample

输出：`workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002`

- Prefab structure：259
- Particle parameter：220
- Rendered：59
- Image feature-only：36
- Aesthetic preference：0

每条样本保留 PrefabGraph、Particle 参数、Renderer/Mesh/Material、Animation/Timeline、依赖健康、技术状态、阻塞原因和来源。59 条渲染样本额外关联帧、Material Timeline、Contact Sheet 和 Auto Eval。

加载边界：

```text
prefab_structure             259
particle_parameters          220
play_mode_render_candidate    59
image_conditioned             36
aesthetic_preference           拒绝
```

## 已知限制

1. 76 条旧 Source Manifest 仍有 unresolved dependency edge；即使 Unity Prefab 能解析，也不能升级为依赖完整的生成正例。
2. 141 条 Particle Prefab 需要脚本、材质或运行上下文；37 条在固定采样点无有效输出。
3. 23 条依赖闭合 Prefab 在独立 Play Mode 场景不可见，主要需要 UI、角色挂点、外部移动或业务驱动，不能直接当坏资产删除。
4. 本轮 render spec 未携带新 R002 case 的完整 material-selection 上下文；正式 TrainingExample 从 `trains_fx_all_002` case 恢复 Material Audit r3 与 Texture tags，后续 prepare 必须直接传 review batch。
5. 人工风格与审美偏好仍为 0。

## WebGL 动态复核 R002 / R006

为避免把帧序列误当作完整动态表现，重新按 Unity audit 修正候选资格后，79 条 `particle_playable` Prefab 已进入真实 Play Mode 和 Unity 2022 WebGL review catalog：

- WebGL build：`workspace/Builds/WebGL/VfxTrainingPlayer2022PrefabReviewR004ShortWindow`
- Build manifest：Unity `2022.3.16f1c1`、`prefabCount=79`、`trainingLinkedPrefabCount=79`
- 服务：`http://127.0.0.1:8777/`
- 评价批次：`workspace/data/vfx_generation/reviews/prefab_human_review_r006_short_window`

为避免循环层把预览拉长，R004 将评价窗口限制为最长 3 秒、最大帧间隔 0.1 秒；79/79 条重新采集成功，`FX_BossTips` 在页面中为 0.00s 至 3.00s 共 31 帧。
- 页面：`http://127.0.0.1:8774/`

WebGL 映射不是按候选 id 或名称猜测，而是通过同一规范化 `Assets/...prefab` 路径得到 Unity AssetDatabase GUID catalog id。运行数据中的 `source_prefab_*` 与评价数据集中的 `trains_fx_*` id 被明确保留并做路径一致性校验。

`r005_all_webgl` 的状态分布为：`webgl_ready=79`、`needs_context=143`、`not_in_direct_playable_set=37`。前 79 条在评价页内嵌真实 Unity Canvas；其他条目显示中文技术原因，不把未渲染或上下文依赖误判为坏特效。

浏览器复验：选择 `trains_fx_024_fx_conecold` 后，iframe 内运行 `Fx_conecold` 且可见蓝色动态粒子；移动端 `390x844` 没有横向溢出。`Fx_JK_zidan02` 的 YOYO shader 在 WebGL 编译后有 2 个活动 Renderer、重播时 68 个活跃粒子；该样本的固定相机画面仍近空白，因此技术可运行不升级为审美可评价。`Eff_glow_box_blue` 纠正了旧路由：11/11 Play Mode 帧有效、WebGL 中有 14 个活跃粒子且可见；auto-eval warn 只表示固定相机下主体偏小。

构建期间发现 YOYO shader 的 package include 在 `-noUpm` staging 不可见，影响两条实际 catalog Prefab。详情、修复边界和复验见 `workspace/progress/ERROR_LOG.md` 的 `ERR-UNITY-051`：兼容宏只存在于 staging，不修改主工程 shader、材质或 manifest。

## 结论

现有 Prefab 已正式进入训练体系，不再只是导入资产。当前可训练的是结构、Particle 参数、依赖状态和图像特征；要把它们用于“什么更好看”和 Prompt 条件生成，还需要人工风格/质量评价以及上下文恢复。

## Prefab Audit R003 与导入修复

针对“之前能播放、现在部分不可见”的问题，重新执行了 `EffectDemo` Unity 2022.3.16f1c1 的 Prefab 审计，并对源工程 `E:/Trains/Unity` 做了逐条对照。

| 指标 | R002 误报 | R003 复核 |
|---|---:|---:|
| Prefab 总数 | 259 | 259 |
| 直接可播放 | 79 | 126 |
| 上下文依赖 | 141 | 94 |
| 原生空材质槽 | 未区分 | 113 |
| 真实缺失材质槽 | 114 | 1 |
| 缺失 Shader | 未记录 | 0 |

R002 的 114 个缺失材质槽来自 `Renderer.sharedMaterials` 的 null 数量，包含了源 Prefab 原本序列化的 `{fileID: 0}` 空槽。R003 使用 Renderer 的 `GlobalObjectId` 与源 Prefab 组件 fileID 精确读取 `m_Materials`，并递归处理嵌套 Prefab，因此不会再把合法空槽当作导入损坏。

唯一真实断链是：

```text
Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/Battle/Fx_xingzhejineng/eff/Fx_xingzhe_zhuangunzi .prefab
材质 GUID: 6bca70b520d27ed41b9f612c4b3334cb
```

该 GUID 在 `E:/Trains/Unity/Assets` 中同样没有 `.meta` 或可靠源文件，已记录为源工程缺失/角色上下文依赖，不绑定相似材质。

另外发现两个没有任何 Prefab/场景引用的 TMP 资产含 SVN 冲突标记，已完整保存在 `workspace/repair-quarantine/unity-conflict-assets-20260829` 后从 `EffectDemo/Assets` 移出，避免继续触发资源导入错误。

R003 报告：`workspace/data/vfx_generation/audits/effectdemo_prefab_structure_audit_r3.json`。主工程实时报告位于 `UnityDemo/EffectDemo/Library/VFXSourceIngest/prefab-playability-audit.json`。基于该报告和 R005 Play Mode 证据生成的技术数据集为 `workspace/data/vfx_generation/datasets/prefab_structure_r005c_training_r005`，人工评价批次为 `workspace/data/vfx_generation/reviews/prefab_human_review_r009_audit_r3_webgl`。
