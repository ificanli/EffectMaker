# PrefabGraph 颜色与材质通道规范

适用：本任务的 EffectDemo 2022，当前实测 Unity 2022.3.62f3c1 / URP 14.0.12。

## 颜色不是一个参数

粒子最终颜色同时受到 Main.startColor、Color over Lifetime、材质颜色、纹理 RGB/A、混合模式及色彩空间影响。不能把同一个 Prompt 色重复写入所有相乘通道。

本次灰色对照中，旧通道的 API 浮点乘积为 `0.5 * 0.5 * 0.5 = 0.125`，独立通道为 `0.5 * 1 * 1 = 0.5`。实际像素还经过线性/sRGB 转换、覆盖率和混合，不能简单乘255推断截图。

## 新字段

`components.particle_systems[].parameters` 增加两个可选字段：

```json
{
  "material_color_mode": "preserve_template",
  "color_over_lifetime_gradient": {
    "mode": "Blend",
    "color_keys": [
      {"time": 0.0, "rgb": [1.0, 1.0, 1.0]},
      {"time": 1.0, "rgb": [1.0, 1.0, 1.0]}
    ],
    "alpha_keys": [
      {"time": 0.0, "alpha": 1.0},
      {"time": 1.0, "alpha": 0.0}
    ]
  }
}
```

- `start_color_rgba`：粒子初始色；新教程的 Prompt 色施加在这里。
- `color_over_lifetime_gradient`：生命周期乘数，完整保存颜色键、Alpha键和 `Blend` / `Fixed` 模式。普通渐隐使用中性RGB与变化Alpha；需要黑白闪时显式提供黑白颜色键。
- `material_color_mode=preserve_template`：保留原材质所有颜色属性，不自动改 `_BaseColor`、`_Color`、`_Main_Color` 或 `_TintColor`。需要明确的材质模板或原始材质引用，供回读核验。
- 缺省模式或 `legacy_start_color`：保持历史 Graph 行为；不能把旧字段的含义静默改成新规则。
- `end_color_rgba`：旧字段保留。新生成器令其与显式渐变的最后颜色/Alpha键一致；完整渐变以键表为准。

键数为每类2至8个，时间在0到1且严格递增，Alpha在0到1，RGB非负且所有数值有限。Unity实际执行仍需回读校验。JsonUtility会将部分缺失嵌套字段构造成空对象，因此不能仅用 `!= null` 判断旧Graph是否提供了新数据。

## 导出和回读

源Prefab导出确定性颜色渐变的完整键表。常量Color可规范化为等值两键渐变；随机颜色分布仍作为明确缺口，不以单次采样冒充完整重建。

回读需要核对：

1. 初始色与全部颜色/Alpha键，包括模式和中间键，不能只核对终点。
2. `preserve_template` 下的所有 Shader Color 属性及 Shader 身份。
3. Renderer 顶点流顺序、材质与贴图绑定。
4. 实际运行的 Pipeline、色彩空间和捕获背景。

保存了Material路径不等于保存了全部材质运行语义。QFX校准例中的额外UV、Noise、Emission、黑色溶解边说明：仅替换主贴图不足以证明配置适合另一种效果。

## 教程映射

`ProcedureSpec.steps[].authoring_stage` 用于区分贴图制作、Unity设置、材质设置和运行验证。复杂渐变可作为 `color_over_lifetime_gradient` 参数对象保存，其结构仍由最终Graph Schema和Unity执行器校验。

Part03局部视频审计确认的内容是：Photoshop贴图图层操作、Fixed模式黑白闪动、以及另一个qi对象的RGB灰度Mask绑定。它没有证明必须创建Unity的OutlineVariation，也没有证明MainBolt采用Alpha Clip。

源教程精确颜色键、Alpha值未完全恢复。本项目用于对照的键值必须保持 `inferred`，不能因为能够运行就升级为作者原始参数或正式SFT。

## 验证入口

- `workspace/tools/vfx_generation/particle_color_calibration.py`：颜色旧/新通道对照、教程Fixed/Blend/Alpha-only对照及源导出往返请求。
- `workspace/data/vfx_generation/generated/particle_color_calibration_r002/`：11个颜色/材质对照、API审计、连续帧和校准报告。
- `workspace/data/vfx_generation/generated/tutorial_lightning_fixed_color_r002/`：亮黑亮机制、源往返和Blend重复性诊断；R003进一步校正Fixed首段先亮。
- `knowledge/sources/SRC-2026-GAMEVFX-001/episode_01雷之呼吸/visual/material_color_audit_20260907/audit_report.md`：源视频事实、时间码与未确认项。

校准中明确使用官方URP粒子材质模板。它是可追溯的实验选材，不是已经接入自动资产排序的证明；完整教程、源场景、专业质量和训练正例资格仍须分别验收。

Fixed会同时影响颜色和Alpha的取样。本机2022实测中，t=0.1取到右侧黑色键，Alpha也取到后一个键的0.4，不能把0秒键值当作整段起始值。必须核对Unity实际Evaluate值和连续帧；未知源Alpha值仍标inferred。新生成包同时保存ProcedureSpec快照，避免后来修正知识库时改变旧实验的来源解释。
