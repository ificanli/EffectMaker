# EXP-2026-138 刀光 Residual 模型与 R013 独立回归

## 批量迁移

`layered_slash_residual_ablation_r001` 使用 R012 四层刀光构造 8 对 premature/staged 同拓扑样本，只修改 Residual 的启动延迟和寿命。

- Pair：`8`；
- 记录：`16`；
- 技术通过：`8/8`；
- 专业规则迁移：`8/8`；
- Pair 切分：train / validation / test = `4 / 2 / 2`；
- 跨 split Pair 泄漏：`0`。

## 模型

`professional_slash_residual_rule_ranker_r001` 使用 PyTorch MLP、AdamW、300 epochs 和成对 softplus 损失。输入包含 Residual delay/lifetime、相对主体结束时间、晚段活跃比例、晚段可见面积和最后可见时间。

训练、验证、测试 Pair Accuracy 均为 `1.0`，测试集只有 2 对，状态保持 `pilot_narrow_axis_not_general_quality`。

## 独立 R013

R013 使用新的 Prompt 和 seed `20262368-20262375`：

- Unity 编译、Prefab API 回读、固定 Residual 协议 Play Mode：`8/8`；
- Residual 模型分布内：`8/8`；
- Top-1：`layered_slash_003_pfg_f2702bfdb876f6e64302`。

该结果只证明刀光收尾节奏进入已验证局部分布。下一步比较完整四层 simultaneous/staged 节奏，并验证所有窄轴联合工作。
