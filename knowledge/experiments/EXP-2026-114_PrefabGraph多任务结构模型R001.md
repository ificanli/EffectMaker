# EXP-2026-114：PrefabGraph 多任务结构模型 R001

## 目标

验证真实 Unity API 源 PrefabGraph 能否与既有结构语料合并，并训练一个共享编码器的三任务技术结构模型，为后续 Prompt 条件 Graph 生成提供预训练基础。该实验不训练审美判断，不消费人工 A/B，也不把静态截图当作监督。

## 输入与证据

| 项目 | 内容 |
|---|---|
| Unity 工程 | `UnityDemo/EffectDemo`，Unity `2022.3.16f1c1`，URP `14.0.9` |
| 原始结构数据 | `workspace/data/vfx_generation/datasets/prefab_graph_r001`，259 条 `structure_only` |
| Unity API 源批次 | `workspace/data/vfx_generation/generated/prefab_graph_source_export_r003`，10 条 `reconstructable` |
| 源批次门禁 | 10/10 导出、10/10 新 Prefab 重建、10/10 API 回读，Schema 错误 0、字段差异 0，未读取或实例化来源 Prefab |
| 合并数据集 | `workspace/data/vfx_generation/datasets/prefab_graph_r002` |
| 模型输出 | `workspace/data/vfx_generation/models/prefab_graph_multitask_r001` |
| 训练划分 | train/validation/test=`185/42/42`，269 个 `prefab_group` 互斥 |

## 实现

合并器读取已通过 Schema 的 Graph 和源导出 manifest，重新生成 R003 的结构 Token，并为每个源 Prefab 分配确定性的 `prefab_group`。它拒绝重复 `graph_id`、缺失 Graph、失败源 manifest 和审美任务泄漏。

模型为共享 PyTorch GRU 编码器，包含三个技术任务：

1. `next-token`：预测 PrefabGraph 序列的下一个 Token。
2. `masked component`：将一个 `COMP_*` Token 替换为显式 `<MASK_COMPONENT>`，恢复原组件 Token。训练阶段每个 Prefab 每轮采样一个组件位置，评估阶段覆盖全部组件位置。
3. `structure reconstruction`：编码完整结构序列，再从 `<AE_BOS>` 自回归恢复原序列；训练指标同时记录 teacher-forcing loss、Token Accuracy 和整序列精确匹配率。

训练没有使用 Prefab 名称、来源目录、材质路径、贴图路径、Shader 路径、Prompt、人工审美或偏好标签作为输入 Token。Graph 内仍保留这些资产 provenance，供后续 AssetPlan 路由使用。

## 结果

| 任务 | 测试结果 |
|---|---:|
| next-token Token Accuracy | `0.8193` |
| next-token Cross Entropy | `0.6552` |
| masked component Accuracy | `0.8190` |
| masked component 目标数 | `840` |
| reconstruction Token Accuracy | `0.2100` |
| reconstruction exact match rate | `0` |

模型状态为 `experimental`，因为 next-token 测试交叉熵优于频率基线；该状态不代表视觉质量或完整生成能力。Checkpoint 已用 CPU 成功加载，包含 116 个 Token 和 15 个 state tensors。

## 结论

本阶段完成了“真实源 Graph 合并 -> 防泄漏划分 -> 三任务训练 -> 留出评估 -> checkpoint/Model Card”的技术闭环。结构先验和组件恢复已经可以作为后续 Grammar 解码的排序信号，但序列重建尚不能从编码表示精确恢复 Graph，当前不能宣称已经训练出完整 Prefab 生成模型。

## 已知限制与下一步

- 当前 10 条 Unity API 源样本都来自同一 Trains 资源来源，`source_group` 不能代表跨来源泛化；需要继续导入不同工程和不同特效族。
- 结构 Token 使用材质数量等摘要，不生成 Material、Shader、Texture 或 Mesh 内容；AssetPlan 仍需独立扩展。
- `structure_only` 样本可用于层级和组件任务，但不进入完整参数重建目标。
- 重建精确率为 0，下一步应增加结构自回归训练、长度分桶、序列截断策略和 Grammar 解码测试，再接 Prompt 条件。
- 真实 Unity 编译、运行抓帧、API 回读仍是视觉和工程验收条件；本实验指标不能替代动态画面检查。

## 可复验命令

```powershell
python -m workspace.tools.vfx_generation.prefab_graph_training_dataset_merge `
  --base-root workspace/data/vfx_generation/datasets/prefab_graph_r001 `
  --source-export-root workspace/data/vfx_generation/generated/prefab_graph_source_export_r003 `
  --output-root workspace/data/vfx_generation/datasets/prefab_graph_r002 `
  --dataset-id prefab_graph_r002

python -m workspace.tools.vfx_generation.prefab_graph_multitask_model `
  --dataset-root workspace/data/vfx_generation/datasets/prefab_graph_r002 `
  --output-dir workspace/data/vfx_generation/models/prefab_graph_multitask_r001 `
  --epochs 8 --batch-size 16 --embedding-dim 48 --hidden-dim 96 `
  --learning-rate 0.002 --seed 20260902 --device auto
```
