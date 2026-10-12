# Datasets

本目录保存从 runs 汇总出的训练数据索引和小型样本。训练中间模型、向量缓存、特征矩阵和大体积二进制数据默认不提交。

第一阶段目标数据集：

```text
SlashArc-Pref-001
```

最小样本来源：

- VFX Prompt
- Negative Prompt
- Candidate VFXSpec
- Source manifest / source sample, if the candidate is derived from Unity source files
- Seed
- Render manifest
- Auto evaluation record
- Human feedback

## 偏好数据形态

第一阶段不要只积累单候选分数，优先积累可训练的比较关系：

```text
prompt + candidate_a + candidate_b + winner + reason_tags
```

建议同时保留三类样本：

- `hard_negative`：Unity 错误、不可见、过曝、贴图缺失、无明显帧间变化等自动淘汰项。
- `pairwise_preference`：人工判断 A 优于 B，并记录原因标签。
- `mutation_seed`：人工认为可继续变异的候选，带下一轮修改建议。

不要把“截图好看”直接等同于“实时特效可用”。训练样本必须同时关联工程状态和视觉反馈。

训练优先级：

1. 主体弧硬失败过滤器。
2. 主体弧成对偏好排序器。
3. 主体弧候选提案和局部变异策略。
4. 支撑层、命中层和材质局部模型。

`examples/human_feedback_example.jsonl` 仅用于说明记录格式，不属于真实候选的审美结论，也不能直接作为训练数据。

## 导入 Prefab 集合

大批量源工程导入先通过 `python -m workspace.tools.vfx_training_dataset` 展开为每个 Prefab 一条 `prefab_cases.jsonl` 记录。每条 case 保留该 Prefab 实际引用的材质、Shader、贴图标签和依赖健康度，同时明确它仍是 `needs_render_and_style_annotation`，不能直接混进正向生成监督集。

当全局贴图索引不覆盖该外部工程时，加 `--generate-local-texture-tags --unity-project <project>`。它只为当前 Shared 贴图生成本地 `texture_tags.jsonl`，再按实际文件路径写回本数据集的材质选择记录。

每条 case 同时有两个风格字段：

- `target_style_profile`：未来 VFX Prompt 的风格条件。
- `observed_style_profile`：渲染后人工标注的实际风格。

源依赖缺失、运行时上下文依赖和播放审计异常都写入 `training.blocking_reasons`。这些 case 可用于检索、材质候选选择和风格标注，但在产生真实渲染和人工反馈前，必须排除出正向生成、风格条件监督与偏好训练。

结构化反馈入口 `workspace.tools.vfx_generation.feedback create` 支持 `--target-style-profile`、`--observed-style-profile`、`--style-match` 和重复的 `--style-mismatch-dimension`。风格 profile 使用 `schemas/style_profile.schema.json`，可使 Prompt 风格条件和人工观察结果参与后续监督。

`workspace.tools.vfx_generation.style_profile` 会先把 Prompt 中明确出现的中文或英文风格词转成 `target_style_profile`。未识别的风格保持 `unknown`，不会擅自写成卡通或写实；混合词会保留所有命中关键词并标为 `mixed`。
