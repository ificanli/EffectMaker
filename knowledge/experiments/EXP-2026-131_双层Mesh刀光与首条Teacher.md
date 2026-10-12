# EXP-2026-131 双层 Mesh 刀光与首条 Teacher

## 目标

把旧的 Slash VFXSpec 随机提案升级为可由 Unity 2022 编译、回读和运行的真实双层 PrefabGraph，并验证专业规则“外侧主刃更亮更长，内侧辅助层更短更弱”。

## 资产与编译器

- Mesh：`Assets/Hovl Studio/Sword slash VFX/Models/Slash4.fbx`；
- Texture：`Assets/Hovl Studio/Toon Projectiles 2/Textures/Trail68.png`；
- Material：QFX 已验证粒子材质；
- Shader：编译结果回读的 QFX 粒子 Shader；
- 结构：`OuterBlade/core + InnerSupport/support`。

PrefabGraph 编译器新增 Mesh ParticleSystemRenderer 绑定，并使用 `LoadAssetAtPath<Mesh>` 或 FBX 子资源中的首个 Mesh；API 回读新增 Mesh 路径一致性检查。

R001 首次因 `shape_enabled=false` 仍写 `shape_type=Sphere` 导致字段 mismatch。R002 改为 `shape_type=disabled` 后 8/8 Mesh/API 回读通过，但 Hovl `SwordSlash.mat` 依赖原 Prefab 的自定义 Particle vertex streams，Play Mode 全部 near-blank。R003 保留真实 `Slash4.fbx`，换成 QFX 材质并显式绑定 `Trail68.png` 后：

- Unity 编译：`8/8`；
- Mesh 路径回读：`8/8`；
- Prefab API 回读：`8/8`；
- Play Mode 可见：`8/8`。

## 专业 Teacher

来源：`SRC-2026-001`，时间码 `00:31:12.540-00:32:06.400`。规则只改变 InnerSupport 的尺寸和 Alpha：

- 错误版：内外同尺寸、同 Alpha；
- 正确版：外层尺寸至少为内层 1.2 倍，外层 Alpha 至少为内层 2 倍。

结果：主刃可见宽度保留 100%，全长高亮跨度减少 0.575，所有 Unity 和层级门禁通过，`professional_slash_outer_inner_hierarchy_r001` 状态为 `verified`。

下一阶段把该规则迁移到 8 个 R003 候选并训练刀光层级模型，然后增加方向拖带、命中和残留层。
