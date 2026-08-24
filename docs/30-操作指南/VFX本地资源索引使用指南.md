# VFX 本地资源索引使用指南

## 适用范围

本工具以只读方式扫描仓库根目录下的 `resource/`，并把生成状态写入 `workspace/data/resource_index/`。扫描不会修改、移动或删除原始资源，也不会自动解压 ZIP、RAR 或 UnityPackage。授权状态默认是 `unknown`，本地存在不代表可以公开分发或用于商业项目。

## 初次扫描

在仓库根目录运行：

```bash
python -m workspace.tools.resource_index.cli scan
```

指定路径和输出目录：

```bash
python -m workspace.tools.resource_index.cli scan --root resource --output workspace/data/resource_index --json
```

扫描摘要会报告新增、修改、未变化、丢失、错误和缩略图统计。图片默认生成缩略图；只需要结构化元数据时可以关闭：

```bash
python -m workspace.tools.resource_index.cli scan --no-thumbnails
```

必要时使用 `--force-hash` 强制重新读取文件元数据并计算内容哈希：

```bash
python -m workspace.tools.resource_index.cli scan --force-hash
```

## 增量扫描

重复运行 `scan` 即可增量更新。文件路径、大小和修改时间未变化时会复用已有记录；新增和修改文件会重新提取元数据。源文件删除后，记录会保留在索引中并标记为 `missing`，便于追溯，不会删除源目录之外的索引历史。

建议在批量导入资源后运行一次扫描，并在资源目录发生整理或删除后再次运行。输出目录应始终位于 `workspace/data/resource_index/` 或其他与 `resource/` 不重叠的目录。

## 常用查询

查看索引统计：

```bash
python -m workspace.tools.resource_index.cli stats
python -m workspace.tools.resource_index.cli stats --json
```

查询刀光贴图：

```bash
python -m workspace.tools.resource_index.cli query --type texture --tag slash --limit 20
```

筛选尺寸和授权状态：

```bash
python -m workspace.tools.resource_index.cli query --type texture --min-width 512 --min-height 512 --license unknown --limit 20 --json
```

列出重复内容：

```bash
python -m workspace.tools.resource_index.cli duplicates --limit 20
python -m workspace.tools.resource_index.cli duplicates --json
```

`query` 支持 `--type`、`--tag`、`--license`、`--min-width`、`--min-height` 和 `--limit`。`stats`、`query`、`duplicates` 都支持 `--json`，适合脚本和后续 RAG 摄取。

## 输出布局

默认输出目录包含：

- `assets.sqlite3`：本地条件查询数据库。
- `assets.jsonl`：按相对路径稳定排序的备份和交换文件。
- `thumbnails/`：生成的图片缩略图，不写入 `resource/`。
- `scan_summary.json`：最近一次扫描的统计摘要。

索引记录包含稳定 ID、相对路径、资产类型、扩展名、大小、修改时间、SHA-256、路径标签、授权状态、图片尺寸和错误信息。

## 授权与使用提醒

授权状态需要人工审核。`unknown`、`restricted` 和 `reference_only` 记录不应直接进入公开发布包；使用前检查来源、许可证、版本、格式兼容性和 Unity 导入设置。索引只记录线索，不替代许可证或法务判断。

## 备份建议

定期备份 `assets.sqlite3`、`assets.jsonl` 和 `scan_summary.json`。若需要跨工具交换，优先使用 `assets.jsonl`；恢复查询能力时可保留 SQLite 文件。不要把未经审核的原始 `resource/` 内容复制到发布目录。

## 故障恢复

单个文件无法读取时，扫描会继续，并在记录的 `error` 字段和摘要的 `errors` 计数中保留原因。处理文件后重新运行扫描即可。

如果输出数据库损坏，先停止并备份现有 `workspace/data/resource_index/`，再移除或改名该输出目录后重新执行初次扫描。不要删除或修改 `resource/` 中的文件来解决索引故障。

如果命令提示扫描根目录不存在，使用 `--root` 指向实际资源目录；如果提示源目录和输出目录重叠，改用仓库工作区下的生成目录。
