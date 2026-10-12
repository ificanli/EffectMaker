# AI 式特效生成工作区

本目录用于启动类似 AI 生图的 Unity 特效生成闭环。它不是单个刀光版本的输出目录，而是保存 prompt、结构化规格、候选、渲染记录、人工反馈和训练数据的工作区。

对应 Beads 系列：`vfx-2df`（AI式特效生成闭环规划与试点）。

## Prefab 五层低人工训练

当前正式方案见 `../../../docs/00-总纲/Prefab五层训练与主动学习方案.md`，首轮体系任务为 `vfx-2df.37`，新 Prefab/资产注册/MaterialPlan 扩展为 `vfx-2df.38`。实际流程是：

```text
technical_corpus
  -> visual_feature_only
  -> ai_pseudo_label
  -> 主动学习有限队列
  -> human_gold
  -> regression_gold（冻结，只评估）
```

当前产物：

- `datasets/prefab_graph_full_r002/`：2115/2115 technical record 与 PrefabGraph，Graph 排除为 0。
- `asset_registry/asset_registry_r003/`：Texture/Shader/Material 统一注册表；只有 Unity 审计通过的 Assets 条目可绑定，NB/GitHub 仍为 reference-only。
- `generated/material_plan_prompt_r004/`：火焰、雷电、刀光真实 Shader×Texture×Material 配对；Unity 9/9 编译与保存后贴图回读通过。
- `datasets/material_plan_validation_r001/`：8 个可见配对和 1 个 near-blank 技术负样本，不含审美标签。
- `captures/full_prefab_capture_r002/`：64 条新来源 Capture v2、1411 个有效帧；正式报告位于 `reports/full_prefab_capture_r002/`。
- `datasets/prefab_five_layer_full_r001/`：2115 technical、60 visual、703 AI pseudo、41 human gold。
- `datasets/prefab_five_layer_full_r002/`：历史边界下的数据集；包含已撤销的非专业审美标签，不再作为正式审美训练输入。
- `active_learning/prefab_active_full_r001/`：2115 个 Prefab、92 个簇、58 个 eligible、16 条人工预算。
- `active_learning/prefab_active_full_r002/`：41 个未评价视觉候选、16 条下一轮人工预算；重复、split 泄漏和已有黄金污染均为 0。
- `reviews/prefab_active_review_full_r005/`：历史复核批次；经 `prefab_active_review_full_r005_semantic_r001` 重分类后，仅 9 条类型正确记录保留为语义 human_gold，5 条缺正确用途的类型错误待重标，2 条非专业材质意见排除。
- `reviews/prefab_active_review_full_r006/`：下一轮 16 条 Capture v2 动态帧 + 默认峰值帧 + 全中文 AI 标签和 11 个反馈动作，当前进度 `0/16`。
- `captures/full_prefab_capture_r003/`：64 条未重复 Prefab 的增量 Capture v2；64/64 完成，56 条 visual_feature_ready、8 条 technical_only、1466 个有效帧。
- `datasets/prefab_five_layer_full_r003/`：历史边界下的数据集；保留作审计，不用于正式审美训练。
- `active_learning/prefab_active_full_r003/`：96 个未评价视觉候选，抽取 32 条集中人工预算，队列门禁全 0。
- `reviews/prefab_active_review_full_r007/`：未提交的旧审美复核页，已由语义用途页 r008 取代。
- `reviews/prefab_active_review_full_r005_semantic_r001/`：非专业反馈重分类结果；9 条语义 human_gold、5 条缺正确用途待重标、2 条审美意见排除，审美训练任务混入为 0。
- `datasets/prefab_five_layer_full_r004/`：错误洋红门禁前的历史语义数据集；2115 technical、113 visual、725 AI pseudo、9 semantic human gold、0 regression。
- `active_learning/prefab_active_full_r004/`：错误洋红门禁前的历史主动学习池；104 个视觉候选、32 条语义人工预算。
- `reviews/prefab_active_review_full_r008/`：历史用途复核页；保留已提交反馈和错误洋红修复前的队列证据，不覆盖。
- `audits/capture_visual_integrity_r002/`：128 个 Capture v2 的错误洋红审计；116 pass、12 technical exclusion，正常粉色反例不误判。
- `datasets/prefab_five_layer_full_r005/`：错误洋红和元素/类型伪标签修正前的历史正式数据集；保留作审计，不作为当前语义训练入口。
- `active_learning/prefab_active_full_r005/`：历史主动学习池；保留作审计，不作为当前语义训练入口。
- `reviews/prefab_active_review_full_r009/`：元素与类型拆分前的历史单维复核页；保留 16 条旧反馈，不直接进入拆分后的语义监督。
- `reviews/prefab_active_review_full_r010/`：已完成的 32 条双维人工复核原始批次；保留原始反馈与页面证据。
- `reviews/prefab_active_review_full_r011/`：r010 的归一化结算批次；32/32 human_gold、0 exclusions，命中类统一为 `impact / 命中/爆点`；`normalization_manifest.json` 与 `normalized_review_summary.json` 保存归一化规则和正确的元素/类型动作统计。
- `datasets/prefab_five_layer_full_r007/`：旧正式双维语义数据集，保留作审计。
- `datasets/prefab_five_layer_full_r008/`：曾生成的归一化数据集，保留作审计。
- `datasets/prefab_five_layer_full_r009/`：当前正式双维语义数据集；2115 technical、102 visual、1188 AI pseudo、32 human gold、0 regression；不含旧单维 human gold，且命中类只有 `impact`。
- `active_learning/prefab_active_full_r006/`：历史主动学习池，保留作审计。
- `active_learning/prefab_active_full_r007/`：基于当前正式数据集的下一轮主动学习池；70 个视觉候选中抽取 32 条，门禁全 0。
- `reviews/prefab_active_review_full_r012/`：历史双维复核页，保留作审计。
- `reviews/prefab_active_review_full_r013/`：历史下一轮双维复核页，保留作审计。
- `reviews/prefab_active_review_full_r014/`：当前 32 条双维复核页；特效元素可多选，特效类型单选，命中类只显示“命中/爆点”，当前 `0/32`。r010 的 32 条人工结果已在 r011 结算完毕。
- `course_knowledge/professional_aesthetic_teacher_readiness_r001/`：专业审美 Teacher 首次门禁审计；2651 条课程记录中 161 条进入补证候选，正式 teacher-ready 为 0，缺专业来源核验、明确审美结论、评价轴和 Unity 复刻。
- `captures/sword_slash_framing_r001/`：指定 Prefab 的 Capture v2 取景回归样本；保留旧 `full_prefab_capture_r002/` 作为对照，不覆盖历史证据。
- `captures/sword_slash_timing_r002/`：指定 Prefab 的主体视觉窗口时序回归样本；总时长 0.3s、间隔 0.015s、21 帧，组件最长周期 4s 作为审计信息保留。
- `captures/material_error_smoke_r001/` 与 `captures/pink_effect_smoke_r001/`：Unity 2022 错误洋红分类正反回归；前者禁止进入图像训练，后者保持可用。
- `models/aesthetic_judge_partial_r002/`：历史非专业审美评分模型，仅保留实验证据，不进入正式推理或晋级。
- `regression/prefab_regression_gold_r002/`：2 条冻结回归、45 条隔离 Judge 输入和回归评估。
- `models/aesthetic_judge_partial_r004_regression_isolated/`：历史非专业审美六头 Judge；误差较大、风格阻塞，已退出当前复核链路。

当前专业 Teacher catalog 为 `professional_teacher_verified_r008`，共有 9 条同时满足专业来源、明确判断、动态证据和 Unity 复刻的窄轴规则；对应 readiness 为 `professional_aesthetic_teacher_readiness_r011`，9/9 ready。非专业元素/类型标签不能替代审美监督；人工只异步修正元素、类型与播放状态。

概念导览：`../../vfx_generation_architecture.html`。先阅读该页面理解 Prompt、VFXSpec、候选、Unity 渲染、自动评价和人工反馈的边界，再进入本目录的 schema、run 和工具。

训练标准：`../../../docs/30-操作指南/生成式VFX训练标准.md`。该文档是特征矩阵、人工偏好、排序模型、权重晋级和下一轮 VFXSpec 的权威规则。

## 目标

把特效制作从单版本手工调参，改为：

```text
VFX Prompt
  -> VFXSpec
  -> 批量候选生成
  -> Unity 多时间点渲染
  -> 候选联系表
  -> 人工偏好反馈
  -> 训练数据沉淀
  -> 下一批候选变异
```

## 当前优先级：MVP 闭环

当前材质子主线已进入 `MaterialTrajectorySpec -> Unity material timeline -> WebGL feedback` 阶段。首批 100 条规格位于 `curricula/material_trajectory_curriculum_r001/`；它们使用真实 Material/Shader/Texture，但在 Unity 执行和验证前仍不是训练样本。

短期不继续扩展资料吸收、完整刀光成品或跨类型大而全训练。先证明一个最小闭环能跑通：

```text
SlashArc prompt
  -> 30~50 个主体弧候选
  -> Unity Play Mode 自适应时间与多视角批量截图
  -> 自动硬过滤
  -> 人工 Top K 反馈
  -> 下一轮局部变异
```

第一轮成功标准不是“生成最终成品”，而是：机器能稳定生成一批可比较候选，自动淘汰明显失败项，并把人工选择转成下一轮搜索信号。

批量 run 汇总、contact sheet 和 `auto_eval.jsonl` 由 `workspace.tools.vfx_generation.run_pipeline` 负责生成，入口默认读取 `runs/<run_id>/candidates/<candidate_id>/spec.json` 和对应的 `capture_manifest.json`。

评价与反馈工具：

```text
workspace.tools.vfx_generation.evaluator
  - 硬过滤后的可测渲染分数：readability/timing/material/camera/performance
  - 特效族专用规格先验：slash/fire/lightning/shield/magic_circle/smoke/explosion/water
  - 所有结果带 provenance；规格先验不是图像理解，也不是最终审美验收

workspace.tools.vfx_generation.feedback
  - create：生成一条可追溯反馈记录
  - append：校验后追加到 run/feedback.jsonl
  - validate：校验候选 ID、决策、分数和成对比较引用
  - summarize：汇总有效反馈的平均排名、决策统计和成对胜负
```

示例：

```bash
python -m workspace.tools.vfx_generation.feedback create --run-root <run> --candidate-id <candidate> --reviewer human --decision partial --summary "保留尖端，重做中段宽度" --specialized-score sharpness=4 --next-mutation "降低中段宽度"
python -m workspace.tools.vfx_generation.feedback validate --run-root <run>
```

自动评价负责淘汰明显失败候选和排序辅助；它不替代实际图片阅读，也不把任何 `candidate_score` 直接当作最终视觉通过。

### MVP 交付门槛

- 每个候选必须能追溯到 `prompt`、`negative_prompt`、`VFXSpec`、`seed`、`generator_version`。
- 每个候选必须有 `play_mode_runtime_isolated_multiview.v2` 动态截图记录，至少覆盖前摇、峰值和收束；请求时间、模拟时间、墙钟时间和 Unity frame 必须可追溯。
- 每个 run 必须产出 `run_manifest.json`、候选 `spec.json`、`auto_eval.jsonl`、`feedback.jsonl`。
- 自动评价第一版只做硬过滤和排序辅助，不做最终审美结论。
- 人工只复看自动筛选后的 Top K 和少量失败样本，反馈必须结构化。
- 下一轮变异必须引用上一轮 `parent_candidate_id` 和人工反馈，不允许重新随机开一批不可追溯候选。

### 自动硬过滤优先项

- Unity `verify` 或 Console 有 error：淘汰。
- 材质、贴图、Mesh 或 Prefab 引用缺失：淘汰。
- 主体不可见、主体面积过小或明显超出画面：淘汰。
- 峰值帧过曝、过暗或只有一团白光：淘汰。
- 多时间点帧间变化过低，无法形成前摇、爆发、收束：淘汰。
- 生命周期、粒子数量或渲染预算明显越界：淘汰或降权。

### 人工反馈优先项

人工反馈不要只写“好/不好”。每个候选至少记录：

- 是否可继续变异。
- 主要失败维度：形体、方向、层级、节奏、材质、构图、技术错误。
- 保留部件和拒绝部件。
- 下一轮变异建议。

成对偏好优先于孤立绝对分：同一 prompt 下，记录 A 是否优于 B 以及原因。

训练体系分为两层：

- 通用 VFX 能力底座：读图、形体、层级、节奏、材质（shader + texture tags + slot roles）、空间锚点、镜头可读性和性能约束。
- 特效族适配器：刀光、火焰、雷电、护盾、烟雾、爆炸、法阵、水系等类型各自的拓扑、生成器和专用评分。

第一门课程是刀光主体弧搜索，代号 `SlashArc-Pref-001`。它只用于启动闭环，不代表完整训练体系。主体弧没有通过候选筛选前，不继续修支撑层、命中层、场景锚点或完整成品。

## 目录

- `schemas/`：VFXSpec、人工反馈和训练样本的数据契约。
- `sources/`：Unity 特效源文件包登记、依赖/授权/参数抽取和 VFXSpec 反推样本。
- `curriculum/`：跨特效能力地图、特效族适配器和训练课程规划。
- `curricula/`：生成后的可执行 Curriculum 规格批次，例如 MaterialTrajectorySpec；与课程规划目录分开。
- `prompts/`：生成式特效 prompt、negative prompt 和首轮搜索约束。
- `runs/`：每轮候选生成、渲染 manifest、contact sheet 和反馈记录。
- `datasets/`：从 runs 汇总出的训练样本、偏好对和特征表。
- `reports/`：阶段报告、候选筛选结论和模型评估摘要。

## 数据规则

可以长期保留和提交的内容：

- schema、README、prompt、small manifest。
- 候选 `spec.json`、`run_manifest.json`、`feedback.jsonl`。
- 源文件摄入的 `material_selection` 摘要、`source_manifest.json`、`source_sample.json` 和小型参数摘要。
- 小型报告和训练样本索引。

默认只本地保留的内容：

- 大量 PNG/JPG 截图、视频、EXR、模型导出、临时 Unity 资产包。
- 授权不明或体积较大的 Unity 原始特效源文件、贴图、FBX 和导出包。
- 训练中间模型、向量缓存、特征矩阵和大体积数据文件。

每个 run 至少应包含：

```text
runs/<run_id>/
  run_manifest.json
  candidates/<candidate_id>/spec.json
  feedback.jsonl
```

如果已经生成截图，还应包含联系表路径、截图时间点、Unity 项目路径、相机和 Console/verify 状态。Unity 错误必须同步记录到 `workspace/progress/ERROR_LOG.md`。

Prefab 捕获 v2 额外要求：Bounds 探测、三视角评估和正式截图使用独立实例；正式时间轴使用固定 simulation delta；MainCamera、EventSystem、地面和目标锚点由标准上下文提供。`source_scripts_excluded`、Missing Script、无可见机位、边缘裁切、未知 MPB 或 Shader global 必须写入 manifest 并降低训练资格。非空 PNG 只能证明文件写入成功。

源文件摄入样本至少应包含：

```text
sources/<source_id>/
  source_manifest.json
  source_sample.json
  derived_vfxspec.json
  training_example.json
```

源文件存在不等于视觉成功，也不等于可训练。必须额外关联渲染结果、人工反馈和授权状态。

## 当前边界

- 活动 Unity 项目：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`。
- 当前试点：爆炸六轴闭环已完成；刀光已具备 Core、Support、Hit、Residual 四层真实 PrefabGraph，并完成外/内层级、方向拖带和接触点聚焦三个专业窄轴闭环。
- 当前不做：把静态图片 A/B 评价当作阻塞条件，也不把当前基础候选称为高质量最终特效。
- 当前训练目标：PrefabGraph 结构先验和 Prompt 条件结构生成继续经过 Grammar、AssetPlan、Unity 编译、运行和 API 回读；非专业人工只低频修正元素、类型和播放状态。审美监督改由专业资料、Unity 受控复刻和成对候选迁移产生。

## 训练路线

不要把 `SlashArc-Pref-001` 误解为整个训练计划。完整路线是：

```text
通用能力底座
  -> 特效族适配器
  -> 类型内候选搜索
  -> 人工偏好数据
  -> 类型专用判断器
  -> 跨类型共享判断器
  -> 类型专用提案器
  -> 多任务迁移
```

当前生成主线已落地到：

```text
Prefab / 结构语料
  -> PrefabGraph
  -> GRU 结构先验
  -> Grammar 约束候选
  -> AssetPlan
  -> Unity 2022 API 新建 Prefab
  -> 运行与 API 回读
```

真实源结构批次 `prefab_graph_source_export_r003`：10/10 源 Graph 导出、10/10 新 Prefab 重建、10/10 API 回读通过；没有人工审美标签，不能把它当作“已经学会好看”。

全量结构训练视图 `prefab_graph_training_view_r002` 包含 2115 个 Graph、337 个结构簇，train/validation/test=`1169/444/502`，结构簇泄漏为 0。`prefab_graph_next_token_full_r001` 测试准确率为 `0.83805`，`prefab_graph_multitask_full_r001` 的 masked component 准确率为 `0.97416`。两者都不消费审美标签，只是合法结构先验。

资产路由批次 `prefab_asset_routes_r001` 已覆盖 `billboard`、`mesh_particle` 和 `impact_decal` 三类显式路由。它读取 Unity API 材质审计、纹理标签和 FBX 几何审计，不按文件名猜 Shader/贴图绑定；计划保留 asset_id、路径、SHA-256、授权状态、Shader 属性、纹理槽位和 Mesh 轴向/Pivot/UV 证据。缺少资源或 Unity 几何检查时状态为 `blocked`/`needs_unity_validation`，禁止静默回退。

Prompt 条件批次使用 `prefab_graph_prompt_condition_r003` 和 `prompt_graph_profile_r004`。数据共 64 条、8 个特效族，标签全部是 `ai_hypothesis` 类型/课程先验；模型 test accuracy=`0.9231`，没有人工或审美标签。最终雷电 `particle_v1` 和爆炸 `multi_particle` 均完成 Graph Schema、Grammar、AssetPlan、Unity 2022 编译和 Play Mode 可见性验证，状态为 `pass_technical_prompt_unscored`。帧只证明运行可见，当前画面仍是基础蓝色拖形和红橙软团，不是高质量雷电或爆炸成品。

双族批次 `prompt_graph_dual_family_r001` 使用爆炸和刀光中文 Prompt，各生成 8 条无 parent 候选。爆炸/刀光均为 8/8 Graph 合法、8/8 AssetPlan 通过、8/8 Unity 编译、8/8 Play Mode 可见；来源 Prefab 读取 0，分别生成 24/8 个独立材质和贴图。汇总位于 `dual_family_report.json`。AI 排序只依据技术可见性并标记为 `ai_hypothesis`；实际 Top 帧仍是软团/条块，不是审美成功。

双族 16 条候选还各自保存通过 `vfxspec.v1` Schema 的 `vfxspec.json`，记录 Prompt、negative prompt、family adapter、seed、模型/编译器版本、Graph ID、层角色、材质和时序参数；爆炸与刀光均为 8/8 VFXSpec 有效。

刀光主体弧只覆盖 `slash.core_blade`。火焰、雷电、护盾、烟雾、爆炸、法阵和水系都需要各自的 generator family 与评价维度。

专业审美训练首条闭环为 `professional_explosion_core_readability_r001`。专家原话、时间码和证据帧经 Unity 受控复刻后得到 1 条 Teacher-ready 规则；该规则迁移到 8 个爆炸候选后，8/8 通过编译、贴图回读、Prefab API 回读、Play Mode 和核心增益门禁。`professional_core_rule_ranker_r001` 用 8 对/16 条动态图像样本做 PyTorch 成对梯度下降，严格按 pair 分组为 4/2/2，三个分区的 pair accuracy 均为 1.0。测试只有 2 对，因此它只是 `explosion/core_readability` 试验排序头，不是通用审美模型。

第二条闭环 `professional_explosion_residual_persistence_r001` 使用专家“爆炸后应有残留”的明确判断，经受控 Residual Alpha 复刻和 8 对四层候选迁移后进入 Teacher catalog。`professional_residual_rule_ranker_r001` 同样使用 8 对/16 条、4/2/2 分组和成对梯度下降；它只学习残留持续性，不评价残留材质或整体好坏。

第三条闭环 `professional_explosion_shockwave_expansion_r001` 使用专家“冲击层应从中心向外扩张”的明确判断。单环复刻、四层静止/外扩消融和成对差异径向门禁均已通过；`professional_shockwave_rule_ranker_r001` 使用 8 对/16 条、4/2/2 分组和 AdamW 成对损失。独立 Prompt/seed 的 R007 为 8/8 技术通过、8/8 分布内。该模型只学习外扩运动，不评价冲击波贴图、材质或完整爆炸质量。

第四条 Teacher `professional_explosion_debris_branches_r001` 来自 EP008 对火鸟/凤凰爆裂的专业点评。受控复刻只切换 Debris Alpha，保持 Core、材质、贴图、数量、速度、相机和种子一致；结果检测到 30 个离散组件、0.541 的峰值径向范围和 20 个有效差异帧，状态为 `verified`。R007、R008 两批四层迁移均为 8/8 通过，合并数据达到 16 对/32 条；`professional_debris_rule_ranker_r002` 在全新 R009 上为 8/8 技术通过、8/8 分布内。它只学习“小型碎片分支存在且离开核心”，不代表碎片材质、最佳密度或整体构图达到最终质量。

第五条 Teacher `professional_explosion_core_texture_structure_r001` 来自 EP007 对火焰核心、边缘和暗部的专业点评。受控复刻保持同一 Shader、颜色、粒子和相机，只把均匀光盘换成单帧结构化软边纹理；bbox fill 降低 0.3461、edge density 增加 0.0521，中心亮度保留 80.57%，状态为 `verified`。四层批量迁移 8/8 通过并训练 `professional_explosion_material_rule_ranker_r001`。独立 R011 使用显式 `structured_flame` 档位，Unity 技术、材质、Shockwave、Debris、Residual 均为 8/8 分布内。旧 Core readability 模型仍为 0/8 OOD，因此结构化纹理保持显式 opt-in，不替换默认档位。

R011 随后生成结构化 Core-off/on 8 对，全部通过中心亮度和局部对比门禁，并训练 `professional_core_rule_ranker_r003_structured`。全新 R012 使用结构化档位，Unity 技术与 Core readability、Core material、Shockwave、Debris、Residual 五轴均为 8/8 分布内。两种 Core 纹理继续作为显式档位，后续由 Prompt/风格条件选择，而不是全局替换。

第六条 Teacher `professional_explosion_staged_rhythm_r001` 来自 EP004 的“亮点→扩散线/碎片→残光”以及 EP006 的“短爆发快速收束”。受控实验只把 Support、Hit、Residual 的启动延迟压到 0 与原始分层时序比较；分层版本早期外围重叠减少 0.00481，晚段可见时间延长 0.20 秒，状态为 `verified`。该规则已经写入生成器 Teacher 列表，尚待 8 对迁移和节奏窄轴模型。

节奏规则已迁移到 R012 的 8 个候选并全部通过。`professional_explosion_rhythm_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`，同时读取 Graph 层间延迟、早期外围重叠与晚段残留。全新 R013 为 8/8 技术通过、8/8 节奏分布内。爆炸族当前已具备 Core、材质、Shockwave、Debris、Residual 和完整节奏的独立门禁，下一族转向刀光。

刀光族 `layered_slash_family_r003` 已从规格生成升级为真实 PrefabGraph：双层 ParticleSystem 使用 `Slash4.fbx` Mesh、显式 `Trail68.png` 和 QFX 粒子材质，8/8 编译、Mesh/API 回读和 Play Mode 可见性通过。`professional_slash_outer_inner_hierarchy_r001` 只修改内层尺寸和 Alpha，正确版本保留主刃宽度并将全长高亮跨度减少 0.575，状态为 `verified`。Hovl `SwordSlash.mat` 的原 Shader 依赖尚未建模的 vertex streams，R002 near-blank 作为失败证据保留。

层级规则已迁移到 R003 的 8 个候选并全部通过。`professional_slash_layer_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`，输入外/内尺寸与 Alpha 比例以及运行画面的宽度和高亮跨度。全新 R004 为 8/8 编译、Mesh/API 回读、Play Mode 和分布门禁通过。该模型不评价攻击方向、命中、残留或整体刀光质量。

`layered_slash_family_r005` 新增第三层 `DirectionTrail/residual`：局部坐标旋转后沿攻击轴运动，使用显式 Trail68 贴图和 QFX 材质。R005 为 8/8 编译、Mesh/API 回读和 Play Mode 可见，但合成帧中拖带与主刃重叠，当前仍是 `ai_hypothesis`，必须通过独立的沿攻击方向/朝镜头方向 A/B 后才能进入训练。

`professional_slash_directional_trail_r001` 已关闭主刃和内层，对 DirectionTrail 做沿相机深度轴/沿画面攻击轴的单变量旋转 A/B。正确版本水平质心跨度为 0.282，水平/纵向运动比为 15.67，相对错误版水平跨度增加 0.272，状态为 `verified`。

方向规则已迁移到 8 对/16 条同拓扑样本并训练 `professional_slash_direction_rule_ranker_r001`。全新 R006 为 8/8 技术通过，6/8 分布内，2/8 保留 OOD；Top-1 为 `layered_slash_002_pfg_7ad0f699330c29fabbd0`。该模型只判断方向拖带，不评价完整刀光。

`professional_slash_contact_focus_r001` 使用专业点评中的接触点/受力端局部聚焦规则。R003 Teacher 仅移动 Hit 位置，接触区平均亮度增益 0.0949、顶部亮像素增益 0.1243、差异质心到目标距离 0.0179，状态为 `verified`。规则迁移到 8 对/16 条后全部通过；`professional_slash_hit_rule_ranker_r001` 使用 pair 级 4/2/2 无泄漏训练，独立 R011 为 8/8 技术通过、8/8 分布内。

`professional_slash_readable_then_fade_r001` 使用专业刀光课程的“关键瞬间先可读，随后慢慢消失”规则。Teacher 只修改 DirectionTrail 的启动延迟和寿命，正确版晚段活跃比例增加 0.333、最后可见时间增加 0.445 秒，状态为 `verified`。R012 的 8 对迁移全部通过；`professional_slash_residual_rule_ranker_r001` 使用 8 对/16 条、pair 级 4/2/2，独立 R013 为 8/8 技术通过、8/8 分布内。刀光生成器现为四层 v8，下一步验证完整四层节奏组合。

`professional_slash_staged_rhythm_r001` 将四层同时起播与 `Core 0 / Support 0.01 / Hit 0.065 / Residual 0.18s` 比较；正确版早期叠加下降、命中窗口峰值保留、最后可见时间增加 0.1355 秒，状态为 `verified`。8 对迁移后训练 `professional_slash_rhythm_rule_ranker_r001`。旧 Layer/Direction 模型面对新增 Hit 与延迟 Residual 时为 0/8 OOD，因此在四层 R012 上重建 v2 数据和模型，没有放宽阈值。全新 R014 的 Layer、Direction、Hit、Residual、Rhythm 五轴均为 8/8 分布内；`professional_slash_multi_axis_rank.py` 按分位排名融合，Top-1 为 `layered_slash_001_pfg_f6e7e4847e6fedabcad0`，已复制到权威 EffectDemo。

雷电族 `layered_lightning_family_r001` 已建立 `MainBolt/Core`、`BranchSupport/Support`、`ImpactFlash/Hit`、`ResidualSpark/Residual` 四层技术底座，使用现有 QFX 材质和 Epic Toon/QFX 实际贴图。8/8 候选通过 Unity 编译、贴图回读、Prefab API 回读和 Play Mode 连续帧，状态仍为 `technical_adapter` / `ai_hypothesis`。下一步用专业“主电流粗、外围分支细且克制”规则建立首条雷电 Teacher。

`professional_lightning_main_branch_hierarchy_r001` 已完成受控复刻。R001 批量迁移因部分随机分支过粗只有 4/8 通过；没有放宽门槛，`lightning_family_adapter.v2` 收紧 BranchSupport 尺寸和 Alpha 后，R002 参数门禁全部通过。早期按两版各自峰值比较仍有 2 条假负值，改成同时间帧成对比较后 R002 为 8/8 技术与规则通过。`professional_lightning_hierarchy_rule_ranker_r001` 使用 8 对/16 条、pair 级 4/2/2；独立 R003 为 8/8 技术通过、8/8 分布内，Top-1 已复制到权威 EffectDemo。雷电生成器现为 `implemented`。

`professional_lightning_impact_focus_r001` 只修改 ImpactFlash Alpha，Teacher 和 8 对迁移全部通过。`professional_lightning_hit_rule_ranker_r001` 使用 8 对/16 条、pair 级 4/2/2；独立 R004 为 8/8 技术通过，Hierarchy 8/8、ImpactFocus 7/8 分布内，1 条保留 OOD。`professional_lightning_instant_pulse_r001` 只修改 MainBolt lifetime，早期峰值保留 1.0、最后可见时间提前 0.22 秒，Teacher 已 verified。

Pulse 首轮在完整四层画面中被其他层遮蔽，出现技术 8/8、规则 0/8；R002 改成 slow/instant 两侧都派生 Core-only Graph，并分别编译、回读和捕获，8 对全部通过。`professional_lightning_pulse_rule_ranker_r001` 使用 8 对/16 条、pair 级 4/2/2；独立 R005 同样使用隔离推理协议，最终 8/8 分布内。下一步训练 ResidualSpark 余电收尾，再做雷电多轴融合。

`professional_lightning_residual_persistence_r001` 只开关 ResidualSpark Alpha。首轮约 0.24 秒 lifetime 的晚段活跃比例增益为 0.133，未达到 0.15；保持专业门槛并将两版共同 lifetime 调整到 0.30 秒后，晚段活跃增益为 0.267、最后可见时间增加 0.28 秒，Teacher verified。当前仍待 8 对迁移和模型训练。
