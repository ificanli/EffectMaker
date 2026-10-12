# EXP-2026-147 雷电余电收尾 Teacher R001

## 专业证据

来源为 `SRC-2026-SERIES-001 / EP008`，时间码 `00:20:53-00:28:24`。专业点评要求雷电命中后保留短时地面残流或传送痕迹，避免峰值后亮暗瞬间跳变。

## 受控实验

两版保持 MainBolt、BranchSupport、ImpactFlash、Residual 参数、材质、贴图、时序、相机和种子一致，只改变 ResidualSpark Alpha：

- `abrupt_no_residual`：Alpha `0`；
- `staged_residual`：保留余电。

第一轮使用约 `0.24s` Residual lifetime，晚段活跃比例增益只有 `0.133`，低于 `0.15` 门槛。没有降低阈值，而是将两版共同 lifetime 延长到 `0.30s` 后重跑。

## 结果

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- 早期最大 MAE：`0.00121`；
- 晚段活跃比例增益：`0.2667`；
- 晚段可见面积增益：`0.0005277`；
- 最后可见时间增益：`0.28s`；
- Teacher：`verified`。

下一步需要完成 8 对迁移、窄轴训练和独立回归；当前不能把单对 Teacher 当成完整雷电收尾模型。
