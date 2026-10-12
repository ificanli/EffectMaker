# 生成式 VFX 训练标准

本文是 `vfx-2df` 生成式 Unity VFX 系统的训练权威入口。训练目标不是从像素直接生成不可编辑视频，而是学习：哪个候选更值得保留、哪些特征影响偏好，以及下一轮 `VFXSpec` 应该向什么方向变异。

审美资料的独立训练方案见[《VFX审美资料训练方案》](../00-总纲/VFX审美资料训练方案.md)。该方案负责把点评、参考视频、连续帧和人工反馈转换成 Judge 与 Preference Ranker 的监督；本文继续负责生成式 VFX 的总体数据门禁和 VFXSpec 回写边界。

## 1. 标准流水线

```text
Prefab / 优秀视频 / 制作教程 / 评价课程
  -> SourceAssetSpec / ReferenceSpec / ProcedureSpec / CritiqueRubric
  -> VFXSpec / PrefabGraph 候选
  -> Grammar 约束结构解码
  -> 技术 AssetPlan（材质 / Shader / 贴图 / Mesh）
  -> Unity Editor API 创建全新 Prefab
  -> Unity 固定场景、相机和时间点渲染
  -> capture_manifest + Console/verify/性能记录
  -> 技术硬过滤
  -> 人工 A/B 偏好、质量和风格反馈
  -> 候选特征矩阵
  -> Pairwise 排序模型
  -> 本地模型权重 + 指标 + Model Card
  -> 模型排序下一轮候选
  -> 人工批准后生成 MutationSpec / 下一轮 VFXSpec
```

任何生成候选都必须经过 Unity 实渲和技术门禁。静态联系表无法支持可靠人工判断时，不强制生成 A/B 标签；当前 AI 评价只能标为 `ai_hypothesis`，不得写成人工质量结论。结构生成主线可以先使用技术结构监督、Grammar 约束和 Unity 自动验证推进。

### 1.1 Prefab 动态捕获 v2

正式 Prefab 图像证据必须使用 `play_mode_runtime_isolated_multiview.v2`，不能继续把编辑器 `ParticleSystem.Simulate`、非空 PNG 或单实例预跑结果当训练真值：

```text
Prefab 资产
  -> 新建 Bounds 探测实例并销毁
  -> 新建三视角评估实例并销毁
  -> 新建正式截图实例
  -> 固定 Unity simulation delta
  -> LateUpdate 材质状态快照 + Camera.Render
  -> 逐帧像素、时间、镜头、上下文和训练资格
```

- Bounds 探测、镜头评估和正式截图必须是三个不同实例 ID；任意 MonoBehaviour、协程、动态材质、MPB 和随机粒子状态不得从预跑进入正式截图。
- 镜头至少评估 front、side、top，使用实际可见像素、边缘裁切和中心偏移选择；只按 Renderer Bounds 猜角度不合格。
- 捕获相机必须提供 `MainCamera`，标准上下文包含 EventSystem、无渲染地面 Collider、目标和角色锚点；缺 Canvas、Missing Script 或排除源脚本必须写 `incomplete_context`。
- 自适应窗口上限为 8 秒；间隔最大 0.1 秒，短特效可细到 0.02 秒。正式截图使用 `Time.captureDeltaTime` 固定模拟步长，分别记录请求时间、simulation elapsed、wall-clock elapsed 和 Unity frame/time。
- 每帧必须保存 visible-area、border-touch、center-offset；全黑、裁切、上下文不完整或实例未隔离的候选不得进入图像训练。
- Material timeline 读取 Shader 属性、keyword 和 MPB；无法枚举的 MPB 与未插桩 Shader global 必须使 `full_visual_training_eligible=false`，但可以保留为带限制的技术图像序列。

R003 五类回归覆盖 instant、moving、ground、UI 和 script-material：5/5 实例隔离、5/5 三机位、所有帧有效、移动/地面可见，脚本材质记录 33 个 delta；0.15 秒瞬发样本最大模拟时间漂移约 `0.01875s`。报告位于 `workspace/data/vfx_generation/generated/runtime_capture_v2_regression_r003/regression_report.json`。

## 2. 数据角色

| 输入 | 结构化产物 | 训练用途 | 不能单独作为 |
|---|---|---|---|
| Prefab / Unity 源工程 | `SourceAssetSpec` | 真实层级、Material、Shader、Texture、Mesh、粒子和依赖先验 | 正向审美标签 |
| 优秀特效视频 | `ReferenceSpec` | 目标轮廓、层级、节奏、风格、峰值和收束 | 原工程参数真值 |
| 制作教程 | `ProcedureSpec` | 制作因果、adapter 字段、参数关系和实现规则 | 完整 Inspector 真值 |
| 评价课程 | `CritiqueRubric` | 反馈字段、失败标签、排序与奖励模型目标 | 具体资产和参数 |

四者与真实 Unity 渲染和人工反馈对齐后，才形成 `ApprovedExample`。

## 3. 监督信号

### 3.0 Prefab 结构与粒子参数监督

已有 Unity Prefab 是完整特效生成的重要源语料。即使没有人工审美标签，也可以从 Unity API 提取并训练：

```text
PrefabGraph
Particle System 主模块、发射、形状和启用模块
Renderer / Mesh / Material 绑定
Animator / Animation / Timeline 时长
依赖健康度与运行上下文需求
```

这些属于技术结构监督，不等于审美正例。当前 `Trains_FX_All_001` 已形成 259 条 PrefabGraph、220 条粒子参数样本；依赖闭合的 59 条已进入 Play Mode 渲染，得到 36 条图像 feature-only 和 23 条不可见上下文样本。人工审美标签仍为 0。

`prefab_graph_r001` 已将 259 条样本规范化为确定性节点、组件引用和结构 Token，Schema 错误和重复 `graph_id` 均为 0，且没有消费任何审美标签。旧 Unity 审计没有记录本地 Transform 和完整 ParticleSystem 模块序列化值，因此当前 `259/259` 都是 `structure_only`，可用于层级建模、组件预测和已抽取的粒子参数建模，不可用于完整 Prefab 重建。

当前优先级为：`PrefabGraph IR -> Unity 编译器 -> 结构预训练 -> Prompt 条件生成`。只有静态图片的 A/B 人工审美不再是这条技术结构主线的前置门禁；AI 可以输出带来源的 `ai_hypothesis`，但不得写成人工偏好或进入人工审美训练集。

当前已验证的生成出口：`prefab_graph_roundtrip_r002` 完成 10 条独立无 parent Graph -> Unity Prefab -> Unity API Graph 回读，10/10 通过、Schema 错误 0、差异 0。`prefab_graph_next_token_r002` 是首个结构神经网络先验，测试 Token Accuracy 为 `0.8594`；`prefab_graph_constrained_r001` 已用该权重生成合法的 root-only、particle_v1 和 multi_particle 结构候选；`prefab_graph_asset_upgrade_r001` 已为三类候选建立 AssetPlan 并在 Unity 2022 中编译与抓帧。

`prefab_graph_source_export_r003` 已从 Unity 2022 的 10 个真实源 Prefab 通过 `AssetDatabase`、`Transform`、`ParticleSystem`、`ParticleSystemRenderer` 和 `Renderer` API 导出完整的当前 `particle_v1` 技术字段；10/10 源 Graph 被重新编译为新的 Prefab，再由 Unity API 回读，10/10 通过、Schema 错误 0、字段差异 0、未实例化来源 Prefab。该批次只使用技术结构监督，未消费审美标签；材质、Shader、贴图和 Mesh 路径保留为资产 provenance，Unity 内置材质路径单独处理，不猜测替换。

`prefab_graph_r002` 已将 R003 源 Graph 合并进原有 259 条结构语料，得到 269 条样本；按 Prefab 组划分为 train/validation/test=`185/42/42`，没有重复 Graph ID 或跨组泄漏。`prefab_graph_multitask_r001` 是首个共享编码器三任务实验：next-token 测试 Token Accuracy `0.8193`，组件掩码恢复 Accuracy `0.8190`（840 个测试目标），结构重建 Token Accuracy `0.2100`，整序列精确重建率 `0`。这证明多任务训练管线和 checkpoint 可复现，不证明已经具备完整 Prefab 生成能力；后续仍需结构自回归解码、Prompt 条件、AssetPlan 和 Unity 视觉验证。

`prefab_asset_routes_r001` 已完成技术资产路由最小闭环：`billboard`、`mesh_particle`、`impact_decal` 三类路由均有显式计划。材质来自 Unity API binding audit，必须通过允许的 Shader 集合并暴露 `_MainTex`；纹理通过 `slot.*`/`role.*` 内容标签选择；Mesh 通过 Unity `AssetDatabase` 检查顶点数、子网格、UV 数量、轴向空间和来源 Pivot。实际批次为 730/730 材质记录通过、39/39 FBX 几何记录通过，计划状态为 `pass`。该结果只代表资源兼容和可追溯，不代表运行画面审美成功。

`prompt_graph_profile_r004` 使用 64 条显式 `ai_hypothesis` 条件先验训练 Prompt profile 路由，覆盖 8 个特效族、风格、节奏、性能档位和颜色；分层留出 test accuracy=`0.9231`，人工标签和审美标签均为 0。`prompt_graph_generation_r001` 的最终雷电 `particle_v1` 与爆炸 `multi_particle` 分别通过 Schema、Grammar、AssetPlan、Unity 编译和 Play Mode 可见性：雷电 14/14 帧、最大可见面积 `0.0227`；爆炸 21/21 帧、最大可见面积 `0.0361`。状态只能写成 `pass_technical_prompt_unscored`；实际帧仍是基础形体，不得称为高质量 Prompt 生成特效。

`prompt_graph_dual_family_r001` 已按爆炸和刀光两族各生成 8 条无 parent 候选。两族 Graph/seed 均为 8 个唯一值；Schema、Grammar、AssetPlan、Unity 编译和 Play Mode 可见性均为 8/8，来源 Prefab 读取数 0。爆炸最大配置粒子预算 192，刀光 64；这些是配置预算，不是目标设备 GPU Profiler 结论。成功集只排除技术失败/空白项，AI 排序明确标记 `ai_hypothesis`，不能当作人工偏好或审美正例。

每条双族候选同时生成一个合法 `vfxspec.v1`，爆炸/刀光均为 8/8 Schema 通过。Spec 保留 family adapter、Prompt/negative prompt、seed、模型 checkpoint、Graph ID、层角色、材质和时序参数；VFXSpec 与 PrefabGraph 共同构成 Prompt 生成的可追溯中间表示。

### 3.1 技术硬负例

Unity 编译或 Console 错误、资源引用缺失、截图不可见、主体明显出框、时间序列静止和性能越界，可以由工具直接标为技术负例。技术硬负例用于可运行性过滤器，不能替代人的审美偏好。

### 3.2 人工偏好对

首版排序模型的主要监督信号是：

```text
同一目标和风格条件下：candidate_a 是否优于 candidate_b，以及原因。
```

每条偏好至少包含两个候选、偏好方向、保留/拒绝部件、下一轮建议、目标与观察风格，以及对应 spec、连续播放证据、manifest 和生成器版本。只有静态联系表而用户无法可靠判断时，不得强制生成人工 A/B 标签；该批次保留为待交互播放复核数据。绝对分用于解释，不作为首版核心标签。

## 4. 特征矩阵

`workspace.tools.vfx_training_features` 将结构和真实画面证据转换为：

```text
candidate_features.jsonl
candidate_features.csv
feature_schema.json
```

结构特征包括特效族、拓扑、控制点、宽度、层级、Material/Shader/Texture tag、slot role、时序和风格轴。图像特征包括主体面积、包围盒、质心、亮度、过曝、饱和度、边缘密度、峰值时间和帧间变化。

特征不是标签。没有人工偏好时，只允许生成 feature-only 数据集。

## 5. 数据划分与泄漏防止

禁止随机拆分同一候选的镜像偏好对。优先按 `run_id`、参考案例/来源 Prefab 组和风格家族进行留出。同一 Prefab 或同一 reference seed 的近邻变体不能同时进入训练集和最终测试集。

只有单 run 的 smoke 实验才允许按原始 pair 分组，并必须标记 `candidate_leakage_risk`。

### 5.1 MaterialTrajectory R002 当前划分

MaterialTrajectory R002 使用 `strict_shader_material_components.v1`：先按 Shader group 形成不可拆分组件，Material group 必须完全包含在同一组件内，再分配 train / validation / test。

当前只有 3 个 Shader group，规格分布为 `93 / 6 / 1`，所以严格无泄漏划分是：

```text
material state: train 93 / validation 1 / test 6
image conditioned: train 67 / validation 0 / test 5
```

该划分的 Material 和 Shader overlap 都为 0，但严重失衡。状态任务可以用于数据加载、特征和受控轨迹实验；图像任务只能标记为 feature-only，因为 validation 为空。不得为了得到漂亮的 80/10/10 数字而拆散 Shader group。

## 6. 样本门槛

跨特效族共享与迁移的边界见 [VFX 多特效训练与迁移策略](../00-总纲/VFX多特效训练与迁移策略.md)。该策略规定：技术闭包、结构和失败路由可共享；目标族审美偏好、主体拓扑、命中语义和风格匹配必须独立采集。

| 等级 | 最低门槛 | 允许用途 |
|---|---|---|
| Feature-only | 1 个可渲染候选 | 检查特征、schema、路径和范围；不能训练权重 |
| Smoke model | 8 候选、20 个非 tie 偏好对、允许单 run | 验证训练代码；不得指导正式生成 |
| Baseline model | 24 候选、60 个偏好对、至少 3 个独立 run | 候选排序辅助；按 run 交叉验证 |
| Promotion candidate | 100 候选、300 个偏好对、至少 5 个 run、独立来源/风格留出 | 受控 VFXSpec 提案试验，仍需人工批准 |

默认训练命令要求至少 20 个偏好对、8 个候选和 2 个独立 run。单 run 必须显式使用 `--allow-single-run`。

## 7. 首版模型

第一版权重使用 scikit-learn Logistic Regression：

```text
P(A 优于 B) = model(feature(A) - feature(B))
```

它适合小样本、可解释、训练快，也容易暴露数据泄漏。模型输出必须包含：

```text
preference_ranker.joblib
metrics.json
model_feature_schema.json
MODEL_CARD.md
```

`joblib` 仅允许加载本项目本机生成的可信文件。

## 8. 指标与晋级

至少报告 Pairwise ROC-AUC、accuracy、log loss、候选数、人工比较数、独立 run 数、特征系数和泄漏风险。

Promotion candidate 至少满足：独立 run/来源留出的 ROC-AUC `>= 0.70`；至少一次“模型排序 -> 人工复核 -> 下一轮变异”闭环；新一轮人工胜率优于随机和规则基线。

模型文件存在、训练集准确率高或截图生成成功都不等于模型有效。

## 9. 权重如何指导 VFXSpec

第一阶段模型只做排序：

```text
候选池 -> preference_score -> 人工审核 Top K -> MutationSpec
```

第二阶段才允许使用系数、局部搜索或提案模型改变拓扑、控制点、层级、Material/Shader/Texture、时序和风格。模型不得直接写入主 Unity 场景。

## 10. 命令

组装 MaterialTrajectory 执行证据：

```powershell
python -m workspace.tools.vfx_generation.material_trajectory_dataset `
  --curriculum-root workspace/data/vfx_generation/curricula/material_trajectory_curriculum_r002 `
  --run-root workspace/data/vfx_generation/runs/material_trajectory_r002_full_r001 `
  --output-root workspace/data/vfx_generation/datasets/material_trajectory_r002_training_r001 `
  --dataset-id material_trajectory_r002_training_r001 `
  --seed 20260828
```

输出包含 100 条 `material_state_examples.jsonl`、72 条 `image_conditioned_examples.jsonl`、完整 `examples.jsonl`、split 文件和 `dataset_manifest.json`。所有 R002 样本的 `aesthetic_quality` 必须保持 `unlabeled`。

组装 Prefab 结构与 Play Mode 证据：

```powershell
python -m workspace.tools.vfx_generation.prefab_structure_dataset `
  --cases workspace/data/vfx_generation/datasets/trains_fx_all_002/prefab_cases.jsonl `
  --audit workspace/data/vfx_generation/audits/effectdemo_prefab_structure_audit_r2.json `
  --unity-project UnityDemo/EffectDemo `
  --render-run-root workspace/data/vfx_generation/runs/trains_prefab_playmode_r002 `
  --output-root workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002 `
  --dataset-id prefab_structure_r002_training_r002
```

Prefab 数据加载器按 `prefab_structure / particle_parameters / play_mode_render_candidate / image_conditioned` 隔离任务；请求 `aesthetic_preference` 必须拒绝。

生成特征矩阵：

```powershell
python -m workspace.tools.vfx_training_features `
  --run-root workspace/data/vfx_generation/runs/<run_id> `
  --output-dir workspace/data/vfx_generation/datasets/features/<run_id>
```

训练排序模型：

```powershell
python -m workspace.tools.vfx_preference_ranker train `
  --features workspace/data/vfx_generation/datasets/features/<run_id>/candidate_features.jsonl `
  --feedback workspace/data/vfx_generation/runs/<run_id>/feedback.jsonl `
  --output-dir workspace/data/vfx_generation/models/<model_id>
```

应用模型排序：

```powershell
python -m workspace.tools.vfx_preference_ranker rank `
  --model workspace/data/vfx_generation/models/<model_id>/preference_ranker.joblib `
  --features workspace/data/vfx_generation/datasets/features/<run_id>/candidate_features.jsonl `
  --output workspace/data/vfx_generation/runs/<run_id>/model_ranking.json
```

## 11. 依赖和插件边界

根目录 `requirements-training.txt` 锁定 NumPy、pandas、OpenCV headless、scikit-learn、joblib 和 Pillow。

- PyTorch 当前作为 PrefabGraph 多任务结构实验模型的可选依赖；首版偏好排序 baseline 仍不依赖它；
- Unity Sentis 只在未来需要 Unity 内推理时考虑；
- ML-Agents 不适合当前候选排序，不安装；
- VFX Graph 是制作工具，不是训练框架；
- TensorBoard 在进入深度模型训练前不安装；
- 不因 GitHub Star 高就安装运行时插件。

## 12. 记录要求

每次训练必须在 Beads 中记录输入 run、feature schema、feedback、候选/比较/run 数、命令、依赖版本、随机种子、指标、权重和 Model Card 路径、泄漏风险、失败和下一步。

## 13. 专业 Teacher 窄轴训练基线

`professional_explosion_core_readability_r001` 是首条完成“专业原话/时间码 -> Unity 受控复刻 -> 跨候选迁移 -> 成对梯度下降”的规则。

- 受控复刻 R006 只改 Core Alpha，两侧编译、贴图回读、Prefab API 回读和 34 帧 Play Mode 均通过；中心亮度/局部对比度增益为 `0.24285/0.24217`。
- 迁移批次对 8 个爆炸候选全部重新编译、回读和同配置重捕，技术通过 `8/8`，核心轴增益通过 `8/8`。
- 训练视图为 8 对/16 条，pair 级 `4/2/2` 分区，overlap 为 0；不消费非专业人工审美。
- PyTorch MLP 使用 AdamW 与成对损失，train/validation/test pair accuracy 均为 `1.0`，但 test 只有 2 对。
- 模型状态固定为 `pilot_narrow_axis_not_general_quality`，只能排序 `explosion/core_readability`，通用质量头仍阻塞。
- 模型推理必须先过输入分布门禁；旧三层模型对四层爆炸返回 `blocked_out_of_distribution` 时不得强行排名。四层 Core-off/Core-on 另建 8 对训练视图后，新 seed 批次才允许用四层专用 checkpoint 排序。
- 残留持续性使用 Residual-off/on 同拓扑对，且必须强制同一镜头；必须同时满足“残留出现前帧几乎不变”、“晚段活跃比例增加”、“晚段可见面积增加”和“最后可见时间延长”。
- `professional_residual_rule_ranker_r001` 仅训练 `explosion/residual_persistence`；其分数不包含烟雾材质美感、颜色协调或总体节奏质量。
- 冲击波使用 Shockwave-static/expanding 同拓扑对，固定 `front`、正交尺寸 `3.0` 和 `640x640`。多层 Prefab 不用完整画面最大半径作为单层真值，而在同种子成对差异图中计算内外圈径向分离、外缘单调性和可见差异。
- `professional_shockwave_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2` 分组和 AdamW 成对梯度下降，只训练 `explosion/shockwave_expansion`。独立 Prompt/seed 批次 R007 为 `8/8` 技术通过、`8/8` 分布内。
- Shockwave 推理必须先通过 `shockwave_fixed_orthographic_v1` 捕获协议；自动取景或不同分辨率的帧必须拒绝，不能把相机构图差异交给窄轴模型评分。
- Debris Teacher 使用同种子 `no_debris/radial_debris` 对，只改变碎片 Alpha；以成对差异图中的离散组件数、径向范围和有效时间帧验证“小型分支或碎片离开核心”。R007、R008 两批迁移均为 `8/8` 通过，合并数据 `16` 对/`32` 条，pair 级 `8/4/4` 分组且无泄漏。R001 模型在 R008 上只有 `5/8` 分布内，保持 OOD 门禁并增加第二批数据后，R002 模型在全新 R009 上达到 `8/8` 分布内；不得用放宽阈值替代数据覆盖。
- 核心材质结构使用相同 Shader、颜色、粒子参数和固定镜头，只替换单帧纹理。`professional_explosion_core_texture_structure_r001` 中结构化软边纹理相对平坦光盘的 bbox fill 降低 `0.3461`、edge density 增加 `0.0521`、中心亮度保留比例为 `0.8057`，状态为 `verified`。亮度标准差只保留为诊断值，不作为透明纹理结构门禁。
- Core 材质批量迁移必须只统计 Support 启动前的 Core-only 时间窗。R010 的 8 对平坦/结构化纹理在该窗口全部通过；`professional_explosion_material_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2` 训练。显式 `structured_flame` 档位生成的独立 R011 为 `8/8` 材质分布内，同时 Shockwave、Debris、Residual 均为 `8/8` 分布内。旧 Core readability 模型仍为 `0/8` OOD，需单独扩样。
- 结构化 Core readability 使用固定 `640x640`、正交尺寸 `1.5` 和 Support 启动前的中心区域。R011 的 Core-off/on 迁移为 `8/8`，新模型使用 8 对/16 条、pair 级 `4/2/2`。完全未参与训练的 R012 为 `8/8` 技术通过，Core readability、Core material、Shockwave、Debris、Residual 五轴均 `8/8` 分布内。
- 完整节奏 Teacher 只修改 Support、Hit、Residual 的启动延迟，其他材质、贴图、数量、速度、寿命和颜色保持不变。正式门禁同时要求 Graph 满足 `Core < Support < Hit < Residual`、画面早期外围重叠下降、晚段可见时间延长；绝对像素 onset 可能被 Core 尖角或光晕越过分区边界，只能作为诊断值。
- 节奏批量训练使用 simultaneous/staged 同拓扑对，特征同时包含层间 delay gap、早期外围重叠和晚段残留证据。`professional_explosion_rhythm_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`，独立 R013 为 `8/8` Unity 技术通过、`8/8` 分布内；该分数只表示 staged rhythm，不是全局审美分。
- 刀光首条 Teacher 使用真实 `Slash4.fbx`、显式 `Trail68.png` 和已验证 QFX 粒子 Shader。外主刃/内辅刃对只修改内层尺寸和 Alpha；正式门禁验证外层更长更亮、主轮廓宽度保留和全长高亮跨度收缩。Hovl `SwordSlash.mat` 因依赖未建模的 Particle vertex streams 在通用 Graph 中 near-blank，不能仅凭引用完整宣称可复现。
- 刀光层级批量训练使用 equal/outer-dominant 同拓扑对，特征同时包含外/内尺寸与 Alpha 比例、可见宽度和高亮跨度。`professional_slash_layer_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`；全新 R004 为 `8/8` 编译、Mesh/API 回读、Play Mode 和分布门禁通过。
- 刀光方向拖带 Teacher 必须关闭主刃和内层，只比较 DirectionTrail。错误版沿相机深度轴运动，正确版将局部发射轴旋转到画面攻击方向；首轮正确版水平质心跨度 `0.282`、水平/纵向比 `15.67`、相对基线水平增益 `0.272`，状态 `verified`。
- 刀光方向模型使用 8 对/16 条、pair 级 `4/2/2` 无泄漏数据和 AdamW 成对梯度下降。全新 R006 为 `8/8` 技术通过、`6/8` 分布内；另外 2 条保留 OOD，不能因原始分数高而绕过门禁。
- 刀光 Hit Teacher 保持 Mesh、材质、`FX_Hit_1.png`、大小、时序和相机一致，只把局部亮点从刀光中心移动到攻击端点。R003 受控复刻的接触区平均亮度增益为 `0.0949`、顶部亮像素增益为 `0.1243`、差异质心到目标距离为 `0.0179`，状态 `verified`。
- Hit 批量训练使用 center/contact-aligned 同拓扑对，特征包含接触位置误差、Hit 尺寸与时序、接触区亮度和有效帧数。`professional_slash_hit_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`；全新 R011 为 `8/8` Unity 技术通过、`8/8` 分布内。该分数只表示接触点聚焦，不评价完整刀光。
- 刀光 Residual Teacher 只修改 DirectionTrail 的启动延迟与寿命。正确版先保留 Core/Hit 可读峰值，再于 `0.18s` 启动并延续到非残留层结束后 `0.12s`；首轮晚段活跃比例增加 `0.333`、最后可见时间增加 `0.445s`，状态 `verified`。
- Residual 批量训练使用 premature/staged 同拓扑对，`professional_slash_residual_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`。全新 R013 为 `8/8` Unity 技术通过、`8/8` 分布内；该分数只表示 `slash/readable_then_fade`，不评价完整节奏。
- 完整刀光节奏 Teacher 只把 Support、Hit、Residual 的启动延迟从全 0 改为 `0.01/0.065/0.18s`。正式门禁要求 `Core < Support < Hit < Residual`、早期叠加下降、命中窗口端点峰值可读和晚段残留延长。8 对迁移和 `professional_slash_rhythm_rule_ranker_r001` 均已完成，独立 R014 为 `8/8` 分布内。
- 新层加入后必须重查旧窄轴分布。旧 Layer/Direction 模型对四层 R014 均为 `0/8` OOD；使用当前四层 R012 重建各 8 对数据并训练 v2 后，R014 两轴恢复为 `8/8`。这是拓扑适配，不得以放宽 OOD 阈值替代。
- 多轴结果不得直接相加原始 logit。`professional_slash_multi_axis_rank.py` 只在全部轴分布内的候选中融合各轴分位排名；R014 的 Layer、Direction、Hit、Residual、Rhythm 五轴交集为 `8/8`。
- 雷电族第一条 Teacher 使用 EP004 `00:17:10-00:24:34` 的“中心主电流更粗、外围分支更细且克制”规则。A/B 关闭 Hit 与 Residual，只修改 BranchSupport 尺寸和 Alpha；Teacher 编译、回读、Play Mode 与层级门禁均通过。
- 雷电层级批量迁移必须比较同一时间帧，不能比较两版各自峰值。R001 参数迁移只有 `4/8`，收紧生成器分支范围后，独立峰值比较仍有 2 条假负值；改用同时间帧后 R002 为 `8/8`。`professional_lightning_hierarchy_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`；独立 R003 为 `8/8` 技术通过和 `8/8` 分布内。
- 雷电命中 Teacher 只修改 ImpactFlash Alpha，固定位置、尺寸、贴图和时序。Teacher 命中区域平均亮度增益 `0.3825`、顶部亮像素增益 `0.9185`；8 对迁移全部通过。独立 R004 的 ImpactFocus 为 `7/8` 分布内，1 条保持 OOD，不得放宽阈值。
- 雷电瞬时脉冲 Teacher 关闭其他三层，仅把 MainBolt lifetime 从 `0.36s` 缩短为 `0.14s`；早期峰值保留 `1.0`、最后可见时间提前 `0.22s`、活跃帧减少 11，状态为 `verified`。
- 脉冲批量训练和推理必须使用 Core-only 派生 Graph。完整四层直接比较会被 Support/Hit/Residual 遮蔽，首轮出现技术 `8/8` 但规则 `0/8`；隔离后 8 对全部通过。`professional_lightning_pulse_rule_ranker_r001` 使用 8 对/16 条、pair 级 `4/2/2`；独立 R005 也必须先派生、编译和回读 Core-only Graph，最终为 `8/8` 分布内。
- 雷电余电 Teacher 只开关 ResidualSpark Alpha。首轮约 `0.24s` lifetime 的晚段活跃增益仅 `0.133`，没有降低 `0.15` 门槛；将两版共同 lifetime 延长到 `0.30s` 后，晚段活跃比例增益 `0.267`、最后可见时间增益 `0.28s`，Teacher verified。完成 8 对迁移前不得称为正式余电模型。
- 窄轴模型不得把完整时段的全图统计与轴特征混合。Residual 只读取非残留层结束后的晚段；Shockwave 只读取冲击环时窗；Debris 只读取中心半径外的离散组件。R010 同帧复验中，轴局部模型使 Shockwave、Debris 从 `0/8` 恢复到 `8/8` 分布内。Residual 还必须匹配 `residual_fixed_orthographic_v1` 的分辨率和采样间隔；合并第二批后在匹配协议的 R010 上恢复为 `8/8`。

复现入口：

```powershell
python -m workspace.tools.vfx_generation.professional_teacher_guided_generation --help
python -m workspace.tools.vfx_generation.professional_core_rule_model --help
python -m workspace.tools.vfx_generation.professional_residual_rule_model --help
python -m workspace.tools.vfx_generation.professional_shockwave_ablation --help
python -m workspace.tools.vfx_generation.professional_shockwave_rule_model --help
```

完整证据见 `knowledge/experiments/EXP-2026-119_专业爆炸核心Teacher闭环R001.md`。
