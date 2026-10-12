# VFX 资源三期增量维护指南

## 目标

资源系统分为三层，均采用一次建设、后续增量处理：

```text
第一期：文件、Hash、图片元数据、标签、SQLite/JSONL、缩略图
第二期：图片 CLIP 向量、自然语言检索、相似图片检索
第三期：FBX/OBJ 几何元数据、三视角预览、模型检索基础
```

原始资源目录始终只读：

```text
E:\Unity特效人工智能学习\resource
```

## 新资源日常流程

批量放入新资源后执行一次第一期增量扫描：

```cmd
cd /d "E:\Unity特效人工智能学习"
python -m workspace.tools.resource_index.cli scan --root resource --output workspace\data\resource_index --json
```

扫描通过后：

- 新图片进入第二期 `build-all`，旧 Hash 自动复用。
- 新 FBX/OBJ 进入第三期模型构建，旧内容 Hash 和解析器版本自动复用。
- 删除文件在第一期标记为 `missing`；向量和模型索引后续按 metadata 清理或重建。

## 第二期图片向量增量

```cmd
python -m workspace.tools.resource_vectors.cli build-all ^
  --root resource ^
  --source-index workspace\data\resource_index ^
  --output workspace\data\resource_vectors\full ^
  --batch-size 32 ^
  --json
```

规则：

- 使用 `openai/clip-vit-base-patch32@main`。
- checkpoint 由内容 SHA-256、模型 ID 和 revision 决定。
- 中断后重复同一命令会续跑。
- 禁止两个 `build-all` 同时写同一输出目录。
- 单图失败写入 `progress.jsonl`，不终止全量任务。
- CPU 全量编码耗时较长；后续可切换匹配 RTX 3060 的 CUDA PyTorch，但模型和 revision 必须保持一致。

查询：

```cmd
python -m workspace.tools.resource_vectors.cli search-text "蓝色闪电拖尾，适合刀光" --output workspace\data\resource_vectors\full --limit 10
python -m workspace.tools.resource_vectors.cli search-image "FXTexture/米家FXTexture/Aura/Eff_Aura_000.tga" --root resource --output workspace\data\resource_vectors\full --limit 10
```

## 第三期模型几何与预览增量

当前后端：

```text
C:\Program Files\Blender Foundation\Blender 5.0\blender.exe
```

小样本命令：

```cmd
python -m workspace.tools.model_index.cli build-sample ^
  --root resource ^
  --output workspace\data\model_index ^
  --limit 5 ^
  --blender "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" ^
  --resume
```

提取：

- 顶点数、polygon 数、三角形数。
- world/transformed Bounds。
- UV 层、顶点色、法线。
- 材质槽和动画数量。
- front、side、perspective 三张预览。

规则：

- 预览使用 `asset_id` 独立目录，避免同名模型覆盖。
- Blender 单模型默认超时 300 秒；超时会终止/杀死子进程并记录错误。
- JSONL 使用临时文件、`fsync` 和原子替换。
- content Hash 或 parser version 未变化时复用 checkpoint。
- 不可解析模型保留错误记录，禁止伪造几何数据。

## 并发规则

可以并行：

- 第二期读取第一期已稳定 SQLite，同时做 Unity 制作。
- 第三期读取 `resource`，同时做 Unity 制作。
- 查询向量索引，同时做只读文档工作。

不要并行：

- 两个第一期扫描同时写 `assets.sqlite3`。
- 两个第二期 `build-all` 同时写 `resource_vectors/full`。
- 两个第三期任务同时写同一个 `model_index` 输出目录。
- 两个 Unity CLI 窗口同时修改同一个 Editor；写操作必须串行。

## 授权与使用

所有索引条目默认 `license_status=unknown`。索引、向量相似度和模型预览只说明“资源可能适合”，不代表允许公开分发。资源进入对外项目前必须人工检查来源、作者、授权和依赖。
