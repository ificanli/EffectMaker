# EXP-2026-129 爆炸完整节奏 Teacher R001

## 专业证据

EP004 `00:24:34-00:34:10` 明确提出“命中亮点→扩散线→外围元素→残光/小元素”的时间层；EP006 `00:10:00-00:20:00` 要求短爆发后快速收束并保留少量外围残留。

## 受控实验

以 R012 的完整四层结构为基础，只修改 Support、Hit、Residual 的 `start_delay_max`：

- `simultaneous_layers`：后三层全部从 `0s` 起播；
- `staged_layers`：Core `0.00s`、Shockwave `0.04s`、Debris `0.07s`、Residual `0.20s`。

所有材质、贴图、粒子数量、速度、寿命、颜色、相机和随机种子保持一致。两侧均完成 Unity 编译、贴图计划回读、Prefab API 回读和固定正交 Play Mode。

## 结果

- Graph 差异仅为三层启动延迟；
- 分层版本早期外围重叠减少：`0.00481`；
- 分层版本最后可见时间延长：`0.20s`；
- 分层版本按 `Core < Support < Hit < Residual` 排序；
- Teacher 状态：`verified`。

首版尝试用固定半径的绝对像素 onset 识别外围层，但结构化 Core 的尖角也会跨过半径边界，导致两侧 onset 都为 0。最终保留 onset 作为诊断，正式门禁使用 Graph 顺序、早期动态差异和晚段残留联合证据。

联系表：`workspace/data/vfx_generation/generated/professional_teacher_explosion_rhythm_r001/rhythm_pair_contact_sheet.png`。

Teacher 已并入 `professional_teacher_verified_r005`，`professional_aesthetic_teacher_readiness_r008` 为 `6/6 ready`。下一阶段将规则迁移到 8 个候选，训练完整节奏窄轴模型，并用新 seed 独立回归。
