# EXP-2026-139 完整四层刀光节奏 Teacher R001

## 专业证据

来源为特效Orange公开课 `BV1mjvxBgESJ`：

- `00:01:15-00:01:35`：先设计起势、快速进入/命中、可读窗口和收尾；
- `00:10:50-00:14:04`：高光快入慢出，利用峰值落差建立打击感；
- `01:00:13-01:01:24`：关键瞬间先可读，再逐步消失。

动态核对证据：`knowledge/sources/SRC-2026-UP389578709/frames/BV1mjvxBgESJ/60-70/60-48_to_61-04_contact_sheet.jpg`。

## 受控实验

同一四层刀光只改变 Support、Hit、Residual 的启动延迟：

- `simultaneous_layers`：四层都在 `0s` 起播；
- `staged_layers`：Core `0s`、Support `0.01s`、Hit `0.065s`、Residual `0.18s`。

Mesh、材质、贴图、粒子数量、速度、寿命、颜色、相机和随机种子保持一致。

## 结果

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- Graph 顺序满足 `Core < Support < Hit < Residual`；
- 早期可见叠加减少 `0.00137`；
- 命中窗口端点峰值亮度 `0.9937`；
- 晚段活跃比例增加 `0.3846`；
- 最后可见时间增加 `0.1355s`；
- Teacher 状态：`verified`。

联系表：`workspace/data/vfx_generation/generated/professional_teacher_slash_rhythm_r001/slash_rhythm_pair_contact_sheet.png`。

该规则只监督四层刀光的相对时序，不代表颜色、材质或总体审美达到最终质量。
