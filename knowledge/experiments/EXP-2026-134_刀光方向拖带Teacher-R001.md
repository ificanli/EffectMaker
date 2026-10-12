# EXP-2026-134 刀光方向拖带 Teacher R001

## 专业证据

来源为 `SRC-2026-SERIES-001 / EP003`：刀光和扩散需要明确方向变化，必须真正离开原空间；飞行能量、刀光和爆点应与受力方向同步。时间码为 `01:02:00-01:12:03`、`01:38:09-02:02:00`。

## 受控实验

以 R005 的 `DirectionTrail` 为对象，关闭 OuterBlade 和 InnerSupport。两侧保持材质、贴图、速度、寿命、尺寸、数量、相机和随机种子一致，只改变节点旋转：

- `depth_misaligned`：局部 Z 轴朝镜头运动；
- `attack_aligned`：绕 Y 轴旋转 90 度，将局部 Z 投影到画面 X 攻击轴。

## 结果

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- 错误版水平质心跨度：`0.0101`；
- 正确版水平质心跨度：`0.2817`；
- 水平跨度增益：`0.2716`；
- 正确版水平/纵向运动比：`15.67`；
- Teacher 状态：`verified`。

联系表：`workspace/data/vfx_generation/generated/professional_teacher_slash_direction_r001/slash_direction_pair_contact_sheet.png`。

该规则只证明 DirectionTrail 的屏幕空间运动与攻击轴一致，不评价主刃形状、命中强度或整体刀光质量。下一阶段迁移到 8 个 R005 候选并训练方向模型。
