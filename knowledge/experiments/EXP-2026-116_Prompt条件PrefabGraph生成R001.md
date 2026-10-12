# EXP-2026-116：Prompt 条件 PrefabGraph 生成 R001

## 目标

验证不读取 parent Prefab 的 Prompt 条件技术链路：Prompt -> 条件 profile -> Grammar Graph -> Asset Route -> Unity 2022 新 Prefab -> Play Mode 动态抓帧。人工静态 A/B 不参与本实验，所有训练条件标签明确标为 `ai_hypothesis`。

## 条件数据与模型

| 项目 | 结果 |
|---|---|
| 数据集 | `prefab_graph_prompt_condition_r003` |
| 条件样本 | 64 |
| 特效族 | lightning、explosion、slash、fire、shield、smoke、water、magic_circle |
| 条件字段 | effect family、style、timing、performance tier、color |
| 划分 | train/validation/test=`38/13/13`，两个目标 profile 都出现在 validation/test |
| 标签来源 | `ai_hypothesis`，human=0，aesthetic=0 |
| 模型 | `prompt_graph_profile_r004`，PyTorch MLP |
| 留出指标 | validation accuracy=`1.0`，test accuracy=`0.9231` |

该模型是类型/课程先验路由器，不是任意自然语言模型，也没有学习视觉质量。Prompt 先通过显式关键词解析器转换成规范条件，模型只预测 `particle_v1` 或 `multi_particle` profile；Graph Token 仍由 Grammar 约束。

## 最终技术候选

| 条件 | 雷电候选 | 爆炸候选 |
|---|---|---|
| Prompt | 写实蓝色雷电，快速爆发，标准性能，不要长拖尾 | 卡通橙色爆炸冲击，中等节奏，标准性能，不要长拖尾 |
| Profile | `particle_v1` | `multi_particle` |
| Graph | 2 节点 / 1 ParticleSystem | 4 节点 / 3 ParticleSystem |
| AssetPlan | `pass` | `pass` |
| Unity compile | `pass`，source Prefab read=false | `pass`，source Prefab read=false |
| 运行帧 | 14/14 valid | 21/21 valid |
| 可见性 | visible，max ratio=`0.0227` | visible，max ratio=`0.0361` |
| 最终状态 | `pass_technical_prompt_unscored` | `pass_technical_prompt_unscored` |

生成 Graph 使用运行验证过的 `Mat_fozu_03` 模板，由 Unity 编译器克隆成独立材质，并生成 `spark`/`soft_disc` Texture2D。没有读取 parent Prefab，也没有写主场景。

## 失败与修复

失败明细保存在 `workspace/data/vfx_generation/generated/prompt_graph_generation_r001/failure_samples.jsonl`：

1. 负面约束“不要长拖尾”误触发 long timing，改为先隔离负面片段。
2. 条件向量表达式优先级错误，风格/节奏/性能/颜色被编码为空，改为显式字段分支。
3. 类别不平衡与非分层验证掩盖多层 profile 失败，改为 profile 分层和类别加权。
4. 直接绑定任意审计材质导致 14/21 张全黑有效 PNG，改为运行验证模板克隆和确定性贴图。

## 视觉边界

本实验的最终帧已经可见，但视觉上只是基础蓝色拖形和红橙软团。它们不能被称为完成的雷电或爆炸，更不能作为审美正例。模型当前只证明 Prompt 条件会影响 profile、颜色和参数，并能通过 Unity 技术门禁。下一阶段必须增加雷电路径/分叉、爆炸核心/冲击波/碎片/残留等特效族专用拓扑，再进行动态人工复核。
