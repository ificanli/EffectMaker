# EXP-2026-144 雷电命中 Teacher 与 R004 回归

## 专业证据

来源为 `SRC-2026-SERIES-001 / EP008`，时间码 `00:20:53-00:28:24`。专业结论为：雷电暴点核心应成为局部最亮峰值，主电流和外围分支不能淹没命中核心。

## Teacher

保持 MainBolt、BranchSupport、ImpactFlash 位置、尺寸、贴图、寿命、相机和种子不变，仅修改 ImpactFlash Alpha：

- `weak_impact`：Alpha `0.15`；
- `focused_impact`：Alpha `1.0`。

结果：

- Unity 编译、贴图回读、Prefab API 回读、Play Mode：`2/2`；
- 命中区域平均亮度增益：`0.3825`；
- 顶部亮像素增益：`0.9185`；
- 差异质心到目标距离：`0.0822`；
- Teacher：`verified`。

## 迁移与模型

`layered_lightning_hit_ablation_r001` 的 8 对全部通过技术和专业规则门禁。训练数据为 8 对/16 条，Pair 切分 `4/2/2`、泄漏 `0`。`professional_lightning_hit_rule_ranker_r001` 使用 PyTorch、AdamW 和成对 softplus 损失。

独立 R004：

- 技术通过：`8/8`；
- Hierarchy：`8/8` 分布内；
- ImpactFocus：`7/8` 分布内，1 条保持 OOD；
- Impact Top-1：`layered_lightning_003_pfg_6ae0f44ed1c593504a71`。

模型仅监督 `lightning/impact_focus`，不能评价整体雷电质量。
