# Unity CLI / MCP 能力验证清单

## 默认顺序

1. 使用 Unity CLI 检查环境、认证、Editor 和项目结构。
2. 使用 Unity CLI 执行项目命令、构建和测试。
3. CLI 无法覆盖时，才使用 Unity MCP 操作实时 Editor。
4. 通过 Unity 运行结果、日志和资源重载确认结果。

## Unity CLI

- [x] `unity --version` 可用。
- [x] `unity --help` 可用。
- [x] `unity editors --format json` 可用。
- [x] `unity doctor` 可用。
- [x] `unity projects verify <project> --format json` 可用。
- [ ] 使用 CLI 创建或打开验证工程。
- [ ] 使用 CLI 执行项目注册命令。
- [ ] 使用 CLI 构建和运行测试。
- [ ] 使用 CLI 完成 Editor license 激活。

## Unity MCP（补充桥接）

- [ ] 读取当前场景名称。
- [ ] 读取根对象和子对象层级。
- [ ] 读取对象的 Transform 和组件。
- [ ] 查询材质、粒子系统和预制体引用。
- [ ] 创建和修改 GameObject。
- [ ] 修改粒子、Trail、Light、Renderer 和材质参数。
- [ ] 进入 Play Mode 并读取运行状态。
- [ ] 获取截图和 Console 日志。
- [ ] 保存场景、预制体、材质和配置资源。

## 能力边界记录

每项失败或未使用的操作记录：

- 操作名称。
- 使用 CLI 还是 MCP。
- 失败表现和错误信息。
- 是否可以由 CLI、Editor 脚本或 MCP 替代。
- 是否需要预先创建模板资源。
- 当前推荐工作方式。

## 当前状态

Unity CLI 已安装并通过基础诊断。验证工程结构已通过 `unity projects verify`。Unity Editor 的实际运行和渲染验证仍受 license 激活状态影响；在 Editor 真正运行前，不把实验标记为 `verified`。
