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
unity project open "E:/path/to/project"
```

如果项目没有匹配的 Editor，再评估是否安装对应版本和模块。不要未经确认自动升级项目版本。

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

已验证：

- Unity CLI `1.0.0-beta.6` 已安装并在 PATH 中。
- `unity --help`、`unity editors --format json`、`unity doctor` 可用。
- Unity 账号认证状态为 OAuth 已登录。
- 验证工程已通过 `unity projects verify`。

尚未完成：

- 目标 Unity Editor 的有效许可证激活。
- 需要 Editor 实际运行的场景、渲染和 Play Mode 验证。

许可证、账号或外部服务不可用时，实验必须标记为阻塞或 planned，不能仅凭 CLI 命令成功就标记为 verified。
