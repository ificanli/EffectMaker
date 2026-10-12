# EXP-2026-137 刀光 Residual 收尾 Teacher R001

## 专业证据

来源为特效Orange公开课 `BV1mjvxBgESJ`。`01:00:13-01:01:24` 强调刀光应先保证关键瞬间可读，随后慢慢消失；从出现到消失都保持同一速度、或过强流动形成拉丝，都会削弱收尾。

本次从原视频 `01:00:48-01:01:04` 以 2 fps 重新抽取 32 帧联系表，并实际核对生命周期变化：

`knowledge/sources/SRC-2026-UP389578709/frames/BV1mjvxBgESJ/60-70/60-48_to_61-04_contact_sheet.jpg`

## 受控实验

以四层刀光的 DirectionTrail/Residual 为对象，保持 Core、Support、Hit、材质、贴图、颜色、速度、尺寸、相机和随机种子一致，只改变 Residual 时序：

- `premature_residual`：delay `0.0s`，lifetime `0.12s`；
- `staged_residual`：delay `0.18s`，lifetime `0.30s`。

固定捕获协议为 Unity `2022.3.16f1c1`、URP `14.0.9`、Play Mode、正面相机、正交尺寸 `1.4`、`640x640`。

## 结果

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- 正确版 Residual 比非残留层结束时间晚 `0.12s`；
- 晚段活跃比例增加 `0.3333`；
- 晚段平均可见面积增加 `0.0003949`；
- 最后可见时间增加 `0.4452s`；
- Teacher 状态：`verified`。

联系表：`workspace/data/vfx_generation/generated/professional_teacher_slash_residual_r001/slash_residual_pair_contact_sheet.png`。

该规则只监督 `slash/readable_then_fade`，不评价刀光形状、Hit 位置、材质风格或总体审美。
