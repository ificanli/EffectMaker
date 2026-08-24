# EXP-2026-012：特效Orange法阵对比、体量与单元素流动验证

## 目的

验证法阵高级感是否来自节奏段落取舍、内外体量对比、单元素独立流动和环绕气浪方向，而非单纯提亮或增加元素。

## 对照组

- `OrangeCircle_Dense`：第一段保留密集包裹气浪。
- `OrangeCircle_Spaced`：减少第一段气浪，为第二段留空间。
- `OrangeCircle_GlobalMotion`：整个法阵统一抖动/流动。
- `OrangeCircle_LocalMotion`：仅单元素独立流动。
- `OrangeCircle_RingWave`：随意气浪 / 环绕式气浪。
- `OrangeCircle_Contrast`：低对比整体提亮 / 内外体量和明暗对比。

## 固定变量

动作、摄像机、背景、播放时长、分辨率、Unity 版本、渲染管线和目标平台固定，每次只改变一个变量。

## 观察指标

- 前段与后段的节奏层次和展示空间。
- 法阵中心、内圈、外圈和气浪的主次关系。
- 单元素流动是否增加细节而不破坏整体稳定。
- 环绕气浪是否强化冲击方向。
- 高亮、暗场和高密度纹理是否形成可读对比。
- Draw Call、透明过绘、材质数量和帧时间。

## 通过标准

1. `Spaced` 比 `Dense` 更能突出第二段强化效果。
2. `LocalMotion` 比 `GlobalMotion` 更有局部细节且不造成整体抖动。
3. `RingWave` 比随意气浪更能传达环绕和打击方向。
4. `Contrast` 在撤除暗场/整体提亮后仍保留结构和焦点。

## 当前状态

`planned`。当前工作区尚无可运行 Unity 工程，尚未执行。

## 来源

- [AESTHETIC-2026-003](../cards/AESTHETIC-2026-003_特效Orange法阵高级感对比体量.md)
- [CRAFT-2026-011](../cards/CRAFT-2026-011_特效Orange法阵元素气浪局部流动.md)
- [SRC-2026-UP389578709](../sources/SRC-2026-UP389578709_source.md)
