# Source Ingestion Rules

## 目标

源文件摄入的目标是把 Unity 特效资产转换为可复盘、可比较、可训练的结构化证据，而不是把原始工程文件堆进训练目录。

## 摄入顺序

1. 登记来源：建立 `source_manifest.json`，写明来源、路径、Unity 版本、渲染管线、授权状态和 Beads id。
2. 扫描依赖：从 Prefab、Scene、Material、Shader、Texture、Mesh、Animation 和 `.meta` 中抽取 GUID 与引用关系。
3. 抽取参数：只保留训练有用的摘要，例如粒子数量、时间、颜色、材质选择摘要、贴图槽、Shader 参数、Texture tag、Shape/Velocity/Emission/Renderer 配置。
4. 反推规格：生成 `derived_vfxspec.json`，把源文件结构映射到 Prompt、层职责、adapter 和生成参数。
5. 关联渲染：把源文件样本连接到 run manifest、截图时间点和 contact sheet。
6. 关联反馈：记录人工接受、拒绝、失败原因和下一轮变异建议。
7. 形成训练样本：生成或引用 `training_example.json`。

## 文件处理规则

- `.meta` 与 Unity 资产同等重要，必须登记。
- 大体积原始资源默认放本地，只提交 manifest 和索引。
- 贴图、模型、视频、EXR、AssetBundle 等默认 `local_reference_only`，除非明确确认授权。
- Shader 和 HLSL 可提交摘要；全文是否提交取决于来源授权和工程归属。
- 缺失依赖必须保留为 `missing`，不能静默删除。
- 若未显式提供纹理标签索引，摄入流程应优先为当前样本生成本地 `texture_tags.jsonl`，再把该索引路径与记录数写回 `source_sample`、`derived_vfxspec` 和 `training_example`。

## 训练规则

源文件样本只有在同时具备以下信息时，才可以标记为 `trainable_internal` 或 `trainable_public`：

- 授权允许训练。
- 渲染结果可复现或已记录不可复现原因。
- 人工反馈存在。
- VFXSpec 与源文件参数能互相追溯。
- 材质选择摘要至少要能区分 shader 候选、texture 候选和 slot role，并且能把贴图标签或标签索引证据带进样本。
- 失败样本记录了失败原因，而不是只记录低分。

## 失败样本同样保留

失败源文件对训练很有价值。保留内容应包括：

- 哪个层级失败。
- 失败是形体、材质、节奏、空间、后处理、性能还是授权问题。
- 是否可以局部复用。
- 下一轮应如何变异。

## 输出命名

建议命名：

```text
source_id: SRC-VFX-<FAMILY>-<NNN>
sample_id: sample_<family>_source_<NNN>
render_run_id: <family>_source_ingest_r<NNN>
candidate_id: <family>_source_candidate_<NNN>
```
