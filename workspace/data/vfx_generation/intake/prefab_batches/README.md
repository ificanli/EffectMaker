# 千级 Prefab 训练资源入口

这里保存批次登记信息，不保存原始 Unity 项目、视频、贴图包或未经确认授权的资源本体。

准备一批 Prefab 时，优先保持它们所在的原 Unity 工程不变。每批至少提供：

- 原 Unity 工程绝对路径；
- 一个或多个 `Assets/` 下的 Prefab 根目录；
- Unity 版本和渲染管线；
- 资源所有权或本地训练授权状态；
- 批次名称和大致特效族；
- 是否依赖角色、UI、Timeline、业务脚本或战斗上下文。

使用 `prefab_batch.template.json` 建立批次登记。原始资源建议放在独立 Unity 工程中，例如：

```text
E:/TrainingSources/VFX_Project_A/
E:/TrainingSources/VFX_Project_B/
```

不要直接把上千个 Prefab 散放到 `workspace/data/`。实际摄入仍由 `workspace.tools.vfx_source_ingest` 执行，并保留：

- Prefab 依赖闭包；
- Material / Texture / Mesh / Shader 的 `.meta` GUID；
- Shader 本地 `#include` 链；
- ShaderGUI 授权和可用状态；
- 源工程、源路径、Unity 版本和授权状态；
- 未复制脚本和上下文依赖的明确记录。

摄入完成后，将生成的 `source_manifest.json` 目录交给：

```powershell
python -m workspace.tools.vfx_generation.vfx_prefab_corpus `
  --input workspace/data/vfx_generation/sources `
  --output-dir workspace/data/vfx_generation/corpora/<corpus-id> `
  --corpus-id <corpus-id> `
  --previous-manifest workspace/data/vfx_generation/corpora/<previous-id>/corpus_manifest.json
```

该命令只建立索引、增量状态和防泄漏切分，不复制或修改 Unity 资产。新资源在完成 Unity 运行、连续帧和人工 Prompt 条件评价前，只能进入结构监督，不能进入正向生成或偏好训练。
