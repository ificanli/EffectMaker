# VFX 图片向量检索原型使用指南

## 范围与边界

该原型从本地 `resource/` 选取 64 张代表性纹理，使用 Transformers CLIP 生成图片向量，并用 NumPy 暴力计算余弦相似度。它不会上传素材，不使用 FAISS，也不会写入、移动或删除 `resource/` 中的文件。默认输出位于 `workspace/data/resource_vectors/prototype/`。

原型优先读取一期索引 `workspace/data/resource_index/assets.sqlite3`；数据库不可用或无有效记录时尝试 `assets.jsonl`，两者都不可用时直接按稳定路径扫描 PNG、JPG、JPEG、WEBP、BMP、TGA 和 DDS。超出样本上限时从稳定排序结果中等距取样，因此相同资源集合会得到相同清单。

## 环境

需要 Python、NumPy、Pillow、PyTorch 和 Transformers。可在适合当前平台的虚拟环境中安装原型依赖：

```bash
python -m pip install numpy pillow torch transformers
```

默认模型为 `openai/clip-vit-base-patch32`，默认 revision 为 `main`。模型版本和向量维度会写入 `manifest.json`。

工具默认只从本机 Transformers 缓存加载模型。若模型不在缓存中，命令会以退出码 `3` 和 `blocked:` 消息停止，不会隐式联网下载或输出 traceback。

只有在确认允许联网和下载后，才显式执行：

```bash
python -m workspace.tools.resource_vectors.cli build-sample --allow-model-download --json
```

也可通过 `--model` 指向本地模型目录，并用 `--revision` 固定版本。首次下载后，后续构建和检索不加 `--allow-model-download` 即采用本地离线加载。

## 构建 64 张样本

```bash
python -m workspace.tools.resource_vectors.cli build-sample --limit 64 --json
```

指定路径：

```bash
python -m workspace.tools.resource_vectors.cli build-sample \
  --root resource \
  --source-index workspace/data/resource_index \
  --output workspace/data/resource_vectors/prototype \
  --limit 64 \
  --json
```

即使模型不可用，确定后的 `sample.jsonl` 仍会保留，便于审核样本。模型可用时还会生成：

- `vectors.npy`：归一化后的 NumPy `float32` 图片向量。
- `metadata.jsonl`：与向量行一一对应的 `asset_id`、`relative_path` 和 `sha256`。
- `manifest.json`：格式版本、模型 ID、revision、维度、数量和构建时间。

重复构建时，模型 ID、revision 和文件 SHA-256 均未变化的向量会直接复用；内容哈希变化的文件才重新编码。

## 自然语言检索

```bash
python -m workspace.tools.resource_vectors.cli search-text "蓝色闪电拖尾" --limit 10
python -m workspace.tools.resource_vectors.cli search-text "blue lightning trail" --limit 10 --json
```

默认模型是英文 CLIP。CLI 会对常见中文 VFX 词汇做确定性规范化，例如“蓝色闪电拖尾，适合刀光”会补充为包含 `blue lightning trail slash VFX texture` 的英文提示。词表只覆盖常见颜色、刀光、闪电、拖尾、火焰、烟雾、冰、水、法阵、光环、爆点、噪声、扰动、溶解和 Mask 等术语，不是通用翻译器；未覆盖的中文查询仍可能需要手工补充英文关键词。

## 相似图片检索

查询图片只在本地读取，不会复制到输出目录或上传。可以传绝对路径、当前目录可访问路径，或相对于 `resource/` 的路径：

```bash
python -m workspace.tools.resource_vectors.cli search-image "FXTexture/米家FXTexture/Aura/Eff_Aura_000.tga" --limit 10
python -m workspace.tools.resource_vectors.cli search-image "E:/Unity特效人工智能学习/resource/path/to/query.png" --limit 10
python -m workspace.tools.resource_vectors.cli search-image "relative/query.png" --root "D:/custom-resource" --limit 10
```

相对路径始终按 `resource/` 根目录解析，并拒绝 `../` 越界；要查询资源库之外的本地图，必须显式传入绝对路径。不存在时会列出实际检查过的路径。

检索使用 NumPy 全量矩阵乘法计算余弦相似度，适合当前 50–100 张原型样本，不适合作为全资源库生产索引。

## 可重复性与限制

- `asset_id` 与一期一致：相对 POSIX 路径的 SHA-256；内容身份由文件 SHA-256 表示。
- 查询必须使用与索引相同的模型和 revision；CLI 默认从 `manifest.json` 读取构建时的值。
- 同分结果按 `asset_id` 排序，保证排序稳定。
- 本原型不处理授权判断。使用结果前仍须核对来源、许可证、格式兼容性和 Unity 导入设置。
- DDS/TGA 是否能编码取决于当前 Pillow 解码支持；无法解码会以清晰错误停止。
- 模型缓存、PyTorch/Transformers 版本及硬件实现可能造成细小浮点差异。
