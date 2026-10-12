# FBX/OBJ 几何索引与预览原型使用指南

## 目的与边界

该原型对本地 `resource/` 中少量 FBX/OBJ 文件做只读扫描，调用已安装的 Blender 5.0 headless 导入模型，提取几何元数据并生成 front、side、perspective 三个 PNG 预览。它是第三阶段小样本验证，不是 602 个模型的全量生产索引；不上传资源，也不改变源文件。

## 前置条件

- Python 3.11+，可从仓库根目录执行命令。
- Blender 5.0 可执行文件在 `PATH`，或通过 `--blender` 传入完整路径。
- 源资源目录可读。

## 构建样本

```bash
python -m workspace.tools.model_index.cli build-sample --root resource --output workspace/data/model_index --limit 5 --blender blender
```

恢复运行使用 `--resume`。资源按 POSIX 相对路径排序，`--limit` 在排序后截取；默认输出目录为 `workspace/data/model_index`。

## 输出

- `metadata.jsonl`: 每个模型一行。成功行包含 `vertex_count`、`polygon_count`、`triangle_count`、`bounds`、`uv_layer_count`、`has_vertex_colors`、`has_normals`、`material_slot_count`、`animation_count` 和 `previews`。
- `progress.jsonl`: 每个本次候选模型的 `ok`、`error` 或 `skipped` 状态。
- `manifest.json`: parser 版本、源根目录、限制和错误数。
- `checkpoint.json`: asset ID、内容 SHA-256、parser 版本和已生成元数据。只有内容哈希和 parser 版本都匹配时才会 resume 跳过。
- `previews/`: Blender 生成的三个 PNG 文件。

`asset_id` 是相对路径（统一为 POSIX 分隔符）的 SHA-256；`content_sha256` 是文件内容 SHA-256。错误会保留在 metadata 中并继续处理后续模型。

## 故障排查

Blender 返回非零退出码、无法导入或没有输出结果标记时，该模型记录为 `error`。检查 `metadata.jsonl` 的 `error` 字段和 Blender 路径；修复环境后重新运行即可。若模型内容改变，checkpoint 会自动失效并重新解析。

## 许可与安全

本工具只读取 `resource/`。本地存在不代表资源可以公开分发；使用或导出预览前仍需单独核查来源和授权。
