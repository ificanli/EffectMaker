# Agent Instructions

## 工程介绍

这是一个 **Unity 游戏特效与 AI 辅助学习工程**。工程的目标不是让 AI 一次性生成一个孤立的特效，而是建立一套可以重复执行、可以验证、可以复盘、可以迁移的特效生产系统：

```text
需求输入
  -> 视觉拆解
  -> 技术选型
  -> Unity 制作
  -> 运行验证
  -> 视觉与工程评价
  -> 参数迭代
  -> 性能检查
  -> 资产和知识沉淀
```

### 要做什么

1. 学习并实践 Unity 粒子、Shader、Shader Graph、VFX Graph、Mesh、材质、Timeline、后处理和场景表现。
2. 把视频、文章、图片和案例拆成可定位的视觉证据、制作步骤、参数范围和限制条件。
3. 在 Unity 中复现和验证资料中的方法，不把作者口述或单张截图直接当成可靠结论。
4. 将经过验证的结果沉淀为预制体、材质、Shader、参数规范、检查清单、知识卡片和实验记录。
5. 使用 Unity CLI、测试和日志保证工程可检查；只有 CLI 覆盖不到的实时编辑器操作才使用 Unity MCP。

### 怎么做

资料按两条管道处理，并在 Unity 中交叉验证：

- **审美管道**：点评、赏析和参考作品 -> 记录问题帧、修改前后和动态节奏 -> 总结判断规则、失败模式和检查清单。
- **制作管道**：教程、实战和案例复刻 -> 记录操作顺序、Inspector/节点参数和依赖 -> 在 Unity 中复现并沉淀步骤模板。
- **交叉验证**：审美规则必须用实际复现检验；制作步骤必须用运行画面、截图、参数和性能数据检验。

每次制作都应留下以下最小证据：需求或目标、使用的资源和授权状态、Unity 版本与渲染管线、关键参数、验证场景、运行结果、截图或日志、已知限制和下一步改进。

### 推荐制作入口

当前推荐使用：

```text
UnityDemo/EffectDemo6.0/
```

该项目使用 Unity `6000.5.9f1` 和 URP `17.5.0`，已通过 Unity CLI 项目结构验证。`UnityDemo/EffectDemo/` 是 Unity 2022.3 的兼容项目；除非任务明确要求维护旧版本，否则不要把两个项目混用。

从远端拉取后，先用 Unity Hub 打开 `UnityDemo/EffectDemo6.0/`，等待 Unity 重新生成本地 `Library/`，再检查场景、包和资源。远端不包含下载的视频、音频、未经确认授权的 `resource/` 原始素材和本地缓存；需要使用这些内容时，先在本机准备并确认授权，不要强行提交到 Git。

### 目录职责

- `UnityDemo/`：Unity 项目源文件、场景、包清单、ProjectSettings 和可公开分发的工程配置。
- `workspace/tools/`：媒体处理、转写、资源索引、知识图谱和辅助 CLI。
- `workspace/tests/`：Python 工具和资源索引测试。
- `workspace/progress/`：验证日志、错误记录、阻塞说明和环境状态。
- `knowledge/sources/`：资料来源登记、引用链接、字幕、抽帧、视觉核对和处理状态；视频本体不提交。
- `knowledge/cards/`：经过证据和实践支持的可复用规则与制作知识。
- `knowledge/experiments/`：Unity 复现实验、参数记录、结果和差异说明。
- `docs/`：稳定的项目原则、参考规范、操作指南、教程和模板。
- `resource/`：本地资源库，不因存在于工作区就默认具有公开分发授权；默认不上传。

### 开工顺序

1. 阅读本文件、`README.md`、相关操作指南和 `workspace/progress/ERROR_LOG.md`。
2. 用 Beads 查看任务状态和依赖，认领当前任务；阶段结论和弯路必须写回任务记录。
3. 明确需求、目标画面、交付物、Unity 版本、渲染管线、资源授权和验证标准。
4. 先建立或确认最小 Unity 场景，再逐层制作：形体 -> 材质/Shader -> 粒子或 VFX Graph -> 动画/节奏 -> 场景与后处理。
5. 用 Unity CLI 做项目检查、构建或测试；需要实时编辑器操作时记录 Unity MCP 的原因、调用和结果。
6. 运行并观察真实画面，保存截图、日志、参数和性能数据；不能只以 CLI 成功作为视觉完成标准。
7. 将结论写入实验、知识卡片或文档，并按 Git 忽略规则检查视频、缓存、密钥、超大文件和授权不明素材。

## Unity 工具规则

本工程默认使用 Unity 官方 CLI（当前验证版本 `1.0.0-beta.6`）执行 Unity 相关工作：项目检查、Editor/模块管理、认证诊断、构建、测试和注册命令。能由 CLI 完成的操作必须优先使用 CLI。

常用检查命令：

```bash
unity --version
unity doctor
unity editors --format json
unity projects verify "<project-path>" --format json
```

只有 CLI 不覆盖的实时 Unity Editor 操作，才使用 Unity MCP；使用 MCP 时必须记录原因、工具调用和结果。Unity CLI、MCP 或 Editor 命令成功不等于视觉效果验证完成，必须保留运行日志、资源状态和人工质量判断。许可证、账号和外部服务需要用户授权时，不得绕过。

详细规则见 [Unity CLI 使用指南](docs/30-操作指南/Unity CLI使用指南.md)、[错误沉淀与预防规范](docs/30-操作指南/错误沉淀与预防规范.md) 和 [AI、Unity CLI 与 Unity MCP 工作边界](docs/10-解释/AI与Unity-MCP工作边界.md)。

所有 Unity 制作错误必须记录原始命令、错误文本、根因、修复、复验和预防措施；开工前先检索 `workspace/progress/ERROR_LOG.md`，同类错误不得重复犯。

## 强制工作记录规则（必遵守）

创建、关闭和更新 Beads 任务时，必须通过守卫命令 `bdg`（`workspace/bdg.bat` / `workspace/bdg.sh` / `python -m workspace.tools.bd_guard`），**不要直接调用 `bd create` / `bd close` / `bd update` 写操作**。`bdg` 会强制校验：

- `bdg create`：必须带 `--description`（做什么）、`--acceptance`（验收标准）、`--notes`（阶段/弯路记录），缺任一拒绝创建。
- `bdg close`：必须带 `--reason`（关闭原因/完成结论），缺则拒绝关闭。
- `bdg close --require-notes`：额外要求任务已有结论性记录（备注/评论含"完成/产出/沉淀/弯路/结果/记录"且长度足够），否则拒绝关闭。

**阶段与弯路记录（必须做）**：
- 每完成一个阶段，用 `bdg note <id> "阶段结论；弯路：..."` 追加备注；交流讨论用 `bdg comment`。
- 弯路必记录：试了什么 → 为什么不行 → 改成什么 → 结果。格式见 [工作记录强制规范](docs/30-操作指南/工作记录强制规范.md)。
- 关闭前必须先有结论记录，再 `bdg close --require-notes`。

**定期检查**：用 `bdg guard-check` 扫描不合规任务（缺验收/closed 无结论），发现即补。带 `legacy` 标签的历史任务豁免，新任务从创建起强制。

完整规范见 [工作记录强制规范](docs/30-操作指南/工作记录强制规范.md)。

This project uses **bd** (beads) for issue tracking. Run `bd prime` for full workflow context.

> **Architecture in one line:** Issues live in a local Dolt database
> (`.beads/dolt/`); cross-machine sync uses `bd dolt push/pull` (a
> git-compatible protocol), stored under `refs/dolt/data` on your git
> remote — separate from `refs/heads/*` where your code lives.
> `.beads/issues.jsonl` is a passive export, not the wire protocol.
>
> See [SYNC_CONCEPTS.md](https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md)
> for the one-screen overview and anti-patterns (don't treat JSONL as the
> source of truth; don't `bd import` during normal operation; don't
> reach for third-party Dolt hosting before trying the default).

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bdg create "标题" --description "..." --acceptance "..." --notes "..."  # 创建（强制三字段）
bdg note <id> "阶段结论/弯路"   # 追加阶段记录（必须做）
bdg close <id> --reason "完成：..." --require-notes   # 关闭（强制 reason + 结论）
bdg guard-check       # 扫描不合规任务
bd dolt push          # Push beads data to remote
```

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bdg claim <id>          # Claim work (guarded write)
bdg close <id> --reason "完成：..." --require-notes  # Complete work (guarded)
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files
- **Write operations (`create`/`close`/`update`) must go through `bdg`** (workspace/bdg.bat / bdg.sh), which enforces description/acceptance/notes on create and reason/conclusion on close. See [工作记录强制规范](docs/30-操作指南/工作记录强制规范.md).

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bdg create "标题" --description "..." --acceptance "..." --notes "..."  # 创建（强制三字段）
bdg note <id> "阶段结论/弯路"   # 追加阶段记录
bdg close <id> --reason "完成：..." --require-notes   # 关闭（强制 reason + 结论）
bdg guard-check         # 扫描不合规任务
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.
- **Write operations (`create`/`close`/`update`) must go through `bdg`** (workspace/bdg.bat / bdg.sh). See [工作记录强制规范](docs/30-操作指南/工作记录强制规范.md).

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->
