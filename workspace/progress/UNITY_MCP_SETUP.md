# Unity MCP 安装与启动记录

## 已安装

- Unity MCP for Unity：`5.0.0`
- Unity 包路径：`workspace/unity-verification/Packages/com.coplaydev.unity-mcp`
- Python：`3.13.14`
- uv：`0.11.25`
- MCP 依赖约束：`mcp[cli]>=1.15.0,<2`
- 嵌入式 Server：`UnityMcpServer~/src/server.py`

## 已验证

命令：

```text
uv run --directory "workspace/unity-verification/Packages/com.coplaydev.unity-mcp/UnityMcpServer~/src" --python 3.13 python -c "from mcp.server.fastmcp import FastMCP; print('FastMCP_IMPORT_OK')"
```

结果：`FastMCP_IMPORT_OK`

Server 启动日志显示：

- 自动发现工具成功。
- 注册 `19` 个 Unity MCP 工具。
- 启动流程成功。

## 当前阻塞

Server 连接 Unity 时超时：

```text
Could not connect to Unity. Ensure the Unity Editor and MCP Bridge are running.
```

目标工程之前用 Unity `2021.3.29f1` batchmode 启动时，日志显示本机 license 无效，因此 Editor 没有真正启动。

## License 激活后启动

1. 用 Unity Hub 打开：

```text
E:/Unity特效人工智能学习/workspace/unity-verification
```

2. 在 Unity Editor 菜单打开：`Window > MCP for Unity`。
3. 执行 `Auto-Setup`，确认 `Start Bridge` 为运行状态。
4. 在 Git Bash 中启动 MCP Server：

```bash
uv run --directory 'workspace/unity-verification/Packages/com.coplaydev.unity-mcp/UnityMcpServer~/src' --python 3.13 server.py
```

5. 确认 `~/.unity-mcp/` 中出现该验证工程的端口/状态文件，并确认 project path 指向 `workspace/unity-verification`，而不是其他 Unity 项目。

只有 MCP Server 和目标 Editor 成功握手后，才能继续执行 `EXP-2026-002` 至 `EXP-2026-009` 并将结果推进为 `verified`。
