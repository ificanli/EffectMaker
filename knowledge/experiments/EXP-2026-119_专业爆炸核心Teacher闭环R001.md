# EXP-2026-119：专业爆炸核心 Teacher 闭环 R001

## 目标

将专业特效师关于“爆炸需要核心体积，外围细节不能代替核心”的明确判断，转换为可定位、可复刻、可执行、可训练的窄轴 Teacher 监督。

## 专业证据

- 来源：`SRC-2026-001`，三生路_王先生特效，作者页面说明为网易资深特效师。
- 时间码：`00:09:29-00:12:07`。
- 证据帧：`knowledge/sources/SRC-2026-001/visual_check/03_explosion_core/`。
- 判断轴：`explosion / core_readability`；`layer_separation` 和 `composition` 只保留为相关轴，本次不训练通用分数。

## Unity 受控复刻

`professional_teacher_explosion_core_r001-r006` 始终保持 Core / Support / Hit 三层结构、捕获种子、镜头和采样规则可追溯。R001-R005 保留为失败证据：

1. R001 暴露二值中心占用指标被 Support 层占满后失效。
2. R002 暴露 `Glow2.png` 实为空心环，不是中心体积贴图。
3. R003-R004 分别定位了材质响应偏弱和 Renderer sorting order 覆盖。
4. R005 暴露 staging 缺配套材质以及关闭 Color over Lifetime 后的 Unity API 回读归一。
5. R006 使用源绑定 `MFX_Flare_4.mat + FX_Glow_1.TGA`，只改 Core Alpha 做最终因果对照。

R006 结果：

| 门禁 | 结果 |
|---|---|
| Graph 变量 | 只有 `core.start_color_rgba.alpha` |
| Unity 编译 | 2/2 pass |
| 贴图计划回读 | 2/2 match |
| Prefab API 回读 | 2/2 pass |
| Play Mode | 34/34 帧 x 2，同镜头，错误洋红 0 |
| 中心亮度增益 | `0.24285`，门槛 `0.03` |
| 中心局部对比度增益 | `0.24217`，门槛 `0.02` |
| Teacher readiness | `ready`，1 条 |

## 规则迁移

`professional_teacher_guided_explosion_r001` 将已验证核心先验应用到 8 个现有卡通爆炸候选，并将原候选与引导候选用同一采样器重捕。

- Unity 编译 / 贴图回读 / Prefab API 回读 / Play Mode：`8/8`。
- 专业规则迁移：`8/8`。
- 中心亮度增益：`0.1374-0.3037`。
- 中心局部对比度增益：`0.1374-0.3033`。
- 联系表：`workspace/data/vfx_generation/generated/professional_teacher_guided_explosion_r001/comparison_contact_sheet.png`。

## 窄轴神经网络

`professional_core_rule_training_r001` 含 8 对、16 条时序图像样本，以 pair 为分组单位分成 `4/2/2` 个 train/validation/test 对，泄漏为 0。`professional_core_rule_ranker_r001` 是 PyTorch MLP，使用 AdamW 和 `softplus(-(guided_score-baseline_score))` 成对梯度下降；三个分区的 pair accuracy 均为 `1.0`。

已用带分布检测的 R002 checkpoint 对 8 个 Teacher 引导候选完成实际推理，7/8 在训练分布内，分布内 Top-1 为 `teacher_guided_000_pfg_6620f1f451a4b7ff44e0`。新四层爆炸 `layered_explosion_family_r003` 技术门禁为 8/8，但 8/8 均被该窄轴模型判定为分布外，所以排名状态为 `blocked_out_of_distribution`。分数是未校准的相对提案分，不是审美绝对分。

测试集只有 2 对，因此 checkpoint 状态只能是 `pilot_narrow_axis_not_general_quality`。它可用于爆炸 Core 提案排序，不得作为通用特效质量、风格、节奏或其他特效类型的证据。

## 主要产物

- 受控复刻：`workspace/data/vfx_generation/generated/professional_teacher_explosion_core_r006/`
- Teacher readiness：`workspace/data/vfx_generation/course_knowledge/professional_aesthetic_teacher_readiness_r003/`
- 引导批次：`workspace/data/vfx_generation/generated/professional_teacher_guided_explosion_r001/`
- 训练数据：`workspace/data/vfx_generation/datasets/professional_core_rule_training_r001/`
- 模型：`workspace/data/vfx_generation/models/professional_core_rule_ranker_r001/`

## 下一步

继续从独立专业来源扩充爆炸的外扩、碎片、残留和节奏轴，再分别为刀光、雷电、火焰、护盾建立自己的 Teacher 闭环。在多族、多轴、多专业来源达标前，通用质量头继续阻塞。
