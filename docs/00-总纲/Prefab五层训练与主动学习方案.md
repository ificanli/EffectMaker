# Prefab 五层训练与主动学习方案

## 1. 目标

本方案用于上千个 Unity VFX Prefab 的低人工训练。技术结构和可运行性覆盖 100% 样本；非专业用户只判断特效元素、特效类型和是否可播放，不评价主体、层次、节奏、材质、构图或风格。审美监督来自专业特效视频、教程、专家明确结论、成品/过程对照和经过 Unity 复刻验证的证据。

默认人工比例为首轮 `5%~8%`，稳定后 `1%~2%`。人工减少不能通过降低证据门禁、把 AI 假设改成人工标签或把无法判断改成负例实现。

## 2. 五层不是质量等级

```text
technical_corpus
  -> visual_feature_only
  -> ai_pseudo_label
  -> human_gold
       -> regression_gold（冻结，只测试）
```

同一个 `sample_id` 可以拥有多层记录，但每层是独立 artifact，旧记录不可被新标签覆盖。所有层必须保存来源、模型/人工版本、置信度、训练权重、允许任务、禁止任务和分组信息。

## 3. technical_corpus

覆盖所有已扫描 Prefab，包括损坏和上下文依赖样本。保存 PrefabGraph、Transform、ParticleSystem、Renderer、Material/Shader/Texture/Mesh、GUID、依赖、授权、Missing Script、编译和 API 回读状态。

允许训练层级、组件、参数、资产路由、依赖错误和可编译性；禁止训练好坏、风格、Prompt 匹配和偏好。技术失败是技术负例，不是审美负例。

默认权重为 `1.0`，但只对明确列出的技术任务有效。

## 4. visual_feature_only

要求 `play_mode_runtime_isolated_multiview.v2` 捕获至少满足 `image_sequence_training_eligible=true`。保存连续帧、时序向量、可见面积、边界裁切、主体质心、色彩、峰值、动态材质和上下文限制。

允许视觉自监督、视频/图像向量、聚类、检索、新颖度和异常检测；禁止直接训练质量分、风格真值和 A/B 偏好。

Shader global 未插桩或 MPB 无法枚举时仍可保留为 feature-only，但 `full_visual_training_eligible=false`，不能升级为完整动态材质真值。

## 5. ai_pseudo_label

AI 伪标签来自 Judge、视觉近邻、簇传播或弱元数据 Teacher。必须保存 `label_source`、模型版本、置信度、模型分歧、父人工记录和距离；模型更新后允许失效重算。

伪标签只用于半监督训练和主动学习排序，不得进入人工黄金测试、模型晋级指标或覆盖人工修正。默认权重：高置信 AI `0.1~0.2`，簇传播 `0.3~0.5`，低置信预测为 `0`。

## 6. human_gold

非专业人工只在真实动态播放上分别确认两个维度，或标记无法播放、无法判断。`特效元素`允许多选，描述火焰、冰霜、雷电、水、风、土/岩石、光、暗影、毒、烟雾等内容属性；`特效类型`单选主要表现形态，描述刀光、爆点、爆炸、法阵、激光、飞行物、枪口、护盾、传送门、光环、拖尾等结构/用途。两个维度都允许新增中文标签，并分别持久化。

`无法播放` 和 `无法判断` 只进入排除记录。有效语义记录权重为 `1.0`，只允许 `effect_element_supervision`、`effect_type_supervision` 和 `pseudo_label_calibration`；质量、风格、主体、层次、节奏、材质、构图、偏好和模型晋级明确排除。

旧 Capture v1 人工标签可用于实验 Teacher，但标记 `pending_capture_v2_revalidation`，不得直接进入模型晋级和 regression gold。

## 7. regression_gold

语义回归可以从已通过 Capture v2 的用途 human gold 中冻结；审美回归只能来自专业专家结论或经过专业资料规则和 Unity 复刻交叉验证的证据。两者不得混用。冻结样本永不参与训练、伪标签传播、阈值选择和超参数选择；发生读取污染后必须更换回归集。

建议固定 `24~40` 条，覆盖爆炸、刀光、火焰、雷电、护盾、烟雾、法阵、水系以及瞬发、移动、地面、UI、脚本材质、全黑、错镜头和裁切边界。

## 8. 元素与颜色标签

元素、类型和颜色不是单一字段，必须区分四种身份：

| 身份 | 示例 | 所在层 |
|---|---|---|
| Prompt 目标 | `target.effect_family=fire`、`target.colors=[blue]` | condition，不是观察真值 |
| 技术/画面实测 | Particle startColor、材质 `_Main_Color`、帧 HSV/Lab palette | technical / visual |
| 语义判断 | `observed.element_tags=[fire, ember]`、`observed.color_tags=[orange, red]` | AI pseudo 或 human gold |

目录名和 `effect_family_hint` 只能写 `source_hint`。元素采用多标签，例如 `fire/ice/lightning/water/wind/...`；主要表现类型单独保存在 `effect_type`，例如 `slash/impact/explosion/magic_circle/laser/...`，不能再把刀光和火焰放入同一枚举。子视觉成分 `flame/ember/smoke/shockwave/shard/rune/...` 与层职责 `core/support/hit/residual` 继续保持独立。颜色同时保存数值 palette、语义色名和角色颜色，不能把 Prompt 蓝色直接当成实际蓝色。

## 9. 主动学习队列

默认队列预算为可评价样本的 `6%`，最少 16 条；模型稳定后允许降至 `1%`。队列构成：不确定性 40%、新簇代表 20%、模型分歧 15%、预测 Top 10%、预测 Low 5%、随机审计 10%。

语义人工频率分别参考元素多标签一致率和类型分类一致率：任一低于 80% 使用 10%，80%~90% 使用 5%，90%~95% 使用 2%~3%，两者连续两轮高于 95% 使用 1%。新元素或新类型提高语义抽样率；当前命中类统一为 `impact / 命中/爆点`，`hit` 只保留兼容别名。新风格、新 Shader 和审美模型晋级由专业资料教师与独立技术门禁处理，不转嫁给非专业用户。

## 10. 去重、聚类和泄漏

聚类特征同时包含 Graph 结构、Particle 参数、Material/Shader/Texture/Mesh 摘要和 Capture v2 时序/视觉特征。不能只按文件名或单帧 pHash。训练、验证、测试和 regression gold 按来源项目、Prefab 近邻簇和 Prompt 组隔离。

簇标签传播只允许同特效族、同风格、同资产路线且距离低于阈值的近邻；传播记录保留父 human gold 和距离，不能反向修改人工记录。

## 11. Judge 和 Ranker

Judge 每个任务头独立门禁。历史 45 条非专业人工训练出的 quality、core readability、layer separation、rhythm、material、composition 六个头只保留为实验失败证据，不再用于正式审美伪标签、回归或晋级；style_family 继续保持 blocked。新 Judge 必须从专业资料教师数据重新训练。

Preference Ranker 只使用同 Prompt、同特效族且两侧都有证据的专家对比、教程明确前后对比或验证过的 Unity 复刻对。非专业用户不承担审美 A/B。当前专业 pair 为 0，不得用语义用途选择代替偏好数据。

## 12. 晋级规则

AI 伪标签永不参与最终评估。Judge/Ranker/Controller 晋级必须使用冻结 regression gold，报告按特效族和风格拆分指标，并保留随机人工审计。Unity 编译成功、PNG 存在、像素可见或训练 loss 下降都不等于审美通过。

## 13. 当前执行结果（2026-09-03）

- 全量技术基线 `prefab_graph_full_r002`：Unity API 审计与磁盘均为 2115 个 Prefab；`technical_corpus=2115`、`PrefabGraph=2115`，Schema 错误、重复和 Graph 排除均为 0。技术状态为 1613 个可独立粒子播放、249 个需要上下文、107 个静态/上下文、146 个无有效输出；Missing Script 128、真实缺材质槽 153、缺 Shader 0。
- 资产注册表 `asset_registry_r003`：38376 个去重 Texture、599 个 Shader/HLSL、2138 个 Material。1826 张项目贴图可绑定且全部有像素 metrics；869 张有 semantic、1287 张有 slot、1321 张有 role 标签。54 个 Shader 为 Unity 可绑定，21 个 NB 和 523 个 GitHub 条目保持 reference-only；1225 个材质 usable，913 个被技术门禁阻塞。
- Prompt MaterialPlan `material_plan_prompt_r004`：按特效族、风格、层职责、颜色、性能、槽位和来源配对联合排序。火焰、雷电、刀光各 3 个候选完成 Unity 编译和保存后 API 回读，9/9 planned texture match，实际引用 8 张不同 Texture、4 个 Shader，生成占位 Texture 为 0。来源配对先验使 Capture 可见率从 5/9 提升到 8/9；剩余 near-blank 是技术负样本，不是审美负例。
- 首批增量 Capture `full_prefab_capture_r002`：从 1593 个严格 eligible Prefab 中按 14 个资源组、11 个元素/未分类组和复杂度抽取 64 条；64/64 Capture v2、1411 个有效帧、0 无效帧、0裁切、0运行错误。经错误洋红完整性门禁复算后，51 条可进入 visual feature，13 条仅保留 technical，其中 6 条为材质/Shader 渲染失败。由于 MPB 属性不可完整枚举且 Shader global 未插桩，`full_visual_training_eligible=0`，不能作为完整动态材质真值。
- 当前正式五层数据集 `prefab_five_layer_full_r009`：`technical_corpus=2115`、`visual_feature_only=102`、`ai_pseudo_label=1199`、`human_gold=32`、`regression_gold=0`。正式双维人工数据只来自 r010/r011；旧 41 条单维或非专业多维记录不进入当前元素/类型监督。错误洋红样本只进入 technical exclusion，不进入颜色、元素、类型、审美或正向生成监督。
- 主动学习 `prefab_active_full_r002`：2115 个 Prefab 重新分为确定性簇；41 个未评价视觉候选中抽取 16 条，重复、split 泄漏、非视觉和已有黄金污染均为 0。
- 中文修正入口 `prefab_active_review_full_r005`：16 条 Capture v2 动态样本已全部完成，9 条 AI判断正确、2 条材质有问题、5 条特效类型错误、0 条无法播放/无法判断；选项支持多选、待确认和备注，点击“确认本条”后才保存。所有 16 条均进入 human_gold。
- 下一轮中文修正入口 `prefab_active_review_full_r006`：16 条新主动学习样本，默认显示像素峰值帧，AI 标签和 11 个操作选项均使用中文，当前反馈为 `0/16`。
- 增量 Capture `full_prefab_capture_r003`：继续覆盖 64 个未重复 Prefab，完成 64/64、1466 个有效帧、0 裁切、0 运行错误。错误洋红门禁复算后为 50 条 visual_feature_ready、14 条 technical_only，其中 6 条为材质/Shader 渲染失败。
- 视觉完整性审计 `capture_visual_integrity_r002`：对 r002+r003 的 128 个捕获逐帧检查纯洋红面积及其在可见前景中的占比；116 个通过，12 个以 `unity_error_magenta` 技术排除。正常 `RocketMuzzlePink` 的纯洋红只占可见前景约 2.5%，不会误判；错误样本接近 100%。Unity 2022 正反烟雾捕获分别得到 `material_render_error`/`image_sequence_partial_material_fidelity`。
- 当前主动学习 `prefab_active_full_r007`：70 个未完成元素/类型确认的视觉候选中抽取 32 条，错误洋红、重复、split 泄漏、非视觉和已有黄金污染均为 0。
- r010/r011 语义复核已完成：32/32 条人工反馈全部保存并结算为 32 条 human_gold，19 条 AI判断正确、11 条特效元素错误、2 条特效类型错误、无法播放/无法判断为 0。命中类已统一为 `impact / 命中/爆点`；旧 `hit / 命中/受击` 和 `爆点/命中` 只作为兼容别名，不作为独立训练类别。正确的归一化统计见 r011 的 `normalization_manifest.json` 和 `normalized_review_summary.json`，旧结算摘要保留作历史证据。
- 当前语义复核入口 `prefab_active_review_full_r014`：元素与类型分为两个维度，元素可多选，类型单选；两边均可新增中文标签。命中类只显示“命中/爆点”。新批次从重建后的主动学习池抽取 32 条，错误洋红为 0，当前进度 `0/32`。
- Capture 取景/时序回归 `sword_slash_timing_r002`：按 `capture_category=slash` 识别 Mesh/刀光主体，独立累计主体包围盒，加入主体法线视角候选并使用正交取景；循环但仅 Burst 的主体使用 `delay+startLifetime` 估算单次视觉窗口。Unity 2022 实测组件最长周期 `4s`、主体窗口 `0.3s`，最终总时长 `0.3s`，采样间隔 `0.015s`、21 帧、1/1 候选、21/21 有效帧、0 裁切、0 运行错误。批次工具支持 `--prefab-path` 单条重捕，评审构建支持 `--capture-override` 替换指定 Prefab 的 Capture manifest，不覆盖旧证据。
- 历史 Judge `aesthetic_judge_partial_r004_regression_isolated`：使用 45 条非专业人工多维分数训练，quality MAE `1.3295`，主体、层次、节奏、材质、构图 MAE 分别约 `2.5313/1.8267/2.1538/0.9550/2.5633`，风格头阻塞。该模型不再接入当前复核页，也不作为正式审美教师。
- 专业资料底座 `course_knowledge_r003`：2651 条记录中 8 条 verified、15 条 tutorial_fact、318 条 engineering_mapping；同时满足专业来源、明确审美结论、中高证据、已定位动态帧/时间码和 Unity 复刻的正式审美教师样本当前为 0。因此页面明确显示“专业资料教师训练中”，不伪造审美判断。

当前人工只需在 `prefab_active_review_full_r014` 中确认特效元素、特效类型与播放状态。审美主线转到 `vfx-2df.29.8`：专业资料来源核验 -> 动态帧/时间码定位 -> 专家规则与前后对比 -> Unity 复刻交叉验证 -> 专业 Teacher 标签 -> 新 Judge/Ranker -> 独立审美回归。现有 GRU 结构模型仍只训练过旧 259 个 Prefab，必须在结构近重复分组完成后再使用 2115 个 Graph 重训。
