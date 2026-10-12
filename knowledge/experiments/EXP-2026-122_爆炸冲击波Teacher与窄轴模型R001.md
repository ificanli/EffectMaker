# EXP-2026-122 爆炸冲击波 Teacher 与窄轴模型 R001

## 目标

把专业资料中的“冲击层应从命中中心向外扩张”从文字规则变成可迁移的 Unity 动态监督，并验证新 Prompt、新 seed 候选能否由窄轴模型排序。

## 专业证据

- 来源：`SRC-2026-SERIES-001 / EP004 / 案例06`。
- 时间码：`00:24:34-00:34:10`。
- 专家判断：冲击层应在命中亮点之后从中心向外扩张，不能只是停在原地的单贴图。
- 证据帧：`knowledge/sources/SRC-2026-SERIES-001/ep004/visual_check/05_impact_burst_layers/`。
- 授权边界：仅内部学习，不重新分发来源视频。

## Teacher 复刻

`professional_teacher_explosion_shockwave_r002` 使用单张圆环贴图 `Glow2.png`，只修改 Support 的 `end_size_multiplier`。静止环半径增长为 `0`，外扩环半径增长为 `0.20862`，外扩单调比例为 `1.0`，同帧最大半径增益为 `0.23285`，状态为 `verified`。

R001 曾误用 `3x3` 序列图，因当前编译器没有 Texture Sheet Animation 支持而同时显示九个圆环，禁止作为 Shockwave 训练资产。

## 四层迁移

`layered_explosion_shockwave_ablation_r001` 对 R006 的 8 个四层候选分别生成 Shockwave-static/expanding 对。所有对固定：

- `front`；
- 正交尺寸 `3.0`；
- `640x640`；
- 相同候选 ID、粒子随机种子、时间点、材质、贴图和其他三层。

结果：

- 编译、贴图计划回读、Prefab API 回读、Play Mode：`8/8`；
- 专业规则迁移：`8/8`；
- 成对差异图内外圈峰值径向分离：`0.258-0.267`；
- 差异外缘单调比例：`0.95-1.00`；
- 联系表：`workspace/data/vfx_generation/generated/layered_explosion_shockwave_ablation_r001/shockwave_pair_contact_sheet.png`。

首版统计使用首帧到峰值增长和完整四层最大半径，错误得到 `0/8`。原因是捕获第 0 帧已进入粒子生命周期，且 Debris 会污染全图半径。最终改为同帧成对差异图的 `p90-p10` 径向分离，仍使用 Teacher 的 `0.20/0.15` 阈值，没有降低标准。

## 训练

`professional_shockwave_rule_training_r001` 含 8 对/16 条，pair 级 train/validation/test=`4/2/2`，泄漏为 0。`professional_shockwave_rule_ranker_r001` 使用 PyTorch MLP、AdamW 和 `softplus(-(expanding_score-static_score))` 成对损失；三个分区 pair accuracy 均为 `1.0`，测试集只有 2 对。

模型只允许评价 `explosion/shockwave_expansion`，不评价冲击波贴图、材质、完整节奏或整体质量。推理必须使用 `shockwave_fixed_orthographic_v1`；错误使用 R006 的自动取景 `512x512` 截图时，OOD 门禁正确返回 `0/8` 分布内。

## 独立回归

`layered_explosion_family_r007` 改变 Prompt 和 seed：

```text
卡通火焰爆炸，中心闪光后出现清晰单环冲击波，碎片向外散射，烟雾延迟消散
seed: 20261304-20261311
```

结果：

- Unity 编译：`8/8`；
- Prefab API 回读：`8/8`；
- 固定正交 Play Mode：`8/8`；
- 模型分布内：`8/8`；
- Top-1：`layered_explosion_003_pfg_bad9a72d8a6caa37a372`。

## 结论与边界

Shockwave 已完成“专业证据 -> 单变量复刻 -> 四层迁移 -> 成对数据 -> 梯度训练 -> 独立推理”闭环。它仍是小样本窄轴模型，不是完整爆炸生成质量模型。下一优先级是 Debris 分支、方向性和散射密度 Teacher，之后再组合完整爆炸节奏与材质。
