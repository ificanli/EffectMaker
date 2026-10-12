# SlashArc-Pref-001 启动 Prompt

## 正向目标

生成一批风格化俯视刀光主体弧候选。主体弧应表达明确的斩击方向、锋利主刃、非对称宽窄变化和可继续制作的攻击形体。

参考目标来自 `BV198v6BoE9h_final_case`，首轮只关注主体弧，不制作支撑层、命中层、场景锚点、Bloom 或最终成品。

## 负向约束

- 不要规则半环。
- 不要完整闭合圆环。
- 不要 UI 图标感。
- 不要左右完全对称。
- 不要把 V9 主体弧作为默认基础。
- 不要矩形 billboard 贴片。
- 不要通过场景、命中粒子或支撑层掩盖主体弧问题。

## 参考帧

- 峰值参考：`knowledge/sources/SRC-2026-UP389578709/teaching_comparisons/BV198v6BoE9h_final_case/reference/frames/ref_0012_0000.600s.jpg`
- 收束参考：`knowledge/sources/SRC-2026-UP389578709/teaching_comparisons/BV198v6BoE9h_final_case/reference/frames/ref_0018_0000.900s.jpg`
- 时间轴：`knowledge/sources/SRC-2026-UP389578709/teaching_comparisons/BV198v6BoE9h_final_case/reference/timeline.json`

## 首轮候选约束

- 候选数量：不少于 16 个。
- 层级：只启用 `core_blade`。
- 渲染时间点：`0.30, 0.50, 0.60, 0.75, 0.90` 秒。
- 输出：每个候选保存 spec、seed、截图 manifest；整批生成 contact sheet。
- 人工反馈：至少标注最接近的 3 个、明确失败的 3 个，以及失败原因。

