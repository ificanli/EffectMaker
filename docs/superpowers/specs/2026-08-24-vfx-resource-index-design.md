# VFX 本地资源混合索引设计

## 目标

为 `E:/Unity特效人工智能学习/resource` 建立只读、可增量更新、可追溯的本地资产索引。制作特效需要贴图、模型、材质或 Shader 时，先查询索引，再选择候选导入 Unity 工程。

## 当前规模

资源库约 22,223 个文件，主体为 PNG、TGA、DDS 和 FBX，同时包含 MAT、PSD、Shader、UnityPackage 和来源说明。目录已有刀光、火、冰、法阵、噪声、Mask、序列帧等分类，但大量文件名不可读或重复，授权状态不完整。

## 分阶段架构

### 第一阶段：结构化资产索引

扫描文件系统并输出：

- `workspace/data/resource_index/assets.sqlite3`
- `workspace/data/resource_index/assets.jsonl`
- `workspace/data/resource_index/thumbnails/`
- `workspace/data/resource_index/scan_summary.json`

每条资产记录包含稳定 ID、相对路径、类型、扩展名、大小、修改时间、SHA-256、目录标签、授权状态、图片尺寸/模式/通道、缩略图状态和错误信息。

SQLite 用于本地条件查询，JSONL 用于备份、RAG 摄取和外部工具交换。扫描以相对路径和文件状态为增量依据；内容哈希用于重复检测。原始资源目录不写入 `.meta`、缩略图或任何旁车文件。

### 第二阶段：视觉向量检索

对图片缩略图生成 CLIP/SigLIP 向量，支持自然语言和相似图片检索。向量结果必须与类型、目录标签、尺寸、授权状态联合过滤，不能单独决定资产可用性。

### 第三阶段：模型索引

提取 FBX/OBJ 的顶点、三角面、Bounds、UV、法线、顶点色、材质槽和动画信息，并生成多视图预览。模型检索使用结构化字段、目录标签和预览图向量组合；无法可靠解析的文件保留错误记录，不中断全库扫描。

## 第一阶段模块

- `workspace/tools/resource_index/models.py`：资产记录和扫描配置数据结构。
- `workspace/tools/resource_index/classify.py`：文件类型、路径标签和授权状态分类。
- `workspace/tools/resource_index/metadata.py`：哈希和图片元数据提取。
- `workspace/tools/resource_index/thumbnails.py`：PNG/JPG/TGA/DDS 等可读取图片的缩略图生成。
- `workspace/tools/resource_index/store.py`：SQLite schema、upsert、重复组和 JSONL 导出。
- `workspace/tools/resource_index/scanner.py`：只读遍历、增量扫描和汇总。
- `workspace/tools/resource_index/cli.py`：`scan`、`query`、`duplicates`、`stats` 命令。
- `workspace/tests/resource_index/`：标准库 unittest 测试。

## 分类规则

资产类型：`texture`、`model`、`material`、`shader`、`package`、`document`、`archive`、`other`。

路径标签由中英文目录词表规范化，例如：

- `刀光/daoguang/slash` → `slash`
- `火/fire/huo` → `fire`
- `冰/ice` → `ice`
- `法阵/magic_circle` → `magic-circle`
- `mask/遮罩` → `mask`
- `noise/噪声/niuqu/扰动` → `noise`、`distortion`
- `序列/sequence/flipbook` → `flipbook`

标签保留原始路径证据，不重命名原文件。

## 授权状态

授权状态是一等字段：

- `verified_internal`
- `verified_redistributable`
- `unknown`
- `restricted`
- `reference_only`

第一阶段默认 `unknown`。路径包含“免责声明”、商店页面、具体游戏名或来源不明素材包时，不自动升级授权；仅记录授权提示和相关说明文件。只有人工审核后的清单可以改变授权状态。

## 安全与性能

- 扫描器不修改、移动或删除 `resource/` 中任何文件。
- 不自动解压 ZIP/RAR/UnityPackage。
- 单文件读取错误写入索引，不终止扫描。
- 缩略图使用固定边长和独立输出目录，保持原图宽高比。
- SQLite 使用批量事务和索引；扫描可中断后重跑。
- SHA-256 首次扫描计算，未变更文件在增量扫描时复用。

## 查询接口

命令行至少支持：

```bash
python -m workspace.tools.resource_index.cli scan --root resource
python -m workspace.tools.resource_index.cli stats
python -m workspace.tools.resource_index.cli query --type texture --tag slash --license unknown --limit 20
python -m workspace.tools.resource_index.cli duplicates --limit 20
```

输出默认表格，可选 `--json`，返回相对路径、预览路径和关键元数据。

## 验收

- 测试夹具证明扫描不写原始资源目录。
- 可重复扫描并正确识别未变化、新增、更新和丢失文件。
- SQLite 与 JSONL 数量一致。
- 图片元数据和缩略图生成失败不会中断扫描。
- 可按类型、标签、尺寸和授权状态查询。
- 可按 SHA-256 列出重复内容。
- 全库扫描产生清晰汇总和错误统计。
