# EXP-2026-010：Orange 刀光课程复现与视觉门禁记录

## 实验状态

- 状态：`experimental`
- 当前决定：暂停制作，等待重新设计 AI 制作特效的方法后再继续。
- 暂停原因：工程链路可以生成和运行，但当前会话没有形成可靠的人工视觉确认，不能证明最终画面是课程刀光。
- 跟踪任务：`vfx-8su`，保持 `IN_PROGRESS`，不关闭。

## 两小时教程证据审计结论

本实验的课程方法论记录已由 `EXP-2026-104_两小时刀光教程复现证据审计.md` 复核。当前课程字幕和视觉复核能够支持节奏、明暗、颜色职责、主体/支撑/亮层/快速打击层的职责关系，但不能支持总层数、对象数量、完整 ParticleSystem Inspector 参数、Shader 名称、材质名称或纹理文件名。

因此，`SlashBody`、`SlashMotion`、`DarkSupport`、`Highlight`、`HitPoint` 只能作为本地工程的失败实现/工程映射，不能宣称为教程真实结构。`0.4` Lifetime、`5` Size 以及 ASR 中的 `0.3`、`0.6` 等数值保持 tentative 或 unknown，不进入正式参数表。下一步必须回到两小时视频，补齐 `70:00–90:00` 和 Inspector/Hierarchy/材质画面证据；证据不足前不继续改 Unity 参数。


复现课程 `BV1mjvxBgESJ：刀光特效制作的底层逻辑（公开课）` 的最终刀光状态，并把课程方法沉淀为更快、更可复现的制作流程。课程证据覆盖：

- 00:00–20:00：主体快速接近/命中，残留慢退，打击节奏优先。
- 20:00–40:00：颜色分工、平面/模型粗轮廓、Mesh 发射器、Local 空间、尺寸和旋转。
- 40:00–60:00：主体、暗层、亮层、多功能贴图、Mask、UV 方向、尾部溶解。
- 60:00–90:00：主体先可读，暗层慢跟，亮层局部，快速打击层接近命中时出现，避免过快拉丝。
- 90:00–128:01：命中点、点光、地面反馈和残留。

## 本轮采用的制作路径

1. 先从课程记录提取最终方法，不再制作 A/B/C/D 对照组。
2. 只制作一个正式目标：`OrangeSlash_Final`。
3. 使用资源库中的真实刀光源模型，而不是从空白猜 ribbon 形体。
4. 主体采用真实 FBX Mesh；同时设置 Mesh ParticleSystem 作为课程式 Mesh 发射运动层。
5. 再加入暗层、亮层和 HitPoint 层。
6. 按视觉门禁验证：纯色/几何可见 → 相机取景 → 爆发窗口 → 连续帧运动 → 材质和分层。

## 实际产物

主工程：`E:/UnityVFX/EffectDemo6.0`

- 生成器：`Assets/Editor/VfxOrangeSlashCommands.cs`
- 正式 Prefab：`Assets/Art/VFX/Orange/Slash/Prefabs/OrangeSlash_Final.prefab`
- Timeline：`Assets/Art/VFX/Orange/Slash/Timelines/OrangeSlash_Final.playable`
- 源目录：`Assets/Art/VFX/Orange/Slash/Source/`
- 源模型：`SM_VFX_Slash_Curve.FBX`
- 源贴图：`刀光.png`、`Eff_Spark_16.tga`
- 运行证据目录：`Assets/Art/VFX/Orange/Slash/Evidence/`

源模型来自：

`E:/Unity特效人工智能学习/resource/特效模型/600特效模型/UE4特效模型FBX/刀光/SM_VFX_Slash_Curve.FBX`

SHA-256：`42fa5e1099f8d31e5966f68d56f1f3501754b2d3b66fc34619cca2133a7dfc97`

## 已验证事实

### 工程和资源链路

- Unity：`6000.5.9f1`
- URP：`17.5.0`
- `recompile_status`：`failed=false`
- `projects verify`：`errors=0`、`warnings=0`
- 正式源模型已从 `ResourceSmokeTest` 移出，改为 Orange 自己的 `Source` 目录。
- Prefab YAML 中存在有效 Mesh GUID 和 Material GUID。
- 最新层级已确认：
  - `SlashBody`
  - `SlashMotion`
  - `DarkSupport`
  - `Highlight`
  - `HitPoint`
- 旧场景实例曾导致回读结果失真，后续已执行删除旧实例、重新实例化最新 Prefab。

### 相机取景

- Main Camera 原位置：`(0, 0, -5)`。
- 相机原旋转为单位旋转，朝向正确，不是完全反向。
- 原正交尺寸：`3`。
- 主体 FBX 包围盒约为 `1.919 × 1.682 × 0.645`。
- 早期画面差异区域约为 `102 × 89` 像素，说明主体在画面中心但占屏过小。
- 已将场景相机正交尺寸调整为 `1.15` 并保存。
- 这项调整确认了“相机取景过远”是问题之一，但没有单独解决空/不可判读画面。

### 动态截图结果

曾生成：

- `OrangeSlash_Final_Start.png`
- `OrangeSlash_Final_Peak.png`
- `OrangeSlash_Final_End.png`
- `OrangeSlash_Final_MaterialCheck.png`
- `OrangeSlash_CameraFix.png`

结果：

- 初次 Start/Peak/End 三帧像素差异为空，不能证明粒子播放。
- 后续 MaterialCheck 曾出现像素范围变化，但没有可靠人工视觉读取，不能证明刀光轮廓。
- 相机调整后的 `OrangeSlash_CameraFix.png` 与旧空帧比较仍出现无差异，说明相机不是唯一问题。
- Unity PNG 文件存在、可解码、尺寸正确，均不等于视觉门禁通过。

## 已确认的失败和弯路

1. **把 ResourceSmokeTest 当正式刀光来源**
   - 试过：从 `Assets/Art/VFX/Samples/ResourceSmokeTest/Meshes/` 读取模型。
   - 为什么不行：ResourceSmoke 是导入/资源闭环样本，不是课程刀光资产，违反正式源和验证样本边界。
   - 改成：从资源库检索真实刀光 FBX，复制到 Orange `Source` 目录。
   - 结果：源资产链路已纠正。

2. **从空白手工猜 ribbon 形体并做 A/B/C/D**
   - 试过：程序化 ribbon、四变体对照、静态 MeshRenderer。
   - 为什么不行：没有复现课程最终状态，且用户只需要一个好看的最终效果。
   - 改成：课程最终状态优先，单一 `OrangeSlash_Final`。
   - 结果：旧变体路径已清理，但视觉目标仍未达成。

3. **把 Prefab、层级、PNG 文件和像素变化当成视觉完成**
   - 试过：仅依赖结构回读和像素统计判断效果。
   - 为什么不行：这些信号不能说明画面是一眼可辨识的刀光。
   - 改成：必须人工看连续画面，检查轮廓、方向、占屏、起势、命中和收束。
   - 结果：视觉门禁保持失败，实验没有升级。

4. **截图时序错误**
   - 试过：固定等待约 2 秒后截图。
   - 为什么不行：主体生命周期小于截图等待时间，拍到空帧。
   - 改成：在约 `0.15–0.35s` 爆发窗口采集，并确认 Play Mode 状态。
   - 结果：工具链可以保存帧，但仍未完成可靠人工视觉确认。

5. **场景实例未随 Prefab 自动更新**
   - 试过：生成新 Prefab 后直接读取场景实例。
   - 为什么不行：旧实例仍然存在，回读的不是最新产物。
   - 改成：删除旧实例，再实例化最新 Prefab。
   - 结果：层级更新为 `SlashBody + SlashMotion + ...`。

6. **Material 持久化和回读不一致**
   - 试过：直接把内存 Material 绑定到对象后保存 Prefab。
   - 为什么不行：重载后引用不稳定；组件接口曾返回 null，而 Prefab YAML 后来出现有效 GUID。
   - 改成：创建 `.mat` 后保存并从资产路径重新加载，再绑定 Renderer。
   - 结果：Prefab YAML 有有效 GUID，但场景组件回读仍存在接口不一致，需后续单独诊断。

7. **相机取景过远**
   - 试过：正交尺寸为 `3`。
   - 为什么不行：主体只占画面很小区域。
   - 改成：正交尺寸调整为 `1.15`。
   - 结果：调整已保存，但后续 Play Mode 帧仍未形成可确认的刀光画面。

8. **浏览器图像查看失败**
   - 试过：通过本地 HTTP 服务和浏览器查看 Unity PNG。
   - 为什么不行：浏览器返回 `guest not attached (webview not ready)`。
   - 改成：不把浏览器失败降级为视觉结论；保留 PNG、Pillow 和 Unity 状态作为客观诊断。
   - 结果：本轮没有可靠人工图像判断。

## 最终结果

本轮没有做出可由人工确认的课程刀光。

已经完成的是：

- 课程资料和方法学提炼。
- 真实刀光源资产检索和导入。
- 单一正式 Prefab 生成。
- Unity 编译和资源校验。
- 场景实例替换。
- 相机取景初步修正。
- 失败原因和工具链问题记录。

没有完成的是：

- 目标相机中清晰可辨的刀光轮廓。
- 起势、命中、收束的连续可解释运动。
- 课程最终帧的人工对照。
- 命中反馈、地面反馈和完整多层材质的视觉确认。
- 将实验升级为 `verified`。

## 暂停后的建议

恢复制作前，先重新设计 AI 特效制作闭环，不要直接继续调当前参数。优先解决：

1. AI 如何获得可靠的画面输入，而不是只获得 PNG 文件路径和像素统计。
2. 如何建立一个可控的“相机、主体、背景、材质、时序”最小验证场景。
3. 如何把课程最终帧和 Unity 输出帧绑定到同一时间点进行人工比较。
4. 如何在第一步就验证纯色主体轮廓，再进入材质和层级。
5. 如何让 AI 直接读取课程最终参数/状态，减少从空白猜参数。
6. 如何把失败自动分类为：相机不可见、资源未绑定、材质透明、粒子未播放、时序错误或视觉形体错误。

在这些方法重新确定前，不继续 Orange 刀光制作。
