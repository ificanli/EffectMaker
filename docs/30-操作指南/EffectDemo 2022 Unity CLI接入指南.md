# EffectDemo 2022 Unity CLI 接入指南

## 结论

`UnityDemo/EffectDemo` 使用 Unity `2022.3.16f1c1` 和 URP `14.0.9`。`rocwood/unity-cli-2022-mod` 只修改 Unity CLI 安装脚本，并不提供可直接放入 Unity 2022 的 `com.unity.pipeline` 包；仓库指南也明确要求对 Pipeline 源码和 DLL 做 2022 兼容修复。

本项目现在直接维护一份 `com.unity.pipeline` 2022 适配快照，配合 Unity CLI 的 `unity run --command` 使用；同时保留 `-batchmode -executeMethod` 作为离线兜底入口。Pipeline 快照位于 `UnityDemo/EffectDemo/Packages/com.unity.pipeline`，来源、修订号和授权边界记录在该目录的 `SOURCE_REVISION.txt`。

## 环境检查

```powershell
unity --version
unity editors --format json
unity projects verify "E:/Unity特效人工智能学习/UnityDemo/EffectDemo" --format json
```

预期项目版本为 `2022.3.16f1c1`，URP 为 `14.0.9`，`projects verify` 应返回 0 errors、0 warnings。

## 运行最小特效命令

在工作区根目录执行离线 batchmode 入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\workspace\tools\effectdemo_cli.ps1 -Action create
```

Pipeline 包完成导入并且 Editor 正常运行后，使用实时命令入口：

```powershell
unity command --project-path "E:/Unity特效人工智能学习/UnityDemo/EffectDemo" --query cli_smoke
unity run "E:/Unity特效人工智能学习/UnityDemo/EffectDemo" --command create_cli_smoke_effect --timeout 180
```

命令会调用 `EffectDemoCliCommands.CreateCliSmokeEffect`，生成：

```text
UnityDemo/EffectDemo/Assets/Art/VFX/CliSamples/CliSmokeEffect.prefab
UnityDemo/EffectDemo/Assets/Art/VFX/CliSamples/CliSmokeEffect.mat
```

删除该验证资产：

```powershell
powershell -ExecutionPolicy Bypass -File .\workspace\tools\effectdemo_cli.ps1 -Action remove
```

正式特效应继续遵循“需求 -> 参数 -> Editor 命令 -> 保存 -> CLI 验证 -> 截图/日志”的闭环。Pipeline 命令用于连接已运行的 Editor；`executeMethod` 仍作为无连接或 CI 场景的兜底入口。

## 导入 Prefab 的批量渲染复核

对于 `Assets/VFXSourceIngest/` 下的外部特效，先在工作区创建渲染请求。准备命令会逐 Prefab 写入候选 spec，并且只带入这个 Prefab 引用的材质、对应 Shader、贴图标签和 slot role：

```powershell
python -m workspace.tools.vfx_source_render prepare `
  --source-dir workspace/data/vfx_generation/sources/trains_ignore_effect_prefabs_003 `
  --run-root workspace/data/vfx_generation/runs/trn_ignore_effect_prefabs_003_r001 `
  --unity-project UnityDemo/EffectDemo
```

然后通过批处理渲染多时刻帧。此脚本故意不传 `-nographics`，因为 `Camera.Render` 必须实际使用图形设备：

```powershell
powershell -ExecutionPolicy Bypass -File .\workspace\tools\effectdemo_render_source.ps1 `
  -Requests workspace/data/vfx_generation/runs/trn_ignore_effect_prefabs_003_r001/render_requests.json
```

最后生成 `run_manifest.json`、`auto_eval.jsonl`、联系表和 `feedback.jsonl`：

```powershell
python -m workspace.tools.vfx_source_render finalize `
  --requests workspace/data/vfx_generation/runs/trn_ignore_effect_prefabs_003_r001/render_requests.json `
  --parent-beads-id vfx-2df.18
```

批处理成功仅表示相机截图已生成；是否能作为训练标签，仍必须查看联系表并把人工结论写入 `feedback.jsonl`。

### 真实播放自适应截图

固定时间点加 `ParticleSystem.Simulate` 只允许用于快速预筛。最终训练证据使用隔离项目中的真实 Play Mode：

```powershell
python -m workspace.tools.vfx_source_render prepare `
  --source-dir workspace/data/vfx_generation/sources/trains_fx_all_001 `
  --run-root workspace/data/vfx_generation/runs/<run_id> `
  --unity-project UnityDemo/EffectDemo `
  --review-batch <review-batch.json> `
  --run-id <run_id> `
  --adaptive-runtime --target-intervals 10 `
  --min-interval 0.02 --max-interval 0.25 --max-duration 8

powershell -ExecutionPolicy Bypass -File .\workspace\tools\effectdemo_render_source.ps1 `
  -Requests workspace/data/vfx_generation/runs/<run_id>/render_requests.json `
  -ProjectPath workspace/unity-render-staging/<staging-project> `
  -NoUpm -PlayModeRuntime
```

`-NoUpm` 只用于本机 Unity 2022 UPM 服务故障下的隔离离线渲染副本；它不能证明 Pipeline 或正式工程 UPM 可用。`capture_manifest.json` 必须记录 `capture_mode=play_mode_runtime`、`play_requested=true`、duration、interval、loop、time points 和 sampling basis。

## 与 `com.unity.pipeline` 的边界

- `EffectDemo6.0`：继续使用项目已有的 `com.unity.pipeline 0.5.0-exp.1` 和 `unity command`/Pipeline 工作流。
- `EffectDemo`：使用仓库内嵌的 2022 适配快照；该快照只保留源码和必要 DLL，不包含 Unity Editor 或 CLI 二进制。
- 2022 适配已对 `PhysicsMaterial`/`PhysicMaterial`、`Material.rawRenderQueue` 和不具备 Input System 的工程做了条件处理；当前已完成首次导入、编译和命令发现验证。
- 两个项目必须由各自版本的 Editor 打开，禁止用 Unity 6 打开 2022 项目或反向打开；两条管线的素材、Library 和临时端口也必须隔离。

## 验证记录要求

每次命令运行保留 Unity log、生成资产路径、Unity 版本、渲染管线和截图。CLI 返回成功只证明 Editor 命令完成，不等于视觉效果通过；动态粒子仍需在 Play Mode 采集至少两个时间点并进行人工画面复核。

## 当前接入验收

- Pipeline Server：`127.0.0.1:7801`
- `Unity.Pipeline.dll`：已生成
- `unity command --query cli_smoke`：已发现 `create_cli_smoke_effect` 和 `remove_cli_smoke_effect`
- `create_cli_smoke_effect`：已通过实时命令执行并返回 Prefab 路径
- Console：无 Error；仅保留 Unity 不建议以管理员权限运行的 Warning
- 工程校验：`unity projects verify` 为 `0 errors / 0 warnings`
