# 单集视频学习标准作业流程（SOP）

> 基于第一集 `SRC-2026-001` 的完整经验总结。后续每集按此流程执行。

---

## 阶段一：准备

### 1.1 确认视频可用

```bash
python -m yt_dlp --dump-single-json --skip-download --no-warnings <URL>
```

记录：标题、时长、作者、BV 号、可用格式、是否有字幕/章节。

### 1.2 下载视频

```bash
python -m yt_dlp --format "30064+30280/bestvideo+bestaudio/best" \
  --merge-output-format mp4 \
  --output "<output_dir>/%(id)s_%(title)s.%(ext)s" \
  <URL>
```

- 优先 `720p AVC + AAC`，格式不可用时降级为 `bestvideo+bestaudio/best`。
- 启用 `--download-archive` 防重复。
- 启用 `--continue` 支持断点续传。
- 下载完成后使用统一媒体工具读取并保存元数据：

```bash
python -m workspace.tools.media_cli probe "<video_path>" --output "<source_dir>/media_meta.json"
```

`media_meta.json` 至少记录容器格式、时长、视频分辨率、FPS、编码，以及音频编码、采样率和声道数。FFmpeg/ffprobe 的路径由 `VFX_FFMPEG`、`VFX_FFPROBE` 环境变量、系统 `PATH` 和本机已知安装路径依次解析，不在每个脚本中单独配置。

### 1.3 建立资料目录

```text
knowledge/sources/<SRC-ID>/
  source.md              # 来源登记
  *.mp4                  # 视频文件
  media_meta.json        # ffprobe 标准化元数据
  transcript_*.srt       # 时间戳转写
  audio/                 # 统一工具提取的音频
  audio_segments/        # 音频时间片段
  storyboard.jpg         # 时间轴预览
  frames/                # 低密度抽帧（每 N 分钟）
  visual/                # 关键帧证据页
  clips/                 # 关键案例视频片段
  visual_review_front.md # 前段视觉核对
  visual_review_middle.md # 中段视觉核对
  visual_review_back.md  # 后段视觉核对
  objective_metrics.csv  # 客观指标
```

## 阶段二：音频/字幕分析

### 2.1 提取音频并生成时间戳转写

先使用统一媒体工具生成 16 kHz、单声道 WAV；长音频按时间区间切片后再转写：

```bash
python -m workspace.tools.media_cli audio "<video_path>" "<source_dir>/audio/<slug>_16k_mono.wav"
python -m workspace.tools.media_cli cut-audio \
  "<source_dir>/audio/<slug>_16k_mono.wav" 0 600 \
  "<source_dir>/audio_segments/<slug>_00000-00600.wav"
```

```python
from faster_whisper import WhisperModel
model = WhisperModel('base', device='cpu', compute_type='int8')
segments, info = model.transcribe(str(audio_segment), language='zh', vad_filter=True, beam_size=5)
```

- 语言：中文，beam_size=5。
- 输出：标准 SRT 格式。
- 保存路径：`transcript_base.srt`。
- 记录语言识别概率。

### 2.2 字幕初稿提取

- 逐案例记录口述。
- 标记不确定术语。
- 按主题区间分组。
- **此步骤的结论只作为"候选知识"，不作为已确认规则。**

## 阶段三：视觉证据生成

### 3.1 时间轴预览

统一媒体工具负责单帧抽取和时间区间操作；批量联系图脚本仍可使用 FFmpeg 生成图集：

```bash
python -m workspace.tools.media_cli frame "<video_path>" 12.5 "frames/00-00-12.jpg"
ffmpeg -i video.mp4 -vf "fps=1/300,scale=320:-1,tile=3x5" -frames:v 1 storyboard.jpg
```

用于整体把握视频结构。

### 3.2 关键时间点抽帧

根据字幕分组确定关键案例，在每个案例区间内抽取：

- 案例开始前一帧
- 作者描述问题时的一帧
- 修改前状态一帧
- 修改后状态一帧
- 爆发/峰值一帧
- 收尾/残影一帧

```bash
python -m workspace.tools.media_cli frame "<video_path>" <time> "<output>.jpg"
```

需要保留动态证据时，直接导出案例时间片段：

```bash
python -m workspace.tools.media_cli cut-video \
  "<video_path>" <start> <end> "clips/<case_id>.mp4"
```

### 3.3 分段密集抽帧

将视频分为 3 段（前 1/3、中 1/3、后 1/3），每段按 2 秒间隔生成密集联系图。联系图可继续用 FFmpeg 批处理；需要保留可回放证据时，使用 `cut-video` 导出对应片段到 `clips/`。

### 3.4 编码标准化

确保所有帧使用标准 JFIF JPEG：

```python
from PIL import Image
im = Image.open(p).convert('RGB')
im.save(output, 'JPEG', quality=92, subsampling=0, progressive=False)
```

### 3.5 生成视觉证据页

创建 HTML 页面，按网格展示所有关键帧和联系图，标注时间戳和案例标签。用本地 HTTP 服务提供浏览。

```python
python -m http.server 8765 --directory "<workspace>"
```

## 阶段四：视觉核对

### 4.1 核心原则

- 必须实际观察画面，不能只看字幕。
- 每个案例至少记录：口述、画面实际、动态过程、前后差异、支持等级。
- 观察不到就说"待复核"，不能用字幕推断。
- 字幕中的"讲了什么"和画面中的"展示了什么"必须分开记录。

### 4.2 逐案例检查清单

每个案例检查以下维度：

| 维度 | 说明 |
|---|---|
| 形状 | 轮廓、核心、宽窄、是否有明确主体 |
| 运动 | 方向、速度、加速度、旋转、衰减 |
| 材质 | 透明度、流动、边缘、噪声、扭曲 |
| 颜色 | 主色、辅助色、亮度峰值、前后统一 |
| 节奏 | 前摇、爆发、持续、收尾 |
| 空间 | 前后、内外、包裹、接触、角色可读性 |
| 属性 | 画面是否真正像目标属性（火/冰/雷/水等） |

### 4.3 支持等级

- **明确支持**：口述与画面完全一致，有前后帧证据。
- **基本支持**：方向一致但细节不完整。
- **部分支持**：主要问题成立，但某些判断无法从画面确认。
- **不支持**：画面明确与口述矛盾。
- **待复核**：观察条件不足，不能下结论。

### 4.4 分段视觉核对

- 前段：使用真实画面观察（浏览器证据页 + 截图）。
- 中段：使用真实画面观察。
- 后段：真实画面观察优先；若图像回传受限，辅以客观指标（亮度、饱和度、边缘密度、主色、亮区偏移），明确标注"客观指标分析，视觉语义待补充"。

## 阶段五：客观指标辅助（可选）

当视觉通道受限时，用 OpenCV 对每帧计算：

- 平均亮度、最大亮度、热区占比
- 平均饱和度
- 边缘密度
- 对比度
- 亮区偏移（距离画面中心的 x/y 偏移）
- 主色聚类

生成 `objective_metrics.csv`，用于辅助判断：

- 亮度变化：是否有爆发、衰减
- 饱和度变化：是否有色彩切换
- 边缘密度：是否有轮廓变化
- 亮区偏移：效果是否在移动
- 主色：是否有多组不同属性

客观指标**不能替代**语义视觉观察。

## 阶段六：知识沉淀

### 6.1 逐案例视觉记录

每段核对结果保存为独立文件：

```text
visual_review_front.md     # 前段
visual_review_middle.md    # 中段
visual_review_back.md      # 后段
```

每个案例包含：时间段、口述、画面实际、动态差异、支持等级、证据路径、不确定性。

### 6.2 规则沉淀

从已确认的案例中提炼可复用规则，写入知识卡片。规则必须标注：

- 来源视频和时间戳
- 画面是否支持
- Unity 验证方案
- 适用范围和限制

### 6.3 Unity 对照实验

设计最小对照实验，每次只改变一个变量。实验结果未出之前，规则保持 `experimental` 状态。

## 阶段七：质量关卡

每集完成前必须通过：

- [ ] 转写覆盖全片
- [ ] 关键帧和联系图覆盖所有案例
- [ ] 至少一段完成真实画面观察
- [ ] 每个案例有明确的支持等级
- [ ] 已确认的规则有画面证据支持
- [ ] 未确认的内容标记为"待复核"
- [ ] 客观指标分析完成（若画面观察受限）
- [ ] 知识卡片更新
- [ ] Unity 实验方案制定
- [ ] 所有文件归档到正确目录

## 常见问题

### Q: 视频没有字幕怎么办？
用 faster-whisper 生成中文时间戳转写。专业术语标记不确定性，后续通过画面复核。

### Q: 视频有多个 P 分集怎么办？
按 P 分集独立下载，每集独立编号和分析。

### Q: 格式不可用怎么办？
降级为 `bestvideo+bestaudio/best`。记录实际格式，后续分析时注明画质差异。

### Q: 图像无法被读取怎么办？
1. 检查编码是否标准 JFIF JPEG。
2. 检查路径是否有中文字符。
3. 生成 ASCII 短路径副本。
4. 如果以上均失败，使用客观指标辅助分析，明确标注限制。
5. 在视觉通道恢复前，不把字幕结论升级为已确认规则。

### Q: 集数太长怎么办？
分为 3 段，每段独立处理。若单段仍过长，按案例再细分。但每段必须有至少一个完整视觉核对。
