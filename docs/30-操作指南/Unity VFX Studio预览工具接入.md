# VFX Studio 预览工具接入

项目引入了 `unity-vfx-studio` 的核心预览能力，位置为：

- `Assets/Editor/VfxPreview/VfxPreviewRenderer.cs`

## 用法

在 Unity 菜单执行：

`Tools > VFX Preview > Render Current Camera`

工具会把 `Camera.main` 的当前编辑器画面保存到：

`Assets/Art/VFX/Orange/Slash/Evidence/OrangeSlash_EditorPreview.png`

脚本也提供 `BatchRenderCurrentCamera()`，可由 Unity batchmode 的 `-executeMethod` 调用。

## 边界

该工具用于编辑器当前相机的静态 PNG 预览，适合检查相机、材质、模型和静态构图。它不替代动态 VFX 验证：粒子播放、生命周期、命中窗口和连续时间点仍必须使用 Unity CLI 的 Play Mode 与 `capture_game_view` 流程验证。
