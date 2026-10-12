# Unity CLI 使用指南

## 定位

本工程默认使用 Unity 官方 CLI（当前验证版本：`1.0.0-beta.6`）管理 Unity 项目、Editor、模块、认证、项目检查、构建和 Editor 命令。

Unity MCP 不再是默认入口。只有 Unity CLI 无法覆盖实时 Editor 操作、对象层级修改、运行状态观察或截图读取时，才启用 Unity MCP 作为补充桥接。

## 常用命令

```bash
unity --version
unity --help
unity doctor
unity editors --format json
unity projects verify "E:/Unity特效人工智能学习/workspace/unity-verification" --format json
```

项目操作前先执行 `unity projects verify`，确认没有缺失 `.meta`、重复 GUID、冲突标记或无效 manifest。

## 项目和 Editor

使用 CLI 管理项目时，优先选择与项目版本匹配的 Editor：

```bash
unity editors --format json
unity open "E:/path/to/project"
```

如果项目没有匹配的 Editor，再评估是否安装对应版本和模块。不要未经确认自动升级项目版本。

### 2026-09-07 批处理验证补充

下文旧版本和连接记录属于历史快照。当前 EffectDemo 2022 包清单为 URP 14.0.12，本次隔离执行实际使用 2022.3.62f3c1；CLI 安装表中对应版本键为 `2022.3.62f3`（不带 c1），旧 2022.3.16f1 可执行文件已不存在。调用工具必须显式提供实际 Editor 路径，不自动升级用户打开的项目。

Windows 精简子进程环境可能没有 `ALLUSERSPROFILE`，导致 UPM 报 `The "path" argument must be of type string. Received undefined`。本次确认异常发生在 UPM 全局配置路径，不是工程路径或包解析本身。EffectDemo 的 8 个执行脚本统一通过 `effectdemo_unity_process.ps1` 启动：仅在缺失时读取 Windows CommonApplicationData 补齐，结束后恢复原进程值，不修改机器/用户环境配置。

禁止把 `-NoUpm` 当成 URP 的正常恢复手段。捕获验证必须同时检查实际 `render_pipeline_instance_type`、`render_pipeline_verified`、帧有效性和动态材质限制；配置中的 `UniversalRenderPipelineAsset` 不能代替运行实例证据。管线不匹配截图保留诊断用途，不进入图像或完整视觉训练。

本次正常 URP 连续帧和故意管线不匹配反例见 `workspace/data/vfx_generation/generated/prompt_execution_regression_urp_r002/`，根因与失败尝试见 `ERR-VFXPIPELINE-001`。

本工作区有两条可并行运行的 Unity CLI 制作管线：

| 项目 | Editor | 渲染管线 | Pipeline 端口 |
|---|---|---|---|
| `UnityDemo/EffectDemo` | `2022.3.16f1c1` | URP `14.0.9` | `7801` |
| `UnityDemo/EffectDemo6.0` | `6000.5.9f1` | URP `17.5.0` | `7800` |

启动时必须显式选择匹配的项目和 Editor：

```powershell
unity open "E:/Unity特效人工智能学习/UnityDemo/EffectDemo" --editor-version 2022.3.16f1
unity open "E:/Unity特效人工智能学习/UnityDemo/EffectDemo6.0" --editor-version 6000.5.9f1
```

两个项目可以同时打开，但不能共用 `Library/`、`Temp/`、日志、端口或命令目标。
2022 项目的 Pipeline 适配、DLL `.meta` 兼容和专用命令见 [EffectDemo 2022 Unity CLI 接入指南](EffectDemo%202022%20Unity%20CLI接入指南.md)。

## 认证与诊断

```bash
unity auth status
unity doctor
```

需要登录、服务账号或许可证时，先检查认证状态和诊断输出。无头 CI 使用服务账号环境变量；交互式登录和许可证激活由用户在 Unity Hub/CLI 中完成。禁止通过修改许可证文件或绕过认证来运行项目。

## 构建与命令执行

构建和测试优先通过 CLI：

```bash
unity build --help
unity test --help
```

项目公开了 `[CliCommand]` 后，可以执行项目命令：

```bash
unity command <command-name>
unity command eval "return Application.version;"
unity command eval "return UnityEditor.EditorApplication.isPlaying;" --json
```

执行会改变场景、资源或项目设置的命令前，先读取当前状态，记录目标路径和预期结果；执行后再读取状态并保存证据。

## CLI 与 MCP 的分工

| 需求 | 默认工具 | 说明 |
|---|---|---|
| 检查项目结构 | Unity CLI | `unity projects verify` |
| 查看 Editor 和模块 | Unity CLI | `unity editors`, `unity modules` |
| 认证、诊断、许可证 | Unity CLI / Unity Hub | 需要用户授权时停止并报告 |
| 构建、测试、批处理命令 | Unity CLI | 统一退出码和日志 |
| 执行已注册 C# 命令 | Unity CLI | `unity command`, `eval`, `eval_file` |
| 查询或修改实时层级 | Unity MCP | CLI 未覆盖时使用 |
| 读取 Console、运行状态、截图 | Unity MCP 或 CLI Pipeline | 先验证实际能力 |
| 复杂 Editor 交互 | Unity MCP | 记录工具调用和限制 |

## 智能使用规则

AI 执行 Unity 相关任务时按以下顺序：

1. 识别任务是项目管理、结构检查、构建测试、Editor 命令还是实时交互。
2. 能用 CLI 完成的，优先使用 CLI。
3. 执行前读取项目版本、目标路径和认证状态。
4. 对会修改工程的命令先做可逆性判断并保留日志。
5. 执行后再次检查项目结构、输出文件、Console 和退出码。
6. CLI 不足时才启用 Unity MCP，并记录为什么需要 MCP。
7. 视觉质量、性能是否达标不能只由 CLI 或 MCP 判定，仍需运行结果和人工评估。

## 当前环境

- Unity 6 工程：`E:/UnityVFX/EffectDemo6.0`，Pipeline `7800`
- Unity 2022 工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`，Pipeline `7801`
- `UnityDemo/EffectDemo6.0` 是 Unity 6 源工程；`UnityDemo/EffectDemo` 是 Unity 2022 独立制作轨道

项目检查示例：

```bash
unity projects verify "E:/UnityVFX/EffectDemo6.0" --format json
```

已验证：
- `unity --help`、`unity editors --format json`、`unity doctor` 可用。
- Unity 账号认证状态为 OAuth 已登录。
- 两个制作工程均可通过 `unity projects verify`。
- Unity 2022 Pipeline Server 可在 `7801` 提供命令发现和实时命令执行。

按效果执行具体任务时，仍需补充该效果自己的场景、渲染和 Play Mode 视觉验证；这不影响两条 Pipeline 的连接和命令 authoring 能力。

许可证、账号或外部服务不可用时，实验必须标记为阻塞或 planned，不能仅凭 CLI 命令成功就标记为 verified。
