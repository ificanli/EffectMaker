# Beads 网页看板使用指南

本地网页看板：在浏览器中实时查看 Beads 任务和进度（类似 Redmine/TAPD 的轻量本地版）。

## 定位与架构

- **后端**：`workspace/tools/board_server.py`，纯标准库（`http.server` + `json`），零第三方依赖。
- **数据源**：每次请求调用 `bd list --all --format json` 拉取全量议题（含已关闭），解析后返回给页面。
- **前端**：单页 HTML（内嵌 CSS/JS），深色主题，固定 UTF-8。
- **刷新**：页面每 10 秒自动轮询 `/api/board`。

```text
浏览器 ──HTTP──▶ http.server ──▶ bd list --all --format json
  ▲ 每 10s 轮询                    │
  └────────────────────────────────┘
```

## 启动

```bash
# 方式一：启动脚本（自动打开浏览器）
workspace/board_server.bat        # Windows
./workspace/board_server.sh       # macOS / Linux / Git Bash

# 方式二：直接运行
python -m workspace.tools.board_server            # 默认端口 8611，自动打开浏览器
python -m workspace.tools.board_server --port 9000 --no-browser
```

启动后浏览器访问 `http://127.0.0.1:8611/`。按 `Ctrl+C` 停止。

## 页面功能

| 视图 | 说明 |
|------|------|
| 看板 | 按状态分列（待办 / 进行中 / 阻塞 / 延后 / 已完成），卡片显示标题、ID、优先级、所属系列，点击卡片打开详情弹窗 |
| 列表 | 表格视图，支持按状态 / 优先级 / 标签 / 文本搜索筛选，点击行打开详情 |
| 系列进度 | epic/系列聚合：已完成 N/总数、进度条、进行中的子任务，按 SRC 系列分组 |
| 详情弹窗 | 点击任意卡片/行打开：描述、验收标准、备注、标签、创建/开始/完成时间、依赖、评论数 |

页面右上角显示"更新于"时间；数据每 10 秒自动刷新。URL 加 `?noauth=1` 可暂停自动刷新（静态查看）。

## 修改任务

看板是**只读**的，不改动 Beads 数据库。修改任务请用命令行：

```bash
bd update <id> --status in_progress   # 标记进行中
bd close <id>                         # 完成
bd update <id> --priority 1           # 调整优先级
```

修改后 10 秒内看板自动反映。

## 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| 页面显示"刷新失败" | `bd` 不在 PATH，或 Beads 数据库异常 | 确认 `bd --version` 可用；Windows 下后端会自动解析 npm 全局目录的 `bd.cmd` |
| 端口被占用 | 8611 已被其他进程使用 | 用 `--port 9000` 换端口，或结束占用进程 |
| 中文乱码 | 页面固定 UTF-8，正常不会出现 | 若从旧工具生成的文件打开乱码，与本看板无关；看板输出均为 UTF-8 |
| 数据不更新 | 10 秒轮询被暂停（URL 带 `noauth=1`） | 去掉 URL 参数刷新 |

## 测试

```bash
python -m unittest workspace.tests.test_board_server -v
```
