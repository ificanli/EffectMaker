# EXP-2026-145 雷电瞬时脉冲 Teacher R001

## 专业证据

来源为 `SRC-2026-SERIES-001 / EP004`，时间码 `00:17:10-00:24:34`。专业点评指出雷电应短促建立峰值并快速退出，不能持续占据画面或以同一亮度拖长。

## 受控实验

关闭 Support、Hit 和 Residual，只保留 MainBolt。材质、贴图、尺寸、Alpha、相机和种子一致，只改变 MainBolt lifetime：

- `slow_pulse`：`0.36s`；
- `instant_pulse`：`0.14s`。

## 结果

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- 早期峰值保留比例：`1.0`；
- 最后可见时间提前：`0.22s`；
- 活跃帧减少：`11`；
- Teacher：`verified`。

下一阶段将该规则迁移到 8 个四层候选，训练 `lightning/instant_pulse` 窄轴模型。该 Teacher 不评价分支、命中、残留或总体审美。
