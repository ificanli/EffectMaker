# EXP-2026-107 Unity WebGL Prefab 特效播放器

> 纠偏：本文前半部分记录的 `E:/UnityVFX/EffectDemo6.0 + Unity 6000.5.9f1` 是早期外部播放器原型，不是当前 AI 特效训练工程的权威实现。当前实现和验收必须使用 `UnityDemo/EffectDemo + Unity 2022.3.16f1c1`；见文末“EffectDemo 2022 纠偏复验”。

## 目标

在主工程 `E:/UnityVFX/EffectDemo6.0` 中构建一个由浏览器直接运行 Unity Prefab 的 WebGL 播放器。网页必须展示 Unity 实时 Canvas，而不是截图轮播或预录视频，并支持搜索、选择、重播、暂停、倍速、背景、旋转和缩放。

## 环境

- Unity：`6000.5.9f1`
- URP：`17.5.0`
- Unity CLI：`1.0.0-beta.6`
- Web Build Support：已安装，`unity editors --installed --format json` 显示 `modules: Web`
- 主工程：`E:/UnityVFX/EffectDemo6.0`
- 构建目录：`E:/UnityVFX/EffectDemo6.0/Builds/WebGL/VfxPrefabPlayer`
- 本地地址：`http://127.0.0.1:8770/`
- Beads：`vfx-adl`

未读取或修改兼容工程 `E:/Unity特效人工智能学习/UnityDemo/EffectDemo6.0`，也未把 Unity 2022 Trains source-render 工程混入本构建。

## 实现结构

```text
Assets/Art/VFX 中的可渲染 Prefab
  + BladeRoot / Fireworks 场景根节点派生快照
  -> VfxWebCatalog.asset
  -> VfxWebPlayer.unity
  -> Unity WebGL Player
  -> HTML 控制层 SendMessage
  -> 浏览器 Canvas 与运行指标回传
```

构建器跳过同时没有 `Renderer` 和 `ParticleSystem` 的 Prefab，因此空 Timeline 控制 Prefab 不会被冒充为可播放效果。

## 首批目录

`vfx_web_build_manifest.json` 记录 5 项：

1. `OrangeSlash_Final`
2. `VFX_OrangeSlash_AB`
3. `VFX_ResourceSmoke`
4. `BladeReproduction`，从 `BladeReproduction.unity :: BladeRoot` 生成派生 Prefab
5. `Fireworks`，从 `SampleScene.unity :: VFX_Verification/EffectRoot/Fireworks` 生成派生 Prefab

目录中的派生 Prefab 不回写源场景参数，只承担 Web 播放引用闭包。

## 构建结果

- Unity WebGL：成功，退出码 `0`
- Catalog：`5` 项
- 场景数据：约 `3.2 MB` 压缩、`8.9 MB` 未压缩
- 完整构建：约 `54.4 MB`
- Wasm：`44,913,109` bytes
- `unity projects verify`：`0 errors / 0 warnings`
- Python/契约测试：`7/7` 通过
- HTTP：`index.html` 为 `200 text/html`
- HTTP：`.wasm` 为 `200 application/wasm`
- 浏览器目录：显示 `5 / 5 项`
- 浏览器 Runtime：状态为“运行时已连接”

## 像素观察

所有结论来自 Codex 浏览器截图的实际像素，不以文件存在、HTTP 200 或构建成功代替视觉判断。

### BladeReproduction

- 桌面峰值中，橙白主体弧连续、边缘清楚，蓝色外缘和橙色内缘可区分。
- 黑灰地面提供尺度和遮挡参照，主体未被左右栏或底部工具条遮挡。
- 移动端 `390x844` 中主体完整可见，工具条位于底部，运行统计位于左上，无文本或控件重叠。
- 当前只证明 Prefab 能在 WebGL 中正确显示，不代表刀光复刻审美任务已通过。

### Fireworks

- 红橙粒子能够真实发射、变化并回传实时粒子数。
- 粒子仍呈简单方块，层次和造型较弱，这是源 Prefab 的视觉质量，不是网页播放器故障。
- 中性背景切换后地面和粒子仍可辨认。

### OrangeSlash / ResourceSmoke

- 两个 OrangeSlash Prefab 即使旋转相机仍主要呈窄 U 形或细暗蓝弧，和 BladeReproduction 的清晰弧面差异明显。
- ResourceSmoke 可见圆环和粒子，但整体偏暗，部分粒子呈黑色方块。
- 这些条目技术上可播放，但不应作为审美正样本；播放器保留它们用于暴露资产问题和对比。

## 交互验证

- 搜索 `Blade`：计数变为 `1 / 5 项`，Prefab 列表只剩 `BladeReproduction`。
- 暂停烟花：700ms 前后保持 `1.22s / 89 粒子`。
- `2x` 恢复：550ms 墙钟时间后播放时间从 `1.22s` 到 `2.38s`，显示 `2x`。
- 拖拽旋转和滚轮缩放：操作前后浏览器截图 SHA-256 不同，且修改后的 Blade 峰值仍完整可见。
- 背景：深色、中性、浅色三种 swatch 可切换，选中态同步更新。
- 移动端：`scrollWidth=390` 与 `viewportWidth=390` 一致；工具条范围 `25-365`；抽屉宽 `320`，位于 `0-320`，没有横向溢出。

## 截图证据

- `workspace/previews/vfx_prefab_player/desktop_blade_peak.png`
- `workspace/previews/vfx_prefab_player/desktop_fireworks_2x.png`
- `workspace/previews/vfx_prefab_player/desktop_blade_orbit_zoom.png`
- `workspace/previews/vfx_prefab_player/mobile_blade_peak.png`
- `workspace/previews/vfx_prefab_player/mobile_library_drawer.png`

`workspace/previews/` 是本地视觉证据目录，按仓库忽略规则不自动提交。

## 弯路与修复

1. WebGL 模块直连被地域重定向到未同步的中国 CDN，返回 404；改用 Unity CLI 显式本机代理后安装成功。
2. 第一版 Volume Profile 只把组件加入列表，没有作为子资产持久化，重新导入后变成 `fileID: 0`；改为 `AssetDatabase.AddObjectToAsset`。
3. 第二版用 `AssetDatabase.IsSubAsset` 判断幂等性，已落盘组件仍被误判并重复添加；改用 `AssetDatabase.GetAssetPath(component)` 是否为空判断。
4. 第一版运行时间使用 wall-clock，暂停时仍增加；改为只在未暂停时按倍速累计的 playback elapsed。
5. 默认第一个条目是视觉较差的 OrangeSlash；改为优先选择 Blade 分类，保留差样本供对比。

## 已知限制

- 浏览器 Console 有一条非致命 URP 警告：`Edge Adaptive Spatial Upsampling` 在 WebGL 不受支持。当前 `m_RenderScale=1`，实际页面、Bloom、材质和交互正常，没有 Runtime error；后续发布优化可为 WebGL 建立专用精简 URP Asset。
- Unity CLI 每次先连接到共享旧 Licensing Client 时会记录协议版本错误，随后自动启动 `6000.5.9` 匹配客户端并成功完成授权。只有出现后续成功握手和构建退出码 `0` 时可视为已恢复。
- 构建包含完整 URP 后处理和多个项目程序集，首包约 `54.4 MB`，尚未做 Shader/程序集裁剪。
- 浏览器不能在运行时读取任意本机 `.prefab`。新增资源必须在构建前进入主工程并形成依赖闭包。
- Trains 全量 Prefab 仍需先完成 `vfx-2df.18.7.1` 可播放性审计，再选择性迁入主工程。

## 下一步

1. 为不同特效族增加条目级相机、缩放、背景和触发上下文配置。
2. 完成 Trains Prefab 可播放性审计，只迁入依赖闭合且授权明确的条目。
3. 建立 WebGL 专用 URP Asset 和程序集/Shader 裁剪，将首包体积和启动时间纳入性能门禁。

## 训练标注接入复验（2026-08-28）

- Beads：`vfx-2df.18.12`
- 新增 run manifest + 显式 Prefab 映射 -> WebGL review bundle 工具和 JSON Schema。
- Catalog 可携带 `run_id`、`candidate_id`、`training_case_id`、材质时间线路径、材质事件数、关键时间点和源脚本覆盖状态。
- 网页新增关键材质时间点重播、动态质量/节奏/风格评价和 `human_feedback.v1` JSONL 导出；未关联候选时记录与导出按钮禁用。
- Unity WebGL 运行时每 `0.25s` 计算材质/Shader/Keyword/声明属性/MPB 指纹和变化次数，该值只作 WebGL 兼容性信号。
- 首次重建因 Unity `6000.5.9f1` 禁止 `GetInstanceID()` 而失败，改用 `GetEntityId()` 后构建成功；详见 `ERR-UNITY-042`。
- 新构建保持 `5` 个 Prefab、约 `54.4 MB`；`VfxPrefabPlayer.wasm` 为 `44,931,701` bytes；build manifest 明确记录当前 `trainingReviewBundleStatus=not_linked` 和 `trainingLinkedPrefabCount=0`。
- 浏览器实际复验：运行时已连接；训练关联、动态评价、滑杆、结论和导出控件布局正常；BladeReproduction 重播约 `0.67s` 可见，当前 WebGL 材质变化计数为 `0`；未关联状态下评价按钮保持禁用。
- Console 仍只有既有 URP Edge Adaptive Spatial Upsampling 非致命警告，没有新增 Runtime error。

该阶段结论已被下方 EffectDemo 2022 纠偏复验取代；Unity 6 原型不再作为当前训练播放器的工程或运行证据。

## EffectDemo 2022 纠偏复验（2026-08-28）

- Beads：`vfx-2df.18.12.2`
- 权威工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`
- Unity：`2022.3.16f1c1`
- URP：`14.0.9`
- 稳定构建输出：`workspace/Builds/WebGL/VfxTrainingPlayer2022`
- 当前本地地址：`http://127.0.0.1:8772/`

纠偏过程：

1. 将 Catalog、运行时播放器、Builder、WebGL bridge 和训练标注模板移入 EffectDemo 2022。
2. Builder 改为直接扫描 `Assets/VFXSourceIngest/Trains/Trains_FX_All_001`；无 review bundle 时只构建 5 项，有 bundle 时只接受同工程、真实 Play Mode、材质时间线 `ready` 的显式候选。
3. Unity 2022 正常 UPM 启动仍复现 `The "path" argument must be of type string. Received undefined`，因此 Builder 去除 URP Editor API 依赖，并使用既有 `-noUpm` 环境规避方案完成 C# 和 WebGL 构建。
4. Unity CLI 首次给中国版 `f1c1` Editor 安装了国际版 `f1` WebGL 模块；构建退出码虽然为 `0`，浏览器报 `Expected 2022.3.16f1 / Actual 2022.3.16f1c1`，Player 初始化失败。
5. 从 Unity 中国官方发布页取得 revision `2f3f1b3bde89` 的 `f1c1` WebGL 安装器；Authenticode 签名有效，签发者为优三缔科技（上海）有限公司。覆盖安装后，使用全新 `EffectDemoWeb2022R002` 隔离副本重新构建。

R002 结果：

- Unity WebGL 构建退出码 `0`，日志包含 `Build Finished, Result: Success`。
- Catalog 为 5 个 EffectDemo Trains Prefab：`FX_BossDie`、`FX_CommonDie`、`FX_EleDie`、`FX_BossTips`、`FX_qiangkouhuo`。
- `VfxTrainingPlayer2022.data`：`2,679,970` bytes。
- `VfxTrainingPlayer2022.wasm`：`12,234,972` bytes。
- 浏览器显示 `Unity 2022 Web`、`5 / 5 项` 和“运行时已连接”。
- `FX_qiangkouhuo` 在 `0.25x`、运行时间约 `0.07s` 时实际显示橙色枪口火焰，不是截图轮播。
- 当前 5 项未绑定 material timeline，因此 `trainingLinkedPrefabCount=0`，评价按钮保持禁用；这是正确边界，不伪造训练关联。
- Console 有 Missing Script 和 Physics Module stripped 警告，条目已标为“需要上下文”；这些样本不能直接成为正向监督。

最终结论：Unity 6 原型不再作为当前任务证据。EffectDemo 2022 已具备可运行的 WebGL 动态复核入口，下一步仍是先完成 `vfx-2df.18.11` 的逐帧材质时间线，再生成正式 review bundle。
