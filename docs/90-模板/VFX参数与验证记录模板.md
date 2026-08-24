# VFX 参数与验证记录模板

## 1. 标识

- Effect ID：
- 效果名称：
- 版本：
- 状态：`prototype` / `experimental` / `verified` / `absorbed`
- Unity 版本：
- 渲染管线和包版本：
- 目标平台：
- 目标镜头：远景 / 中景 / 近景 / UI
- 来源或参考：

## 2. 视觉目标

- 主体识别点：
- 主题颜色和明暗关系：
- 动作方向：
- 时间结构：
- 空间关系：
- 必须避免的问题：

## 3. 资源清单

| 类型 | 路径 | 命名 | 用途 | 版本/导入设置 | 依赖 |
|---|---|---|---|---|---|
| Texture |  |  |  |  |  |
| Mesh |  |  |  |  |  |
| Material |  |  |  |  |  |
| Shader |  |  |  |  |  |
| Particle System |  |  |  |  |  |
| Prefab |  |  |  |  |  |
| Timeline |  |  |  |  |  |

## 4. 贴图参数

- 文件：
- 用途：Base Color / Mask / Noise / Ramp / Normal / Flipbook / Distortion
- 分辨率：
- 格式与压缩：
- sRGB：开 / 关
- MipMap：开 / 关
- Filter：Point / Bilinear / Trilinear
- Wrap：Repeat / Clamp / Mirror
- RGBA 通道：
- UV 方向：
- UV 速度：
- 序列帧行列数与帧率：
- Alpha：Straight / Premultiply
- 已知限制：

## 5. 模型参数

- 文件：
- 类型：平面 / 弧面 / 带厚度网格 / 地面网格 / 其他
- 面数：
- 法线方向：
- Pivot：
- UV0 用途：
- UV1 用途：
- 顶点色用途：
- 是否允许负缩放：
- 是否有接缝、拉伸或背面问题：

## 6. 材质与 Shader 参数

- 材质：
- Shader：
- Blend：
- Cull：
- ZWrite：
- ZTest：
- Render Queue / Sorting：
- 主纹理：
- Mask：
- 主色：
- 辅助色：
- Emission/HDR：
- Opacity：
- UV Tiling/Offset/Speed：
- Dissolve 阈值/宽度/方向：
- Vertex Offset/Noise：
- 参数默认值、最小值、最大值：
- 透明叠加和过曝风险：

## 7. Particle System 参数

- 系统名称：`PS_<EffectName>_<Layer>`
- 层职责：Core / Body / Impact / Support / Detail / Ground
- Duration：
- Loop：
- Start Delay：
- Start Lifetime：
- Start Speed：
- Start Size：
- Start Rotation：
- Start Color：
- Emission Rate：
- Burst 时间与数量：
- Shape：
- Simulation Space：Local / World / Custom
- Size over Lifetime：
- Color over Lifetime：
- Rotation over Lifetime：
- Noise：
- Gravity：
- Trails / Collision / Sub Emitters：
- Renderer 材质与排序：
- Max Particles：
- 关闭本层后的视觉变化：

## 8. Timeline 与触发

| 阶段 | 开始 | 结束 | 层 | 事件/曲线 | 观察结果 |
|---|---:|---:|---|---|---|
| Prewarm/Anticipation |  |  |  |  |  |
| Build |  |  |  |  |  |
| Burst/Impact |  |  |  |  |  |
| Sustain |  |  |  |  |  |
| Dissolve/Residual |  |  |  |  |  |

- 触发方式：
- 可重复播放：是 / 否
- 慢速检查结果：
- 方向性溶解是否连续：
- 地面反馈是否与主体衔接：

## 9. 验证记录

### 视觉

- [ ] 正常速度检查
- [ ] 0.25 倍速检查
- [ ] 逐帧检查
- [ ] 远景检查
- [ ] 中景检查
- [ ] 近景检查
- [ ] Core/Impact/Support/Detail/Ground 分层开关检查
- [ ] 轮廓未被 Bloom、雾效或辅助元素覆盖
- [ ] 收束没有整层同时消失

### 工程

- [ ] `unity projects verify` 通过
- [ ] Prefab 可独立打开
- [ ] 引用无丢失
- [ ] 实际 Inspector 值与本记录一致
- [ ] Timeline 可重复播放
- [ ] Unity 版本和渲染管线已记录

### 性能

- 平均帧率：
- GPU Frame Time：
- CPU Frame Time：
- 最大粒子数：
- Draw Calls：
- Overdraw 观察：
- 纹理显存：
- Shader 变体/后处理成本：
- 目标设备：
- 是否需要 LOD/裁剪/对象池：

## 10. AI 操作审计

- 工具：CLI / Pipeline / MCP / Editor 脚本 / 人工
- 操作时间：
- 目标路径：
- 修改前状态：
- 修改后状态：
- 日志路径：
- 截图路径：
- 人工质量判断：
- 是否允许升级状态：
- 未解决问题：
