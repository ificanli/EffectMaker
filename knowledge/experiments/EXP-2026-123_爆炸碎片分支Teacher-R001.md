# EXP-2026-123 爆炸碎片分支 Teacher R001

## 目标与来源

将 EP008 对火鸟/凤凰爆裂的专业判断转为 Unity 可验证 Teacher。来源时间码为 `00:05:53-00:11:14`，明确判断为：爆裂时应增加从核心向外展开的小型分支或碎片，不能只有单一过曝主体。

证据帧位于：

```text
knowledge/sources/SRC-2026-SERIES-001/ep008/visual_check/02_fire_burst/
```

来源仅用于内部学习，不重新分发原始视频。

## 受控变量

实验 `professional_teacher_explosion_debris_r001` 使用同一四层爆炸 Graph，关闭 Shockwave 与 Residual，保留 Core。两侧只修改 Debris 的 `start_color_rgba.alpha`：

- `no_debris`: alpha `0.0`；
- `radial_debris`: alpha `0.95`。

Debris 材质、贴图、数量、速度、寿命、重力、相机、种子和时间点全部保持一致。捕获固定为 `front`、正交尺寸 `3.0`、`640x640`。

## 结果

- Unity 编译：`2/2`；
- 贴图计划回读：`2/2`；
- Prefab API 回读：`2/2`；
- Play Mode：`2/2`；
- 峰值离散组件数：`30`；
- 峰值径向范围：`0.54099`；
- 有效差异帧：`20`；
- 状态：`verified`。

联系表：

```text
workspace/data/vfx_generation/generated/professional_teacher_explosion_debris_r001/debris_pair_contact_sheet.png
```

该结果证明“小型碎片分支存在并离开核心”可以成为窄轴监督，不证明碎片贴图、颜色、密度或完整爆炸构图已经达到最终质量。Teacher 已并入 `professional_teacher_verified_r003`，`professional_aesthetic_teacher_readiness_r006` 为 `4/4 ready`。下一阶段是对 8 个四层候选做同拓扑 Debris-off/on 迁移和成对训练。
