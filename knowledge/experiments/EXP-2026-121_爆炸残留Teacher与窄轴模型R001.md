# EXP-2026-121：爆炸残留 Teacher 与窄轴模型 R001

## 专业规则

- 来源：`SRC-2026-001`，三生路_王先生特效，作者页面说明为网易资深特效师。
- 时间码：`00:57:40-00:58:47`。
- 原话规则：爆炸后应有残留，不应在峰值后瞬间清空。
- 画面证据：`knowledge/sources/SRC-2026-001/visual_review_44-66/evidence/00-57-48.jpg`、`00-57-55.jpg`、`00-58-48.jpg`。
- 训练范围：仅 `explosion/residual_persistence`，不包含残留材质美感或总体节奏质量。

## 受控 Unity 复刻

`professional_teacher_explosion_residual_r001` 以四层爆炸 Top 候选为基础，只修改 `residual.start_color_rgba.alpha`：

| 门禁 | 结果 |
|---|---|
| Graph 变量 | 只有 Residual Alpha |
| Unity 编译 / 贴图回读 | 2/2 pass |
| Prefab API 回读 | 2/2 pass |
| Play Mode | 同镜头、同帧数、错误洋红 0 |
| 早期帧最大 MAE | `0.0000902`，门槛 `<=0.002` |
| 晚段活跃帧比例增益 | `0.27027`，门槛 `>=0.15` |
| 晚段可见面积增益 | `0.001488`，门槛 `>=0.0005` |
| 最后可见时间增益 | `1.15s`，门槛 `>=0.3s` |

结论为 `verified`。该规则与核心规则合并到 `professional_teacher_verified_r001`，`professional_aesthetic_teacher_readiness_r004` 显示 `teacher_ready_count=2`。

## 批量迁移与训练

`layered_explosion_residual_ablation_r002` 对 8 个四层候选生成 Residual-off/on 对。首次 R001 虽所有数值增益达标，但 6 对由自动取景选了不同视角，只有 2/8 通过。Capture v2 随后增加仅用于受控对照的 `forced_camera_view=front`，重捕后：

- 技术门禁：`8/8`。
- 残留规则迁移：`8/8`。
- 晚段活跃比例增益：`0.2632-0.3514`。
- 晚段可见面积增益：`0.001623-0.002817`。
- 最后可见时间增益：`1.10-1.30s`。
- 联系表：`workspace/data/vfx_generation/generated/layered_explosion_residual_ablation_r002/residual_pair_contact_sheet.png`。

`professional_residual_rule_training_r001` 含 8 对/16 条样本，pair 级 train/validation/test=`4/2/2`，泄漏 0。`professional_residual_rule_ranker_r001` 是 PyTorch MLP，用 AdamW 与成对 softplus 损失训练，三分区 pair accuracy 均为 `1.0`。

独立推理使用未参与该模型训练的 `layered_explosion_family_r004`：7/8 候选通过 L2 分布门禁，1/8 保留为 OOD；分布内 Top-1 为 `layered_explosion_005_pfg_3ef5dcdf4fe51010ccd9`。

## 边界

此模型只能回答“爆炸峰值后是否有持续残留”，不能回答残留的烟雾材质是否自然、颜色是否协调、节奏是否达到商业品质。后三项需要独立专业规则和更多来源。

## 产物

- 受控复刻：`workspace/data/vfx_generation/generated/professional_teacher_explosion_residual_r001/`
- 联合 Teacher：`workspace/data/vfx_generation/course_knowledge/professional_teacher_verified_r001/`
- readiness：`workspace/data/vfx_generation/course_knowledge/professional_aesthetic_teacher_readiness_r004/`
- 成对迁移：`workspace/data/vfx_generation/generated/layered_explosion_residual_ablation_r002/`
- 训练数据：`workspace/data/vfx_generation/datasets/professional_residual_rule_training_r001/`
- 模型：`workspace/data/vfx_generation/models/professional_residual_rule_ranker_r001/`
