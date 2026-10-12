# AESTHETIC-2026-057：VFX.library 关键词候选低证据参考

## 来源与证据

- 来源：`SRC-2026-VFXLIB-001`
- 清单：`workspace/data/resource_index/vfx_library/manifest.jsonl`
- 候选聚类：`workspace/data/resource_index/vfx_library/clusters/clusters.json`
- 逐媒体联系：`workspace/data/resource_index/vfx_library/clusters/assignments.jsonl`
- 联系表：`workspace/data/resource_index/vfx_library/clusters/clusters.md`
- 代表帧入口：`workspace/data/resource_index/vfx_library/clusters/representatives/`
- 状态：`experimental`
- 证据等级：低；当前只验证了文件名关键词、媒体元数据和文件哈希，未完成稳定的人工逐帧复核。

## 可确认内容

本库可按文件名关键词建立初步检索入口，当前形成 13 个候选主题：`fire`、`water`、`explosion`、`ice`、`lightning`、`energy`、`slash`、`blood`、`smoke`、`portal`、`shield`、`trail` 和 `unclassified`。其中 `unclassified` 有 2,406 条，是最大类别，说明文件名不足以支持主题判断。

这些素材只作为参考、灵感和反例来源，不代表制作质量、审美标准、风格目标或正确实现。即使某个效果完成度较低，也可以用于分析其形体、层级、节奏、颜色、空间或失败原因；分析不应把素材本身当作应当追随的标准。

这些主题只适合作为后续观看和抽帧的检索入口，不能证明画面中确实出现对应元素，也不能证明任何 Shader、粒子、材质、网格或时序实现。

## 复用方式

1. 先在 `assignments.jsonl` 按主题筛选，再按 `sha256` 去重。
2. 通过 `relative_path` 回到外部原始媒体，结合 `evidence_manifest.jsonl` 选择起始、中段和结束证据点。
3. 人工确认连续画面后，分别记录主体形体、层级、节奏、颜色、空间承接和镜头展示；未确认项保持假设状态。
4. 不要将文件名关键词直接复制为效果设计结论，也不要把展示视频当作制作教程。

## 复用边界

本卡不新增稳定审美规范，不支持直接设置 Unity 参数，也不支持生成可分发资产。只有在代表帧和连续时间证据可复核、且观察能跨多个独立样本重复出现时，才应拆出更具体的 `AESTHETIC-*` 卡片并设计 `EXP-*` 验证。
