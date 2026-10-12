# EXP-2026-135 刀光命中接触点 Teacher R001

## 专业证据

来源为 `SRC-2026-001`，作者页面说明为网易资深特效师。`00:33:12.540-00:34:09.000` 与 `00:36:15.900-00:37:45.450` 的点评明确指出：刀光命中反馈应集中在真实接触点或受力端，并成为局部视觉重点；空中拖尾只能作为次级信息。

画面证据：

- `knowledge/sources/SRC-2026-001/visual_review_22-44/2007_ground_hit.jpg`
- `knowledge/sources/SRC-2026-001/visual_review_22-44/contact_11_33-34.jpg`
- `knowledge/sources/SRC-2026-001/visual_review_22-44/2176_floating_blade.jpg`
- `knowledge/sources/SRC-2026-001/visual_review_22-44/contact_14_36-37.jpg`

## 受控实验

在四层刀光 Graph 中保留相同的 OuterBlade、InnerSupport、Hit 材质、`FX_Hit_1.png`、尺寸、时序、颜色、相机和随机种子，并关闭 DirectionTrail。两侧只改变 Hit 节点位置：

- `center_misplaced`：Hit 位于刀光中心；
- `contact_aligned`：Hit 位于攻击前端 `local_position=[1.45,-0.05,0]`。

固定捕获协议为 Unity `2022.3.16f1c1`、URP `14.0.9`、Play Mode、正面相机、正交尺寸 `2.0`、`640x640`。

## 弯路

1. R001 将 `+X` 错判为尾端，随后实际连续帧证明首个小亮点判读不可靠。
2. R002 改到 `-X` 后，成对差异质心稳定落在画面 `x=0.209`，明确证明该方向才是尾端。
3. 首版使用半径 `0.1` 的区域平均亮度衡量稀疏闪点，信号被大量背景像素稀释。R003 改为小区域均值与顶部 5% 亮像素均值并行，但没有放宽位置误差门禁。

## 结果

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- 有效差异帧：`7`；
- 接触区最大平均亮度增益：`0.0949`；
- 接触区顶部亮像素增益：`0.1243`；
- 正向差异质心到目标位置距离：`0.0179`；
- 材质错误：`0`；
- Teacher 状态：`verified`。

联系表：`workspace/data/vfx_generation/generated/professional_teacher_slash_hit_r003/slash_hit_pair_contact_sheet.png`。

该规则只证明 Hit 应位于攻击接触端并形成局部亮点，不判断刀光整体轮廓、方向拖带、残留节奏或总体审美。
