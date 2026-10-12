# Unity WebGL Prefab 特效播放器

## 定位

该播放器用于在普通网页中运行 Unity Prefab 特效，并提供搜索、切换、重播、暂停、倍速、背景、旋转、缩放、运行指标和动态人工评价。它不是截图轮播，也不是录制视频：实际渲染由 Unity WebGL Player 完成。

```text
Prefab 与依赖资源
  -> Unity 构建期目录资产
  -> WebGL Player
  -> HTML 控制层
  -> 浏览器 Canvas 实时画面
```

浏览器不能直接解析 `.prefab`。Prefab、Material、Texture、Mesh、Shader 和脚本必须先进入 Unity WebGL 构建，网页再通过 `SendMessage` 控制运行时对象。

训练接入采用明确的证据分工：

```text
EffectDemo 2022 真实 Play Mode
  -> material_timeline.json（材质真值）
  -> run_manifest.json
  -> WebGL review bundle（只复制训练标识和时间线摘要）
  -> EffectDemo 2022 WebGL 同候选动态复核
  -> human_feedback.v1 JSONL
```

`material_timeline.json` 才是材质、贴图、Shader Keyword、MaterialPropertyBlock 和溶解参数的训练真值。WebGL 侧材质指纹只用于判断同一 Prefab 在 WebGL 中是否发生材质状态变化和是否可能出现平台偏差，不能覆盖或替代 EffectDemo 采集结果。

## 固定工程边界

- 工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`
- Unity：`2022.3.16f1c1`
- 渲染管线：URP `14.0.9`
- 默认构建输出：`E:/Unity特效人工智能学习/workspace/Builds/WebGL/VfxTrainingPlayer2022`
- 默认本地地址：`http://127.0.0.1:8770/`
- 当前基础验证地址：`http://127.0.0.1:8772/`
- 当前材质时间线复核地址：`http://127.0.0.1:8773/`
- 当前 79 条 Prefab WebGL 构建：`workspace/Builds/WebGL/VfxTrainingPlayer2022PrefabReviewR004ShortWindow`
- 当前 WebGL 服务：`http://127.0.0.1:8777/`
- 当前全量人工评价页：`http://127.0.0.1:8774/`，批次为 `prefab_human_review_r006_short_window`

`EffectDemo6.0` 和 `E:/UnityVFX/EffectDemo6.0` 不参与当前训练播放器构建。Trains Prefab、材质、贴图、Mesh 和 Shader 已按依赖闭包位于同一个 EffectDemo 2022 工程，WebGL 目录直接引用这些资产，不再跨 Unity 工程搬运第二份副本。

## 当前结构

Unity 侧：

- `Assets/Art/VFX/WebPrefabPlayer/Runtime/VfxWebCatalog.cs`：构建期生成的 Prefab 引用目录。
- `Assets/Art/VFX/WebPrefabPlayer/Runtime/VfxWebPlayer.cs`：实例化、播放、暂停、倍速、视角和浏览器事件。
- `Assets/Art/VFX/WebPrefabPlayer/Editor/VfxWebPlayerBuilder.cs`：扫描、派生场景根节点 Prefab、生成场景和执行 WebGL 构建。
- `Assets/Art/VFX/WebPrefabPlayer/Plugins/WebGL/VfxWebBridge.jslib`：Unity 到网页的原生 WebGL 消息桥。
- `Assets/WebGLTemplates/VfxPrefabPlayer/`：网页 UI、加载逻辑和交互。

工作区侧：

- `workspace/tools/build_vfx_web_player.ps1`：固定版本、固定主工程的一键构建入口。
- `workspace/tools/vfx_web_training_review.py`：把 run manifest、材质时间线摘要和 WebGL Prefab 映射打包为 review bundle。
- `workspace/tools/vfx_generation/prefab_human_review.py`：生成全量中文固定选项评价页，并按 `webgl_preview` 状态嵌入动态 Unity 复核。
- `workspace/tools/vfx_web_player_server.py`：只监听本机回环地址的静态服务。
- `workspace/tests/test_vfx_web_prefab_player_contract.py`：Unity 与网页消息契约。
- `workspace/tests/test_vfx_web_player_server.py`：本地服务入口和 MIME 类型。

## 构建

首次使用必须确认 Web Build Support：

```powershell
unity editors --installed --format json
```

本机必须存在与中国版 Editor 完全一致的 `2022.3.16f1c1` WebGL Support。不要直接给 `f1c1` Editor 安装国际版 `2022.3.16f1` 模块：国际版构建虽然能退出 `0`，浏览器会报 `Expected 2022.3.16f1 / Actual 2022.3.16f1c1` 并拒绝加载。

```powershell
https://download.unitychina.cn/download_unity/2f3f1b3bde89/TargetSupportInstaller/UnitySetup-WebGL-Support-for-Editor-2022.3.16f1c1.exe
```

该地址来自 Unity 中国 `2022.3.16` 官方发布页，安装包签名应为优三缔科技（上海）有限公司。模块目录存在不等于版本匹配，最终必须在浏览器中真实加载 Player 数据。

执行构建：

```powershell
powershell -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1
```

构建已具有材质时间线的训练候选时，额外传入 review bundle：

```powershell
python -m workspace.tools.vfx_web_training_review asset-map `
  --run-manifest workspace/data/vfx_generation/runs/<run-id>/run_manifest.json `
  --output workspace/data/vfx_generation/runs/<run-id>/webgl_asset_map.json

python -m workspace.tools.vfx_web_training_review bundle `
  --run-manifest workspace/data/vfx_generation/runs/<run-id>/run_manifest.json `
  --asset-map workspace/data/vfx_generation/runs/<run-id>/webgl_asset_map.json `
  --output workspace/data/vfx_generation/runs/<run-id>/webgl_review_bundle.json

powershell -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1 `
  -TrainingReviewBundle workspace/data/vfx_generation/runs/<run-id>/webgl_review_bundle.json
```

`webgl_asset_map.json` 只负责声明候选对应 EffectDemo 中的哪个 Prefab，不能用名称相似自动猜测：

```json
{
  "schemaVersion": "vfx_web_training_asset_map.v1",
  "reviewBundleId": "trains_fx_runtime_r001_web_review",
  "mappings": [
    {
      "candidateId": "source_prefab_001_fx_acid",
      "webPrefabPath": "Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/Battle/Fx_acid/eff/Fx_acid.prefab"
    }
  ]
}
```

由于该机 Unity 2022 UPM 存在 `path argument ... undefined` 环境故障，当前包装脚本使用已验证的 `-noUpm` 入口。主工程正在 Editor 中打开时，不得抢占 Lockfile，先复制不含 `Library/Temp/Logs/Builds` 的隔离副本，再传入 `-ProjectPath`：

```powershell
powershell -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1 `
  -ProjectPath E:/Unity特效人工智能学习/workspace/unity-render-staging/EffectDemoWeb2022R002
```

构建器会执行以下动作：

1. 从 `Assets/VFXSourceIngest/Trains/Trains_FX_All_001` 扫描带 Renderer 或 ParticleSystem 的 Prefab。
2. 没有 review bundle 时只选前 `5` 个可渲染 Prefab，避免把全量 259 项塞入验证包。
3. 有 review bundle 时只构建显式映射的候选，并要求来源工程是 EffectDemo 2022、`capture_mode=play_mode_runtime`、材质时间线状态为 `ready`。
4. 跳过没有 Renderer 和 ParticleSystem 的空壳或纯控制 Prefab。
5. 生成 `VfxWebCatalog.asset`、预览场景和地面材质；WebGL Builder 不依赖 URP Editor API。
6. 使用项目 WebGL Template 构建，写出 `vfx_web_build_manifest.json`；任一训练候选未映射就拒绝构建。

## 接入全量人工评价页

`prefab_human_review_r005_all_webgl` 不会把 259 条 Prefab 都冒充成可独立 WebGL 运行。它按规范化 `prefab_path` 将两个候选 id 命名空间连接起来：Play Mode run 的 `source_prefab_*` 只保留为运行溯源，结构数据集的 `trains_fx_*` 才是网页评价条目 id。不能按相似名称或两个 id 的序号连接。

```text
Play Mode run source_prefab_*
  -> source Prefab Assets 路径
  -> dataset trains_fx_* Prefab 路径
  -> Unity AssetDatabase GUID
  -> WebGL catalog id
  -> 8774 当前评价条目
```

为实际 run 生成完整映射、WebGL catalog 元数据和评价批次：

```powershell
python -m workspace.tools.vfx_web_training_review asset-map `
  --run-manifest workspace/data/vfx_generation/runs/trains_prefab_playmode_r002/run_manifest.json `
  --review-bundle-id trains_prefab_playmode_r002_web_review `
  --output workspace/data/vfx_generation/runs/trains_prefab_playmode_r002/webgl_asset_map_r002.json

python -m workspace.tools.vfx_web_training_review catalog `
  --asset-map workspace/data/vfx_generation/runs/trains_prefab_playmode_r002/webgl_asset_map_r002.json `
  --unity-project UnityDemo/EffectDemo `
  --dataset-root workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002 `
  --player-url http://127.0.0.1:8776/ `
  --output workspace/data/vfx_generation/runs/trains_prefab_playmode_r002/webgl_catalog_r002.json

python workspace/tools/vfx_generation/prefab_human_review.py build `
  --dataset-root workspace/data/vfx_generation/datasets/prefab_structure_r002_training_r002 `
  --run-root workspace/data/vfx_generation/runs/trains_prefab_playmode_r002 `
  --output-root workspace/data/vfx_generation/reviews/prefab_human_review_r005_all_webgl `
  --batch-id prefab_human_review_r005_all_webgl `
  --webgl-catalog workspace/data/vfx_generation/runs/trains_prefab_playmode_r002/webgl_catalog_r002.json
```

评价页对 `webgl_ready` 条目嵌入 `8775` 的 Unity WebGL iframe。父页只发送 `{ type: "vfx-web-select", catalogId }`；子页要求 URL 传入的 `parentOrigin` 与同主机回环来源精确匹配，且只能调用既有 catalog 的 `SelectEffect`。这不是通用远程 Unity 命令接口。

其余条目不会加载黑屏 iframe：

| WebGL 状态 | 当前数量 | 页面行为 |
|---|---:|---|
| `webgl_ready` | 79 | 显示真实 Unity WebGL，帧序列继续作为辅助证据 |
| `needs_context` | 143 | 显示角色挂点、UI、脚本或战斗上下文的中文原因 |
| `build_excluded` | 20 | 说明未进入已验证的 59 条构建集合 |
| `not_in_direct_playable_set` | 37 | 说明当前没有独立 WebGL 输出 |

`ai_drafts.jsonl` 仍只提供未保存建议；只有点击评价页的“保存本条”才会写入 `feedback.jsonl` 和 `feedback_store.json`。重建评价批次时使用 `migrate-feedback` 迁移已有 Schema 合法的人类选择，证据 trace 会绑定新 run；浏览器联调禁止保存测试数据。

评价表单中的“人工备注”是唯一允许自由输入的字段，用于记录选项无法表达的额外视觉判断、上下文限制或复用条件。它保存为 Schema 内的 `notes`，会与其他人工选择一起迁移到重建批次；不要把 AI 建议、命令输出或无关调试日志填入备注。

## 启动

```powershell
python -m workspace.tools.vfx_web_player_server
```

打开：

```text
http://127.0.0.1:8770/
```

不能直接双击 `index.html`。浏览器对 WebAssembly 和 Unity 数据文件要求 HTTP 来源；本地服务还会返回正确的 `.wasm` MIME 类型。

## 新增 Prefab

1. 将 Prefab 与完整依赖闭包放入 EffectDemo `Assets/VFXSourceIngest`。
2. 确认没有 Missing Script、Missing Material 和只在 Editor 中存在的脚本。
3. 在 Unity 中单独播放，确认其不依赖角色骨骼、场景锚点、运行时事件或外部管理器。
4. 重新运行构建脚本，检查 `vfx_web_build_manifest.json`。
5. 在浏览器中实际查看动态画面，并验证重播、暂停、倍速、旋转和缩放。

Trains 全量 Prefab 已位于当前 EffectDemo 2022 工程。默认验证目录中的 Missing Script 项只用于暴露上下文缺失，不能作为正向训练样本；正式 review bundle 必须结合材质时间线和源脚本覆盖状态筛选。

## 动态训练评价

只有 Catalog 条目同时具有 `run_id` 和 `candidate_id` 时，网页才允许记录评价。每条导出记录使用现有 `human_feedback.v1`，并附加 `web_review_context`：

- 观察时间、暂停状态和播放倍速；
- 背景、相机 yaw/pitch/distance；
- WebGL 材质状态指纹和本次播放中的变化次数；
- EffectDemo 材质时间线路径、真值变化次数和源脚本覆盖状态；
- 固定 `evidence_role=dynamic_human_review_only`，禁止升级为材质真值。

有材质关键变化点时，右侧时间点按钮会真实重播，并在目标时间附近暂停；这让评价者观察脚本驱动的贴图替换、Keyword、MPB 或溶解变化，而不是只看随机暂停画面。导出的 JSONL 可直接交给 `workspace.tools.vfx_generation.feedback` 校验和后续汇总。

逐帧材质采集的实现、受控正例、真实静态负例、上下文阻塞案例和源脚本审计见 [EXP-2026-108 EffectDemo 逐帧材质状态时间线](../../knowledge/experiments/EXP-2026-108_EffectDemo逐帧材质状态时间线.md)。

## 限制

- WebGL 构建只包含构建时已引用的 Prefab，不能读取本机任意 `.prefab` 路径。
- 依赖角色 Animator、骨骼挂点、场景脚本、运行时事件或专用渲染功能的 Prefab，仍需要适配上下文。
- VFX Graph、Compute Shader、GrabPass、自定义原生插件和部分平台 Shader 可能不支持 WebGL，必须逐项构建和像素验证。
- 大批量 Prefab 会显著增加首次下载体积。训练集浏览应保留快速视频/截图模式，实时 WebGL 用于选中候选的最终动态复核。
- WebGL 材质指纹只能枚举 Shader 声明属性和可查询的 MPB 属性；未知属性 ID、全局 Shader 状态和被裁剪的平台分支仍需 EffectDemo 真值和源脚本审计。
- `-noUpm` WebGL 构建可能裁剪未显式引用的 Physics 等模块；浏览器 Console 中的缺失脚本和模块裁剪警告必须进入技术有效性标签。
- source manifest 的 unknown/missing dependency edge 是来源完整性风险，不是独立运行失败的证明。Unity audit 为 `particle_playable` 的 Prefab 必须先进入真实 Play Mode；固定镜头主体偏小只能标记为 `主体过小`，不能标记为不可播放。
- 网页能成功加载、构建退出码为 0、Canvas 非空，都不能替代人工视觉评价。

## R009 导入修复复核

2026-08-29 对 `EffectDemo` 的 Trains 导入闭包和 Prefab 审计进行了修复复核。r3 审计使用 Renderer `GlobalObjectId`/组件 fileID 对照序列化 `m_Materials`，可以区分源 Prefab 原生空槽、嵌套 Prefab 空槽和真实非零 GUID 断链：259 个 Prefab 中 126 个可直接播放，94 个需要上下文，37 个空/无效；真实缺失材质槽为 1，缺失 Shader 为 0。

126 条候选已通过 Unity 2022 Play Mode 采集，生成 3354 张有效帧且运行时错误为 0。WebGL R005 构建使用显式 AssetDatabase 路径映射，`prefabCount=126`、`trainingLinkedPrefabCount=126`，构建结果为 Success。新的人工评价页批次为 `prefab_human_review_r009_audit_r3_webgl`，服务地址为 `http://127.0.0.1:8774/`，旧批次中的 23 条人工反馈已迁移保留；对应技术数据集为 `prefab_structure_r005c_training_r005`，Unity WebGL 播放器服务为 `http://127.0.0.1:8778/`。

唯一未修复的引用是 `Fx_xingzhe_zhuangunzi` 的材质 GUID `6bca70b520d27ed41b9f612c4b3334cb`。该 GUID 在源工程中也没有对应 `.meta` 或可靠源文件，因此必须标记为源工程缺失/角色上下文依赖，禁止绑定相似材质。

## 验收证据

每次发布至少记录：

- Unity 版本、URP 版本和 WebGL 模块状态；
- 构建命令、日志和 `vfx_web_build_manifest.json`；
- 实际浏览器截图；
- 至少两个 Prefab 的切换与重播结果；
- 暂停、倍速、旋转、缩放和背景切换结果；
- WebGL Console 错误；
- review bundle 状态、训练关联条目数、材质关键时间点和一条通过 `human_feedback.v1` 校验的动态评价；
- 不可播放 Prefab、原因和下一步适配方式。

当前已验证实现、构建数据、浏览器像素、交互数值和截图路径见 [EXP-2026-107 Unity WebGL Prefab 特效播放器](../../knowledge/experiments/EXP-2026-107_Unity-WebGL-Prefab特效播放器.md)。
