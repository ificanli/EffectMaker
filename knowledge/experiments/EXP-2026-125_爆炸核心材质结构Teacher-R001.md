# EXP-2026-125 爆炸核心材质结构 Teacher R001

## 目标与来源

来源为 `SRC-2026-SERIES-001 / EP007`，时间码 `01:01:14-01:09:43`、`01:41:37-01:45:20`。专业判断为：火焰不能只是一整块高亮贴片，应保留中心高亮、外部暗色、可识别轮廓和软边结构。

## 受控实验

`professional_teacher_explosion_material_r001` 保持 Core 的 Shader、材质模板、粒子参数、颜色、相机、随机种子和时间点不变，只替换纹理：

- 基线：`FX_Glow_1.TGA` 均匀径向光盘；
- 提案：`Tex_xingzhe_fire3_0e15be311470531b.png` 单帧结构化软边纹理。

Support、Hit 和 Residual 在两侧均关闭，捕获固定为 `front`、正交尺寸 `1.5`、`640x640`。

## 结果

- Unity 编译、贴图计划回读、Prefab API 回读、Play Mode：`2/2`；
- bbox fill 降低：`0.34609`；
- edge density 增加：`0.05211`；
- 中心亮度保留比例：`0.80567`；
- 材质渲染错误：`0`；
- 状态：`verified`。

首版曾把“可见像素亮度标准差必须增加”作为门禁，实际得到 `-0.02944`。该指标会被 Alpha 裁切改变采样集合，不能表达“是否为平坦贴片”，因此保留为诊断值，正式门禁改为轮廓填充下降、边缘结构增加和中心亮度保留三项联合判断。

联系表：`workspace/data/vfx_generation/generated/professional_teacher_explosion_material_r001/material_pair_contact_sheet.png`。

Teacher 已并入 `professional_teacher_verified_r004`，`professional_aesthetic_teacher_readiness_r007` 为 `5/5 ready`。

## R010 跨轴回归

结构化纹理曾临时接入 `explosion_family_adapter.v3`，随后生成新 seed 的 R010。R010 为 `8/8` 编译、Prefab API 回读和 Play Mode 技术通过，但四个既有模型的分布门禁结果为：

- Core：`1/8` 分布内；
- Residual：`0/8` 分布内；
- Shockwave：`0/8` 分布内；
- Debris：`0/8` 分布内。

这不能证明其他三层视觉退化。根因是现有窄轴模型仍从完整合成画面提取特征，Core 纹理变化会改变所有模型的输入分布。结构化纹理因此回退为候选资产，不作为默认生成纹理。

Residual、Shockwave、Debris 模型随后移除完整时段的全局图像特征：Residual 只读晚段，Shockwave 只读冲击环时窗，Debris 只读中心半径之外的组件。复用完全相同的 R010 帧后，Shockwave 与 Debris 都恢复为 `8/8` 分布内，证明跨层污染已被消除；Residual 仍为 `0/8`，其晚段可见面积超过旧训练范围，需要新增残留消融数据，而不能放宽阈值。Core 材质本身仍需独立排序模型。

## 材质模型与 R011

R010 的 8 个结构化候选分别生成平坦 Core 基线。首轮使用 0.45 秒窗口时外围层污染指标，规则迁移为 0/8；按每个候选的 Support 启动时间截断 Core-only 窗口后，8/8 技术与材质规则通过。数据集含 8 对/16 条、pair 级 `4/2/2`、泄漏 0，`professional_explosion_material_rule_ranker_r001` 三分区 pair accuracy 均为 1.0。

生成器新增显式 `--core-texture-profile structured_flame`，默认仍为 `flat_glow`。全新 seed 的 R011 使用结构化档位，结果：

- Unity 编译、Prefab API 回读、Play Mode：`8/8`；
- Core 材质结构：`8/8` 分布内；
- Shockwave：`8/8` 分布内；
- Debris：`8/8` 分布内；
- Residual：`8/8` 分布内；
- 旧 Core readability：`0/8` OOD。

因此结构化纹理已具备材质与非目标三轴的独立证据，但仍保持显式 opt-in，直到 Core readability 用结构化样本扩充并通过下一批独立回归。
