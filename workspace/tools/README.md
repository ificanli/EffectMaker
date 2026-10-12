# Workspace Tools

Flat script layout, grouped by purpose.

## Media and extraction

- `media.py`, `media_cli.py`, `media_integrations_cli.py`
- `transcribe_*`, `frame_*`, `scene_detect.py`, `merge_episode_transcript.py`

## Indexing and search

- `resource_index/` - includes `texture_tagger.py` for fine-grained texture labels such as semantic, alpha, luminance, shape, and material-slot usage tags.
- `model_index/`
- `resource_vectors/`
- `vfx_library_index/`
- `kg.py`, `rag.py`

## Review and services

- `annotation_server.py`
- `board_server.py`
- `image_attachment_server.py`
- `teaching_comparison.py`

## Unity and policy

- `unity_capture.py`
- `build_vfx_web_player.ps1` - 固定使用 `UnityDemo/EffectDemo`、Unity `2022.3.16f1c1` 构建真实运行 Trains Prefab 的 WebGL 动态训练播放器；主工程被 Editor 占用时传入隔离副本路径。
- `vfx_web_training_review.py` - 将 VFX run manifest、材质时间线摘要和显式 WebGL Prefab 映射打包为动态训练 review bundle。
- `vfx_web_player_server.py` - 在 `127.0.0.1` 提供 Unity WebGL 构建和正确的 WebAssembly MIME 类型。
- `vfx_generation/run_pipeline.py` - AI式VFX run 汇总、contact sheet 生成和 auto-eval 输出；读取候选 `spec.json` 与 Unity `capture_manifest.json`，写回 `run_manifest.json`。
- `vfx_generation/evaluator.py` - 通用渲染可测分数和特效族专用规格先验；明确区分机器可测证据与人工视觉验收。
- `vfx_generation/feedback.py` - 非交互反馈创建、追加和 JSONL 校验工具。
- `vfx_training_features.py` - 从候选 spec、Unity 多帧截图和 auto-eval 生成带 provenance 的训练特征矩阵。
- `vfx_preference_ranker.py` - 训练和应用 scikit-learn pairwise 候选排序模型；标签不足时拒绝写入权重。
- `vfx_generation/vfx_prefab_corpus.py` - 将多个摄入批次聚合为可增量更新的千级 Prefab 语料索引，并按内容哈希切分防止同资产泄漏。
- `vfx_generation/vfx_controller_dataset.py` - 将 Unity 运行结果和人工 Prompt 条件导出为带 provenance 的 Controller 数据与 MiniMind-compatible SFT JSONL。
- `vfx_generation/course_knowledge_adapter.py` - 将课程来源、知识卡片和 Unity 实验转成带证据等级的 VFXSpec 先验，并可通过 Controller 数据集的 `--course-adapter-manifest` 入口接入审计；未复现、未评价内容只进入排除清单。
- `vfx_generation/aesthetic_record_exporter.py` - 将课程/审美资料、专家反馈和技术排除标准化为统一 `aesthetic_record` 数据集；历史非专业审美反馈不再作为正式 Judge 真值。
- `vfx_generation/aesthetic_training_dataset.py` - 将统一审美记录和连续帧特征组装为 Judge/偏好训练文件，按 Prompt/Prefab 分组切分并拒绝缺特征、不可见和技术排除样本。
- `vfx_generation/aesthetic_judge.py` - 多任务 Judge 轻量基线；历史非专业评分模型仅保留为实验，正式重训必须读取专业 Teacher 数据并通过独立门禁。
- `vfx_generation/prefab_active_learning.py` - 将五层 Prefab 记录按 Prefab 路径去重并确定性聚类，整簇分配 split，按不确定性、新簇、模型分歧、Top/Low 和随机审计生成有限人工队列。
- `vfx_generation/prefab_active_review.py` - 使用 Capture v2 连续帧和可选 WebGL 的中文复核页；`semantic_function_only` 模式将特效元素与特效类型分开：元素多选，类型单选，两边均可新增并复用中文标签。稳定 ID、中文名称和维度写入 `custom_semantic_options.json`；旧单维反馈不会跨 Schema 迁移。构建时会拒绝错误洋红 Capture，不要求非专业用户评价审美。
- `vfx_generation/nonexpert_semantic_feedback.py` - 将历史非专业主动反馈重分类为语义监督；旧单维记录只保留历史证据，当前正式监督必须同时包含独立元素与类型字段。命中类统一为 `impact`，`hit` 只作兼容别名；r010/r011 的 32 条双维人工结果已结算。
- `vfx_generation/professional_aesthetic_teacher_readiness.py` - 审计课程资料是否具备专业来源、明确审美结论、动态证据、评价轴和 Unity 复刻；缺任一项时只进入补证队列，不生成审美训练标签。
- `vfx_generation/prefab_review_judge_features.py` - 从主动学习 Capture v2 构建兼容 Judge 的未标注特征输入；只为未来专业 Judge 推理准备，不自行产生审美真值。
- `vfx_generation/prefab_regression_gold.py` - 从 Capture v2 human gold 冻结回归集，隔离整个近邻簇，并导出无回归污染的训练、伪标签传播和 Judge 训练/评估视图。
- `vfx_generation/full_prefab_technical_baseline.py` - 将 Unity 全 Assets Prefab 审计组装成 100% technical corpus 和 PrefabGraph 数据集；审计失败仍保留技术记录，不伪造 Graph。
- `vfx_generation/asset_capability_registry.py` - 合并全局贴图库、项目 Texture、Unity Shader/Material 审计、NB 包和 GitHub reference，严格区分 bindable/reference/blocked。
- `vfx_generation/material_plan.py` - 按 Prompt 特效族、风格、层职责、颜色、性能、槽位和来源配对联合选择 Material×Shader×Texture，并输出多样化候选。
- `vfx_generation/material_plan_validation.py` - 将 MaterialPlan 的 Unity 编译、保存后贴图回读和 Capture v2 可见性整理成技术正负监督，不产生审美标签。
- `vfx_generation/full_prefab_capture_batch.py` - 从全量技术基线按资源组、元素族和复杂度确定性生成可增量 Capture v2 批次。
- `vfx_generation/full_prefab_capture_report.py` - 汇总 Capture v2 输出，将可见样本路由到 visual feature，并把空帧/上下文限制保留为 technical-only。
- `vfx_generation/prefab_graph_training_view.py` - 按参数无关结构和组件拓扑聚类后切分全量 PrefabGraph，防止近重复结构跨 train/validation/test 泄漏，并校验 Graph ID 对齐。
- `vfx_generation/prefab_graph_model.py` - 训练带长度窗口和分桶 batch 的 PrefabGraph next-token 结构模型；长序列先按结构簇切分再窗口化。
- `vfx_generation/prefab_graph_multitask_model.py` - 训练共享编码器的 next-token、组件恢复和结构重构多任务结构模型。
- `vfx_generation/prefab_graph_model_compare.py` - 在同一无泄漏训练视图上对比新旧结构 checkpoint，避免跨数据集直接比较误导指标。
- `vfx_generation/prefab_graph_generation_report.py` - 汇总生成 Graph 的解码、AssetPlan、贴图回读、Prefab 回读和 Play Mode 门禁，输出 `training_ready` 与技术排除集。
- `vfx_generation/stage_material_plan_assets.py` - 将 MaterialPlan 实际选中的 Material/Texture/Shader 及 GUID/include 依赖闭包同步到隔离 Unity 工程，并校验 SHA-256 与 `.meta`。
- `vfx_generation/material_asset_pair_dataset.py` - 从真实 PrefabGraph 材质绑定和 asset registry 生成 Material×Shader×Texture 技术配对训练视图，按材质簇隔离 split。
- `vfx_generation/material_asset_pair_model.py` - 训练技术资产组合 PyTorch MLP，并作为 MaterialPlan 的可选神经重排器；不产生审美标签。
- `vfx_generation/visual_dynamics_training_view.py` - 合并 MaterialTrajectory、Prompt 双维条件、连续帧图像特征和 MaterialTimeline，专业 Teacher 不足时只开放技术自监督。
- `vfx_generation/visual_dynamics_model.py` - 预训练材质动态状态/变化量表征模型；没有审美质量头，不能把可见性当作质量。
- `vfx_generation/capture_visual_integrity.py` - 检测 Unity 错误洋红；同时要求纯洋红达到最小画面面积并主导可见前景，避免把正常粉色/紫色高亮误判。命中项只进入 technical exclusion，不进入审美负例。
- `vfx_generation/aesthetic_preference_ranker.py` - 将规范化 A/B 偏好转换给现有 pairwise ranker，按训练 split、候选数量、比较数量和独立 run 执行门禁。
- `vfx_generation/vfx_controller_aesthetic_guidance.py` - 将 Judge 预测、偏好排序和人工问题转换为可追溯的 Controller 变异指导；指导永远需要人工批准，不直接生成或修改 Unity 资产。
- `vfx_generation/aesthetic_model_promotion.py` - 审计审美模型的族/风格覆盖、split 泄漏、模型卡、回归集和晋级状态；数据或模型不足时只报告阻塞。
- `vfx_generation/aesthetic_preference_review_batch.py` - 从技术通过的同 Prompt/同族变异 run 创建专业 Teacher A/B 候选；排除技术失败，不从质量分数推导偏好。
- `vfx_generation/aesthetic_preference_review_server.py` - 历史中文 A/B 页面；非专业用户不再承担审美 A/B，正式胜负标签必须来自专家对照或教程明确前后关系。
- `vfx_generation/vfx_controller_train.py` - Controller 训练预检；正例或特效族覆盖不足时只写审计报告，不生成权重。
- `vfx_generation/prompt_condition_scorer.py` - 从人工 Prompt 条件标签和多帧渲染提取特征，训练带分组门禁的 VFX Judge 条件评分器；无法判断不会成为类别。
- `vfx_source_ingest.py` - Unity VFX source-file ingestion. Use `--copy-dependency-closure` when copying external Prefab batches so referenced Materials, Textures, Meshes, Shaders, Shader Graphs, VFX Graphs, and animation assets are copied with their `.meta` files. Script dependencies stay external unless `--include-script-dependencies` is explicitly used.
- `bd_guard.py`

## Shared utilities

- `output-accumulator.js` (local helper)

## Rule of thumb

Keep new helpers in the closest purpose group. If a script starts to grow or get shared, move it under a dedicated subfolder instead of adding more flat siblings.
