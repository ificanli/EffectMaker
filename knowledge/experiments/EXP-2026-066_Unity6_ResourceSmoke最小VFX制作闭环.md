# EXP-2026-066：Unity 6 ResourceSmoke 最小 VFX 制作闭环

状态：`experimental`

## 工程

- Unity 工程：`E:\UnityVFX\EffectDemo6.0`
- Unity 版本：`6000.5.9f1`
- 渲染管线：URP `17.5.0`
- Pipeline package：`com.unity.pipeline 0.5.0-exp.1`
- Pipeline 端口：`7800`
- 结构验证：`unity projects verify` 通过，errors=0

## 样本资源

样本从 `E:\Unity特效人工智能学习\resource` 选择，复制到：

`Assets/Art/VFX/Samples/ResourceSmokeTest/`

- `Meshes/SM_VFX_Slash_Curve.FBX`
- `Meshes/SM_Torus.FBX`
- `Textures/T_Diciquan_Ground.TGA`
- `Textures/T_Shandian_Electric.TGA`
- `Textures/T_Dissolve_04.png`
- `Textures/T_Spark16A.png`
- `ResourceSmokeTest_manifest.json`

来源清单保留 SHA-256，授权状态均为 `unknown`。原始 `resource` 未修改。

## 已验证

1. Unity 6 已导入 2 个 FBX 和 4 张贴图，并生成 `.meta` 文件。
2. `create_fireworks_particles` 成功幂等创建/复用 5 阶段粒子层。
3. `configure_burst` 成功配置 Burst：duration=1.2 秒，burstCount=32，并保存场景。
4. 已读取 URP 后处理：Bloom active，intensity=0.25，threshold=1；Tonemapping=Neutral；Vignette active，intensity=0.2。
5. 通过官方 Pipeline 创建场景根对象 `VFX_ResourceSmoke` 及 `Core`、`Impact`、`Residue` 三个子层。
6. 三层均已添加 `ParticleSystem` 组件。
7. 已创建 Prefab：`Assets/Art/VFX/Samples/ResourceSmokeTest/Prefabs/VFX_ResourceSmoke.prefab`。
8. 已创建 60 FPS Timeline：`Assets/Art/VFX/Samples/ResourceSmokeTest/Timelines/VFX_ResourceSmoke.playable`。
9. 已添加 Activation 轨道 `VFX Layers`。
10. 最终工程结构验证通过，Pipeline 状态 ready。

## 当前缺口

- 已完成 Play Mode 进入、Scene/Game 两张 1280×720 截图和编辑器状态恢复；截图路径分别为：
  - `E:\UnityVFX\EffectDemo6.0\Temp\pipeline-screenshots\ResourceSmoke_scene.png`
  - `E:\UnityVFX\EffectDemo6.0\Temp\pipeline-screenshots\ResourceSmoke_game.png`
- 自定义 `VfxResourceSmokeCommands.cs` 因导入器文件锁和旧编译缓存未注册，因此未依赖它宣称闭环完成。
- 尚未把导入资源实际绑定到粒子 Renderer 材质；当前 Prefab 已包含三层 ParticleSystem，材质绑定仍需下一轮 Inspector/官方命令验证。
- 尚未完成目标设备性能数据。

## 错误修复记录

首次添加 `VfxResourceSmokeCommands.cs` 后，Unity 编译报：

```text
The type or namespace name 'CliCommandAttribute' could not be found
```

根因是样本脚本使用 `[CliCommand]`，但缺少：

```csharp
using Unity.Pipeline.Commands;
```

补充 using 后执行官方 `recompile`，结果为 `status=up_to_date`、`failed=false`、`errors=[]`。随后 `create_resource_smoke_prefab` 注册并执行成功，返回 `importedMeshes=2`、`importedTextures=2`、`layers=3`。Editor.log 中保留的是修复前的历史错误快照；当前重编译状态和命令执行均无错误。

修复后重新进入 Play Mode，并保存：

- `E:\UnityVFX\EffectDemo6.0\Temp\pipeline-screenshots\ResourceSmoke_scene_fixed.png`：1280×720，165806 bytes。
- `E:\UnityVFX\EffectDemo6.0\Temp\pipeline-screenshots\ResourceSmoke_game_fixed.png`：1280×720，220459 bytes。

## 材质绑定与性能验证补充

- 材质：`Assets/Art/VFX/Samples/ResourceSmokeTest/Materials/M_VFX_ResourceSmoke_Core.mat`
- Shader：`Universal Render Pipeline/Particles/Unlit`
- `_BaseMap`：`T_Dissolve_04.png`
- `_EmissionMap`：`T_Spark16A.png`
- `_BaseColor`：`[0.2, 0.6, 1.0, 0.85]`
- Render Queue：`-1`
- `_ZWrite`：`1`
- `_Blend`：`0`
- `_Cull`：`2`
- `Core`、`Impact`、`Residue` 三层 `ParticleSystemRenderer.m_Materials[0]` 均已绑定该材质，并通过组件属性回读确认。
- 粒子生命周期回读：Core `1.0s`，Impact `0.45s`，Residue `1.8s`。

编辑器环境性能基线（非目标设备承诺）：

- Edit Mode：39 draw calls，34 set-pass，10,407 triangles，CPU frame `0.6207ms`。
- Play Mode：47 draw calls，2 batches，34 set-pass，10,455 triangles，CPU frame `21.1166ms`，GPU frame `0.59904ms`，CPU main thread `4.6016ms`。
- 材质绑定后的 Play Mode 截图：`E:\UnityVFX\EffectDemo6.0\Temp\pipeline-screenshots\ResourceSmoke_materials_game.png`，1280×720。

这些性能数据只代表当前 Editor、当前场景和当前机器，不能直接作为移动端或目标设备预算。

## 当前缺口

- 尚未完成目标设备性能数据。
- 自定义脚本编译问题已修复，但 Unity 日志保留修复前的历史错误文本。
- 全量资源索引仍暂停，后续新增资源走增量扫描。
