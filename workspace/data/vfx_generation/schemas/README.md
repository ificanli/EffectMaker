# Schemas

本目录定义 AI 式特效生成闭环的核心数据契约。

- `vfxspec.schema.json`：候选特效规格，描述 prompt、生成器、层职责、参数空间和参考帧。
- `adapters/`：特效族专用契约，当前包含 `slash.adapter`、`fire.adapter`、`lightning.adapter`、`shield.adapter`、`magic_circle.adapter`。
- `auto_eval.schema.json`：自动硬过滤评价，描述工程错误、可见性、亮度、帧间变化和排序辅助分。
- `human_feedback.schema.json`：人工候选反馈，描述选择、拒绝、保留部件和下一轮变异建议。
- `training_example.schema.json`：从 spec、渲染、反馈和材质选择摘要汇总出的训练样本。
- `run_manifest.schema.json`：候选 run 的批量渲染、contact sheet、verify 和 Console 汇总。
- `source_manifest.schema.json`：Unity 特效源文件包登记，描述文件列表、GUID/meta、依赖、授权、Unity 上下文和后续链接。
- `source_sample.schema.json`：源文件抽取结果，描述可用于反推 VFXSpec 的层级、材质选择摘要、时间、证据和训练 readiness。
- `prefab_graph.schema.json`：版本化的 PrefabGraph 中间表示，绑定层级节点、ParticleSystem、Renderer、动画和资产路径，并显式区分 `structure_only` 与 `reconstructable`。
- `prefab_graph_training_dataset.schema.json`：PrefabGraph 规范化和 Token 数据集 manifest；该数据集只消费技术结构证据，不使用审美偏好标签。
- `aesthetic_record.schema.json`：统一审美记录，区分 `reference`、`observation`、`human_label`、`technical_exclusion` 和 `preference_pair`，固定来源、可见性、风格、质量、层职责、问题与训练资格字段。
- `aesthetic_dataset_manifest.schema.json`：审美资料标准化数据集 manifest，记录记录类型、Judge/偏好资格、技术排除和训练政策统计。
- `aesthetic_record.schema.json` 的标准化导出入口为 `workspace/tools/vfx_generation/aesthetic_record_exporter.py`；导出器将资料文本保留为 observation，将完整可见人工反馈转为 human_label，将技术/不可见记录转为 technical_exclusion。
- `aesthetic_training_dataset.schema.json`：Judge/偏好训练集组装 manifest，记录特征匹配、分组切分、训练资格、排除原因和数据门禁。
- `aesthetic_training_dataset.py`：将统一审美记录与候选特征组装为 Judge/偏好训练 JSONL；没有特征向量的人工标签只保留为待补/排除，不会静默进入训练。
- `aesthetic_judge.py`：多任务 Judge 轻量基线，分别检查和预测综合质量、五个通用审美维度与风格类别；标签不足时只写预检，不写模型权重。
- `vfx_controller_aesthetic_guidance.schema.json`：Controller 审美指导契约，固定 Judge/偏好/人工反馈证据、变异目标、保留项、理由和 approval 门禁。
- `vfx_aesthetic_promotion_report.schema.json`：跨特效族/风格模型晋级审计，记录覆盖、泄漏、模型卡、回归集和阻塞原因。
- `aesthetic_preference_review_batch.schema.json`：同 Prompt/同族 A/B 人工偏好批次，技术通过候选进入待评价，偏好结论必须人工填写。
- A/B 批次的运行入口为 `workspace/tools/vfx_generation/aesthetic_preference_review_server.py`；最终化后生成统一 `aesthetic_record` 偏好记录。
- `examples/adapter_examples.json`：第一批特效族 adapter 示例，覆盖 slash、fire、lightning、shield、magic_circle。

第一阶段只要求字段稳定、可追溯、便于验证；不要在 schema 中写入某个历史版本的固定参数。
