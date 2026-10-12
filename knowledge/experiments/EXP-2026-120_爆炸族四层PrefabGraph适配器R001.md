# EXP-2026-120：爆炸族四层 PrefabGraph 适配器 R001

## 目标

将通用三层粒子候选升级为爆炸族专用拓扑，不再用同一软团/闪光贴图换色代替职责分层。

## 四层结构

| 层 | 职责 | 资产 | 时间 |
|---|---|---|---|
| `CoreFlash` | 白亮核心体积 | `MFX_Flare_4.mat + FX_Glow_1.TGA` | `0s` 起势，短寿命 |
| `ShockwaveRing` | 从中心外扩的冲击环 | `Mat_pomoarrow_ring.mat + ring_1.png` | `0.04-0.06s` 延迟，尺寸扩大 |
| `DebrisBurst` | 快速散射的命中碎片 | `sparkle_ADD2.mat + dian.png` | `0.07-0.08s` 延迟，高速+重力 |
| `ResidualSmoke` | 峰值后的烟雾残留 | `Mat_zombie_boss_smoke1.mat + smoke1.png` | `0.20-0.275s` 延迟，长寿命 |

PrefabGraph/Unity 契约新增 `start_delay_max`、`start_rotation_max`和 `gravity_modifier_max`，编译器、源导出器和 API 回读器同步支持。

## 运行结果

`layered_explosion_family_r003` 产生 8 个无 parent 候选：

- VFXSpec/PrefabGraph：8/8 生成。
- Unity 2022 编译：8/8 pass。
- 计划贴图与保存后材质回读：8/8 match。
- Prefab API 回读：8/8 pass。
- Play Mode：8/8 pass，每个 51 帧，错误洋红 0。
- 帧联系表：`workspace/data/vfx_generation/generated/layered_explosion_family_r003/top4_early_timeline_contact_sheet.png`。

## 模型边界

`professional_core_rule_ranker_r002` 对原 Teacher 引导批次有 7/8 条在训练分布内，但对新四层爆炸是 0/8。因此 `core_rule_model_ranking_r002.json` 正确输出 `blocked_out_of_distribution`，不允许用其分数宣称四层候选的审美排名。

后续 `layered_explosion_family_r004` 替换了过弱的外围层材质，再由 `layered_explosion_core_ablation_r003` 生成 8 对同拓扑 Core-off/Core-on 对照。8/8 对的外围层在 Core-off 时仍可见，且开启 Core 后中心亮度/局部对比度增益均超过门槛。`professional_core_rule_ranker_layered_r001` 按 4/2/2 对分组训练，train/validation/test pair accuracy 均为 1.0。

独立新种子批次 `layered_explosion_family_r005` 再次完成 8/8 编译、贴图回读、Prefab API 回读和 Play Mode；四层专用 Ranker 判定 8/8 在训练分布内并完成排名，Top-1 为 `layered_explosion_004_pfg_c659b1e50c02756e4c0f`。这是核心轴的独立 seed 推理，仍不是整体审美通过。

R005 的 8 个 Prefab、生成材质和 `.meta` 已从 staging 原样转入权威工程 `UnityDemo/EffectDemo/Assets/Generated/LayeredExplosionFamilyR005/`；共96个文件，抽查12个 Prefab/Material/meta 哈希一致。

当前画面已有清晰白亮核心和元素时序差，但冲击环、碎片和残留的形体/材质仍是 AI 假设，不是专业审美通过。下一步为这 8 个四层候选生成 Core-off 消融对，扩充同拓扑训练分布；其他三层分别等待专业 Teacher 复刻。

## 产物

- 生成器：`workspace/tools/vfx_generation/explosion_family_generator.py`
- 最新独立批次：`workspace/data/vfx_generation/generated/layered_explosion_family_r005/`
- 同拓扑消融：`workspace/data/vfx_generation/generated/layered_explosion_core_ablation_r003/`
- 四层训练视图：`workspace/data/vfx_generation/datasets/professional_core_rule_training_layered_r001/`
- 四层窄轴模型：`workspace/data/vfx_generation/models/professional_core_rule_ranker_layered_r001/`
- 错误记录：`ERR-UNITY-067`
