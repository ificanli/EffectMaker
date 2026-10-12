# EXP-2026-111 MaterialTrajectory R002 训练数据组装

## 目标

把已经通过 Unity 执行的 MaterialTrajectory R002 从运行证据组装为正式 `training_example.v1` 数据。状态监督、图像监督和人工审美监督必须分开，不能因为 execution pass 就生成审美正标签。

## 输入

- Curriculum：`workspace/data/vfx_generation/curricula/material_trajectory_curriculum_r002`
- Run：`workspace/data/vfx_generation/runs/material_trajectory_r002_full_r001`
- Spec：100
- Result：100
- Material Timeline：100
- PNG：1100
- 人工 R002 审美标签：0

## 实现

- 组装器：`workspace/tools/vfx_generation/material_trajectory_dataset.py`
- Example Schema：`workspace/data/vfx_generation/schemas/material_trajectory_training_example.schema.json`
- Dataset Schema：`workspace/data/vfx_generation/schemas/material_trajectory_training_dataset.schema.json`
- 测试：`workspace/tests/test_material_trajectory_dataset.py`
- 输出：`workspace/data/vfx_generation/datasets/material_trajectory_r002_training_r001`

每条样本保留：

```text
MaterialTrajectorySpec
execution_result
material_timeline
真实 Material / Shader / Texture 选择
parameter tracks / runtime events
expected / actual / raw signals
visual eligibility
negative mutation
resource audit
split group
provenance
```

near-blank 样本保留 11 张 diagnostic frame 路径，但 `render_paths=[]` 且 `image_conditioned=false`，防止图像训练加载器误用。

## 输出统计

- 全部 TrainingExample：100
- Material-state eligible：100
- Image-conditioned eligible：72
- Controlled negative trajectory：15
- Positive trajectory但审美未标注：85
- Aesthetic-preference eligible：0

所有样本：

```text
technical_execution = pass
aesthetic_quality = unlabeled
style_match_decision = unlabeled
rank = null
```

## 无泄漏划分

R002 Shader group 只有 3 个，规模为：

```text
a2d49f234dad = 93
c0ac9ea0cc85 = 6
bf7064ee1fa6 = 1
```

严格保持 Shader 与 Material group 不跨集合后：

| Split | State | Image | Shader groups | Material groups |
|---|---:|---:|---:|---:|
| train | 93 | 67 | 1 | 86 |
| validation | 1 | 0 | 1 | 1 |
| test | 6 | 5 | 1 | 6 |

验证结果：

- Material group overlap：0
- Shader group overlap：0
- Image validation：空

这是数据本身造成的严重失衡，不允许通过随机拆分同 Shader 样本掩盖。图像任务当前只能用于 feature-only 管线检查，不能报告正式 validation 指标。

## 加载边界

`load_material_trajectory_examples` 按任务读取：

- `material_state`：100
- `image_conditioned`：72
- `aesthetic_preference`：直接拒绝，因为没有人工标签

## 结论

R002 已经形成可复现、可验证、可加载的状态训练数据集。它可以支持 Material 状态、轨迹信号和受控负例实验；图像监督仍需补 validation Shader/context；审美排序必须等待真实人工 A/B，不得直接训练。
