# Unity 制作错误日志

> 详细规范见 [错误沉淀与预防规范](../../docs/30-操作指南/错误沉淀与预防规范.md)。每条记录都必须保留原始错误和修复后的验证结果。

## ERR-UNITY-001

- 日期：2026-08-24
- 任务：`vfx-2zo.9`
- 工程：`workspace/unity-verification`
- 工具：Unity Editor batchmode
- 现象：Editor 退出但没有执行场景构建脚本。
- 原始错误：`Unity license information is invalid.`
- 根因：本机 Unity license 无效。
- 影响：不能生成场景，实验保持 planned。
- 修复：记录阻塞；安装并接入 Unity CLI；不绕过许可证。
- 验证：`unity projects verify` 可检查项目结构，但不替代 Editor 运行验证。
- 预防：开工前运行 `unity doctor`，授权问题先阻塞，不把退出码 0 当成成功。
- 状态：mitigated

## ERR-UNITY-002

- 日期：2026-08-24
- 任务：场景搭建
- 工程：`UnityDemo/EffectDemo6.0`
- 工具：Unity CLI / Git Bash
- 现象：使用 `/VFX_Verification/EffectRoot/Burst` 作为对象路径时，Unity 收到 `C:/Program Files/Git/VFX_Verification/...`。
- 根因：Git Bash 对以 `/` 开头的参数执行路径转换。
- 影响：第一次添加组件失败，工程未被修改。
- 修复：改用 Unity 返回的 `GlobalObjectId` 作为对象句柄。
- 验证：ParticleSystem 成功添加并读取。
- 预防：Pipeline 对象写操作优先使用 `GlobalObjectId`；层级路径不作为绝对 shell 路径传递。
- 状态：verified

## ERR-UNITY-003

- 日期：2026-08-24
- 任务：场景搭建/后处理
- 工具：Unity CLI / Pipeline
- 现象：调用 `read_console` 返回 Command Not Found。
- 根因：当前 Pipeline 版本命令名是 `get_console_logs`，不是 `read_console`。
- 影响：产生一次无效 Console 错误；未影响场景。
- 修复：使用 `unity command --tag editor --detail full` 查询实际命令，再调用 `get_console_logs`。
- 验证：成功读取 Unity Console。
- 预防：不凭 MCP 或旧版本记忆猜命令名；每次编译/版本变化后重新查询命令清单。
- 状态：verified

## ERR-UNITY-004

- 日期：2026-08-24
- 任务：烟花
- 工具：Unity CLI / Pipeline
- 现象：新增 Editor 脚本后命令未注册，或查询短暂连接旧端口。
- 根因：Unity 正在编译/域重载，Pipeline 服务在重启。
- 影响：命令查询失败；未执行写操作。
- 修复：等待 Editor 恢复后检查 `editor_status`，确认 `ready`、`compiling=false`、`domainReloadInProgress=false`，再重新发现命令。
- 验证：场景搭建和后处理命令在等待后恢复；烟花脚本仍需进一步处理。
- 预防：任何脚本或包变更后先等待并轮询 Editor 状态。
- 状态：mitigated

## ERR-UNITY-005

- 日期：2026-08-24
- 任务：Pipeline 安装
- 工具：Unity CLI
- 现象：对 `EffectDemo` 2022.3 工程安装 Pipeline 失败。
- 原始错误：`Pipeline 包需要 Unity 6.0 或更高版本。`
- 根因：目标工程版本为 `2022.3.16f1c1`。
- 影响：没有修改旧工程。
- 修复：确认实际目标是 `EffectDemo6.0`，版本 `6000.5.9f1`，再安装成功。
- 验证：`com.unity.pipeline 0.5.0-exp.1` 写入并在 PackageCache 解析。
- 预防：安装包前必须执行 `unity projects info`。
- 状态：verified

## ERR-UNITY-006

- 日期：2026-08-24
- 任务：游戏特效制作资料处理
- 工具：资料整理流程
- 现象：把视频核验、抽帧、知识卡片和实验方案误判为 Unity 实验完成。
- 根因：完成标准没有要求真实 Editor/Pipeline 运行证据。
- 影响：任务过早关闭，实验错误地保持或接近 verified。
- 修复：重新打开任务；建立 Unity 6 验证工程；只有真实运行、日志和资源状态满足条件才升级实验。
- 验证：场景搭建和后处理已在 `EffectDemo6.0` 真实运行并补充证据。
- 预防：`planned`/`experimental` 没有 Editor/Pipeline 证据不得关闭任务。
- 状态：verified

## ERR-UNITY-007

- 日期：2026-08-24
- 任务：Unity MCP/CLI 环境
- 工具：Unity MCP Server
- 现象：Python 3.14 解析到 `mcp 2.0.0`，`mcp.server.fastmcp` 导入失败。
- 根因：Unity MCP 5.0.0 源码依赖旧版 MCP API。
- 修复：安装 Python 3.13，固定 `mcp[cli]>=1.15.0,<2`。
- 验证：FastMCP 导入和 Server 工具注册成功。
- 预防：按嵌入式 `pyproject.toml` 和锁文件运行，不使用系统 Python 猜测依赖。
- 状态：verified
