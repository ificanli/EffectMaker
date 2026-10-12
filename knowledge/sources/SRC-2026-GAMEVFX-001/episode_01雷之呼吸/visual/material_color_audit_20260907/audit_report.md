# Part03 贴图、黑白闪动与 Mask 局部证据审计

日期：2026-09-07。对象：SRC-2026-GAMEVFX-001 / episode_01雷之呼吸 / Part03。

## 1. 结论与边界

本次完成的是三个指定窗口的局部视频证据核对，未操作 Unity，也未验证当前工程的编译器或颜色修复。以下结论来自本次实际打开查看的原分辨率帧、联系图和连续视频帧，并与既有字幕及 ProcedureSpec 对照。

- **354–397 秒的复制、反相、最小值滤镜和自由变换发生在 Photoshop。** 这些是贴图制作操作，不能直接证明教程创建了名为 OutlineVariation 的独立 Unity 粒子层。
- **Color over Lifetime 的 Fixed 模式和黑白分段有直接画面证据。** 连续帧中出现亮白形体、可见黑色形体、再亮起的变化，不能把它简化成仅调 Alpha 让粒子消失。
- **Mask 操作针对另一个已存在的 Unity 对象。** 1518–1550 秒选中的是 qi (1)，材质为 trail002；前面闪电的 Renderer 材质为 lightning001。Mask 证据不能无条件归入 MainBolt。
- **Mask 的灰度外观、贴图选择和材质绑定可见，Shader 内部取样通道不可见。** 选择器显示 RGB 格式的 fx_mask_010，不能据此宣称使用纹理 A 通道、Alpha Test 或某个确定的裁切阈值。
- **可读 Inspector 值只能作为指定时刻的源教程快照。** 它们不是完整最终配置，也不等于当前工程可直接套用的参数。

仅向本目录新增报告及图像证据。未修改 Unity 代码、ProcedureSpec JSON、其他报告或 Beads；未执行 Git 操作，未改索引、分支或提交；未下载或上传媒体。图片继承原教程的来源与授权边界，仅作本地证据，不代表已取得再分发许可。

## 2. 输入与取证方法

### 输入快照

| 输入 | 路径或信息 |
|---|---|
| 本地原视频 | knowledge/sources/SRC-2026-GAMEVFX-001/videos/03_BV1w14y1B7W7_p3_零基础补足计划08-雷之呼吸01案例分析 p03 20230813雷之呼吸03闪电制作.mp4 |
| 视频参数 | H.264，1280×720，标称 30 fps；视频流 1600.299 秒，容器 1600.362333 秒；59,056,813 字节 |
| 视频 SHA-256 | 9A5D51BFB2E80F7C6A7727A345B33A008BCFC83DDE69247F7AE2AD058F359518 |
| 既有字幕 | knowledge/sources/SRC-2026-GAMEVFX-001/episode_01雷之呼吸/transcripts/part03.zh.srt |
| 字幕 SHA-256 | BAF7CF14C3FBFA7C5C1182DB50E5DF5B5F381EF8EE1A6DD532AD2DF09143DC90 |
| 对照流程 | workspace/data/vfx_generation/procedures/procedure_lightning_shape_lifecycle_r001/procedure_spec.json |
| ProcedureSpec SHA-256 | E2C31085368ECA9C7DC740E89C82B78B71F4909DD71A3E211AC13D256FB60018 |

字幕按空行分块、编号和十进制秒起止时间解析，共识别 854 个字幕块。00354.59 解释为 **354.59 秒，即 05:54.59**，不是常规时分秒字符串。下面引用字幕编号和原始秒数；已有自动转写中的错词保留在引文中，校正另行说明。未重新转写或听音核实。

使用本机既有 FFmpeg 9.0.1、ffprobe、Pillow 12.3.0 和 workspace/tools/media.py 中的工具路径解析函数。未安装依赖，Python 使用 -B 禁止生成字节码缓存。单帧以准确 seek 解码、-copyts 保留时间、showinfo 核对 PTS，PNG 不缩放。20 张单帧均为原视频分辨率 1280×720；“全分辨率”不意味着恢复录屏压缩前的界面细节。

单帧命令结构如下，实际源文件与输出路径均为本地绝对路径；-n 防止覆盖已有单帧：

    ffmpeg -hide_banner -loglevel info -nostdin -ss <seconds> -copyts -i <source.mp4>
      -map 0:v:0 -frames:v 1 -an -vf showinfo -fps_mode passthrough
      -f image2 -update 1 -n <frame.png>

联系图采用 FFmpeg 解码后在内存中合成，不留下额外脚本、临时视频或 JSON。总览每格缩到 400×225；细节图只做标明倍率的最近邻放大，不使用生成式修复、锐化补字或 OCR 推测。902 秒序列一次顺序解码连续 24 帧，未用稀疏 seek 冒充连续帧。

### 覆盖范围

| 范围 | 实际检查方式 | 能支持的范围 |
|---|---|---|
| 333–397 秒 / 05:33–06:37 | 每 4 秒抽一帧，共 17 格；另看 6 张原分辨率关键帧 | Photoshop 形状、图层、滤镜、变换操作的状态变化 |
| 811–965 秒 / 13:31–16:05 | 从 811 到 963 秒每 8 秒抽样，另含 965 秒，共 21 格；另看 10 张原分辨率关键帧 | 生命周期、发射、大小、渐变编辑及预览状态 |
| 902.000–902.767 秒 | 连续 24 帧，约 30 fps；逐格检查 Game 视图裁切 | 短时间内亮、黑、灰蓝、再亮的实际图像变化 |
| 930–949 秒 | 每秒一帧，共 20 格；保留 Game 视图和 Particle Effect 播放字段 | 作者手动查看不同预览时刻时的亮段、黑段及返回亮段 |
| 1518–1550 秒 / 25:18–25:50 | 每 2 秒抽一帧，共 17 格；另看 4 张原分辨率关键帧 | 对象、材质、Mask 选择/绑定及后续 TEX02 参数 |

三个主窗口合计 250 秒，但仅按上述采样及短连续序列检查，**没有逐帧覆盖全部 250 秒**。未检查 Part03 的其余部分、其他分 P、源纹理文件或 Shader 代码；不据此宣称学完整套教程或完成专业复刻。20 张全帧和联系图存在重复时间点，不能相加当作额外覆盖。

## 3. Photoshop 形体与轮廓操作

| 时间 / 字幕 | 画面观察 | 判断 |
|---|---|---|
| 333–353 秒；#82 337.35–340.71“黑线 钩边”；#83–86“光柱”“锐辩” | Photoshop 画布有四个纵向闪电形状；其间调出参考图片，353 秒回到白底黑色实心形状。[全帧 353](frame_353.000s.png) | “黑线勾边、光柱、锐边”属于参考分析。此处没有创建 Unity 发光层，也没有设置 emission 的画面。 |
| #88 354.59–356.83“复制一层”；#91 359.63–361.11“抗日加i 反转” | 353 秒图层面板只有图层 1 与背景；361 秒多了图层 1 拷贝，主体显示为很细的轮廓，屏幕按键提示为 Ctrl+i。[全帧 361](frame_361.000s.png) | 可以将转写错词校正为 Ctrl+I 反相。这是像素颜色反相，不是空间翻转、Unity 旋转或复制粒子系统。 |
| #92–98 361.43–380.76；#95“点绿件 点最小值” | 369 秒打开 Photoshop 滤镜菜单；377 秒出现标题“最小值”的对话框，轮廓明显加粗。[菜单](frame_369.000s.png) / [滤镜](frame_377.000s.png) | 支持“滤镜 -> 其他 -> 最小值”用于扩大黑边。377 秒输入框可读为半径 4 像素，是操作中的快照；字幕 #97 单独的“3”不能当成最终值。 |
| #100 384.44–385.72“抗日加替自由变化”；#101–105 385.72–396.80 | 389、397 秒可见画布自由变换框，黑边两侧不再均匀，局部变厚、变薄或露出缺口。[389](frame_389.000s.png) / [397](frame_397.000s.png) | 支持 Ctrl+T 自由变换及偏移/尺寸调整形成不均匀边缘。不能推导出独立 Unity OutlineVariation 的位置、延迟、寿命或颜色。 |

观察到的是 Photoshop 图层与画布合成。白色背景和图层缩略图不足以确定最终导出纹理的 RGB/A 布局、白底是否被去除、导出格式或 Unity 导入后的通道语义。本窗口也不能证明四个图形最终如何排列进粒子帧动画。

## 4. 生命周期、黑白闪动与 Alpha

### 字幕与画面

| 时间 / 字幕 | 画面观察 | 判断 |
|---|---|---|
| #372–375 818–825.66 秒：“闪得慢”“生命周期太长” | 827 秒与 843 秒的 Main 模块 Start Lifetime 两个字段发生变化，Duration 仍为 1.00。[Inspector 对照](detail_particle_inspector.png) | 支持修改 Start Lifetime；“生命周期”不能自动映射成缩短 Duration。 |
| #379–382 835.57–839.57 秒：“持续发射”“生命周期挑短了” | 827 秒 Rate over Time 为 0，843 秒为 10，Burst 行仍在。[827](frame_827.000s.png) / [843](frame_843.000s.png) | 支持增加持续发射来补充短寿命后的显示覆盖；不能写成删除 Burst 或唯一标准发射方式。 |
| #387–389 847.96–850.96 秒：“太细了”“15” | 851 秒正在编辑 Start Size 左侧字段，值为 15；843 秒该位置为 5。[851](frame_851.000s.png) | “15”可以绑定到 Start Size 字段。不能把它直接解释为 start_size_x、贴图宽度、Transform X 或三个固定轴值。 |
| #400–404 868.20–874.20 秒：“颜色在生命周期调整”“fix模式” | 875 秒勾选 Color over Lifetime，Gradient Editor 的 Mode 显示 Fixed；883 秒出现硬分界的白/黑/白段；899 秒下拉菜单同时显示 Blend、Fixed，Fixed 有勾选。[渐变细节](detail_gradient_modes.png) | Fixed 模式及分段色标有直接 UI 证据。“不烂”可结合菜单理解为 Blend 的转写错误。 |
| #423–427 903.62–909.62 秒：“闪了很多”“一坨量在进行变化” | 902.100 秒 Game 视图有亮白闪电，902.133 秒为可见黑色轮廓，902.167 秒为灰蓝形体，902.200 秒重新出现亮白。[连续 24 帧](contact_flicker_native_0902_000_0902_767.jpg) | 确认实际预览包含快速亮暗变化。不能仅凭此序列声称完整重建了每颗粒子的最终渐变、频率或全部颜色键。 |
| #430–460 911.62–953.62 秒：视觉刺激/残像解释及“黑白闪” | 934–943 秒，画面保持黑色闪电，Particle Effect 的 Playback Time 保持 0.06；944 秒推进后亮起，947 秒仍可见亮闪电。[手动预览序列](contact_flicker_scrub_0930_0949.jpg) / [黑段全帧](frame_939.000s.png) / [亮段全帧](frame_947.000s.png) | 黑色形体确实仍覆盖背景；这段长时间停留来自作者手动查看预览，不能把录屏停留约十秒当作粒子黑段时长。关于人眼残像的解释仅记为作者说法，本审计不验证生理机制。 |

### 可以确认与不能确认的颜色信息

- **观察：** Color over Lifetime 编辑的是下方颜色键；上方另有 Alpha 键。883 秒 Color 选择器的 R/G/B 均显示 255，Hexadecimal 为 FFFFFF，属于所选白色色标。见 [883 秒全帧](frame_883.000s.png)。
- **观察：** 883、899 秒渐变条有黑色分段，939 秒 Game 视图有实体状黑轮廓。观察中没有足够证据把闪动机制归结为 Alpha 变成零。
- **未确认：** 黑键的精确 RGB 输入、所有最终颜色键的位置、各 Alpha 键的数值及是否在未采样时刻被改动。没有把白色色标的 RGB 255 扩展写成 RGBA 255，也没有把顶部 Alpha 标记直接当成 Alpha=1。
- **未确认：** lightning001 的完整 Shader、Blend 方程、纹理通道处理、顶点颜色与材质颜色的乘法次序，以及光晕中的后处理贡献。875/899 秒能读到 Renderer 材质名，不能据此恢复 Shader 实现。
- **工程推断：** 若实现采用纯加法合成 C_out = C_bg + C_fx，将 RGB 降为零通常只会留下背景，不能得到覆盖背景的黑色形体。若目标是复现本窗口，材质能力检查应包含“黑段仍可见”，并把颜色与覆盖率分别处理。具体采用支持遮盖的混合方式或其他等价方案需要后续实验；本视频证据不要求额外新增一个暗色 Unity 层。

## 5. Mask、Shader 与作用对象

1518 秒 Hierarchy 选中 **qi (1)**，而非前面选中的 shandian。该对象附近还有 qi、shandian 等现有子对象，说明本段是在复合特效里处理另一个对象；不能仅凭 qi 名字确定它的全部语义或创建过程。[对象与资源标签](detail_source_labels.png)

| 时间 / 字幕 | 画面观察 | 判断 |
|---|---|---|
| 1518 秒；#807 1518.19–1520.19“这个切边” | qi (1) 的材质显示 trail002，Shader 栏为 Dong/Add_uv。材质有 Color、TEX01、TEX02 和 mask 字段，mask 为 None。[1518 全帧](frame_1518.000s.png) | 可以记录这些 UI 名称。Shader 名字含 Add 不等于已读取 Blend 实现，尤其不能移用为 lightning001 的 Shader 结论。 |
| #808–809 1520.19–1524.19：“加一个Mask”“虚化” | 打开 Select Texture；1524 秒选中 fx_mask_010，预览为中间白、上下暗的灰度带；资源信息显示 Texture 2D、256×256、RGB Compressed DXT1 sRGB。[1524 全帧](frame_1524.000s.png) | 支持选择有渐变的灰度纹理。此处可见的导入格式是 RGB，不能据名称“mask”假定渐变存放在纹理 A 通道。 |
| 1526 秒；#811 1525.19–1526.19“就没有这个切边了” | 选择器关闭，trail002 的 mask 槽已出现与所选纹理一致的水平灰度带；mask 的 Tiling、Offset 仍可见。[1526 全帧](frame_1526.000s.png) | 绑定有直接证据。作者声称虚化后没有切边，但当前取景有多层高亮闪电和场景叠加，没有隔离目标层或清晰标定切边位置，因此只记“绑定与虚化意图支持，消除程度未可靠确认”。 |
| #812–815 1526.19–1533.46：“不需要…深度”“没必要” | 样本画面没有显示新增深度配置；继续停留在材质和纹理参数界面。 | 这是对当前切边问题的局部建议，不能扩展为所有特效都不需要深度、Soft Particles 或场景交互。 |
| 1534–1550 秒；后段字幕多次只剩“5” | 1548 秒编辑的是 TEX02 的 Tiling，相关数值还包括 TEX02_V；mask 自身的 Tiling/Offset 保持 1,1 / 0,0。[材质对照](detail_mask_material.png) / [1548 全帧](frame_1548.000s.png) | 后段数值属于 TEX02，不能混记成 Mask 的羽化半径、阈值或缩放。字幕乱码不能代替字段绑定。 |

**通道结论：** 当前窗口显示的是纹理槽、灰度预览和 RGB 导入信息，没有 Shader Graph/HLSL、R/G/B/A 选择器或 Alpha Test 阈值画面。可以要求“支持灰度 Mask 调制及渐变过渡”；不能确认为读取 .r、.a、RGB 亮度、相乘位置、Alpha Clip 或 cutout_control。读取单个 RGB 通道是可供验证的工程假设，不是本次观察事实。

## 6. 可读 Inspector 快照

下表只记录本次可以把字段名称与值同时辨认出来的条目。数值属于示范过程，不声称为最终保存状态；双输入字段按画面左、右顺序抄录，不擅自修正顺序或补出下拉模式。

| 时间 / 对象 | 字段 | 可读值 | 使用限制 |
|---|---|---|---|
| 827 / shandian | Duration；Start Delay | 1.00；0 | Duration 与 Start Lifetime 是不同字段。 |
| 827 / shandian | Start Lifetime | 左 0.5，右 0.2 | 操作中的状态；不把这组输入按大小重排成已确认最终范围。 |
| 843、851 / shandian | Start Lifetime | 左 0.15，右 0.2 | 支持寿命左字段缩短的对比。 |
| 827 -> 843 / shandian | Emission / Rate over Time | 0 -> 10 | 843 秒 Burst 仍存在，不能解释为纯连续发射。 |
| 843 -> 851 / shandian | Start Size 左字段 | 5 -> 15 | 此处不恢复 3D 各轴或全部随机范围。 |
| 875、899 / shandian | Renderer / Render Mode；Material | Stretched Billboard；lightning001 | Start Size 的变化需要结合该 Renderer 理解，不能直接等价为贴图宽度。 |
| 875、883、899 / shandian | Color over Lifetime；Gradient Mode | 已启用；Fixed | 菜单中还可见 Blend；完整最终渐变键未恢复。 |
| 939 / shandian | Particle Effect / Playback Time | 0.06 | 是粒子预览时间，不是视频的 939 秒。 |
| 1518、1526、1548 / qi (1) | Material；Shader | trail002；Dong/Add_uv | 仅该对象，不能套到 lightning001。 |
| 1518 -> 1526 / qi (1) | mask 纹理槽 | None -> 灰度带纹理；与 1524 秒选择的 fx_mask_010 对应 | 纹理身份由选择器与前后槽位共同支持，未读取 GUID。 |
| 1518、1526、1548 / qi (1) | mask / Tiling；Offset | (1,1)；(0,0) | Mask 自身参数，不能与上方 TEX02 混淆。 |
| 1548 / qi (1) | TEX02 / Tiling；TEX02_V | (0.5,0.2)；-30 | 编辑中的输入快照，不是 Mask 参数。 |

源 Editor 标题可确认属于 Unity 2019.4 系列。本报告不将压缩后小字的完整补丁版本作为精确事实；DX11 标题也不能证明使用哪一种渲染管线。源渲染管线仍未确认，当前工作区 Unity 版本与该教程配置不能混为一谈。

## 7. 对现有 ProcedureSpec 的修正建议

以下是针对输入 SHA-256 对应版本的建议，**没有编辑 JSON**。使用 step_id 及字段名定位，避免把本报告的推断回写成未经审查的教程事实。

| 现有位置 | 审计结果 | 可执行的修正方向 |
|---|---|---|
| step_001 / bind_texture / 1024×1024 | 其证据时间 2–50 秒、150–170 秒不在本次窗口内。333 秒后只能看到已经存在的形状。 | 保留本次未复核标记。不要用本次审计给尺寸、早期绘制或导出通道补充确认。 |
| step_002 / create_layer / MainBolt | 333–353 秒为 Photoshop 参考分析，“光柱、锐边”没有对应 Unity 创建动作。 | 将可确认部分表述为贴图/造型目标；把 create_layer 与 emission_control 要求标为后续工程映射。 |
| step_003 / create_layer / OutlineVariation | 354–397 秒直接证据是 Photoshop 图层与像素处理。 | 建议改为贴图作者阶段的“复制图层 -> 反相 -> 最小值 -> 自由变换”。不要从该段导出 Unity 支撑对象、变换或时序关系。 |
| step_004 / configure_timing | 生命周期过长及持续发射的因果关系得到支持，但当前文字没有区分 Main.Duration、Start Lifetime 和 Emission。 | 将三个字段分开；用 827/843 秒快照记录寿命与 Rate over Time 的变化。 |
| step_005 / configure_particle | 此步骤已标 inferred，这一点应保留。当前 duration=0.25、lifetime=0.14、三个 size 轴、旋转和 #D7EEFFFF 等不是本次观察到的源参数组。 | 把当前工程参数留作工程配置，不升级成 tutorial_fact。新增来源字段记录时应保留原字段、双输入模式未完全恢复、Stretched Billboard 等上下文。 |
| step_006 / configure_timing | 仅用 color_over_lifetime=true 不足以表达本段的关键操作。 | 增加来源语义“Gradient Mode=Fixed、分段黑白色标、黑段仍有可见形体”。颜色键与 Alpha 键分别记录；完整键值未读全时留待复核。 |
| step_007 / configure_shader / MainBolt | 证据对象实际为 qi (1) / trail002；RGB Mask 可见，cutout_control、slot.alpha_mask、alpha.gradient 的具体含义未获证实。 | 将目标改为源教程的对应辅助对象，或明确为可迁移到其他对象的建议。将“存储于 A 通道”与“用于不透明度调制”分开；未看到阈值时不强制 Alpha Clip。 |
| step_008 / validate_visual | 锐边、粗细、短闪动可作为检查项；本次未证明当前工程已满足它们，也未可靠确认切边全部消除。 | 保留为验收清单，不把它或旧 contact_sheet 当成目标工程已通过的记录。 |
| step_009 / OutlineVariation | 已明确为 inferred 的 EffectDemo 2022 映射；本次也没有找到能证明“略宽、略暗、0.01 秒延后”来自该 PS 片段的证据。 | 保留为可选工程实验，而非课程必要结构；#244A99A0 等值不能借由 step_003 的错误分层获得事实地位。 |
| output_contract / required_roles、layer_sequence、outline_follows_main_bolt | 必须出现 MainBolt+OutlineVariation，以及 outline_follows_main_bolt 的要求，不能由本次窗口推出。 | 建议解除其作为源教程硬约束的地位，保留为自有设计方案；Photoshop 图层与 Unity 层应有不同的阶段归属。 |
| source.timecodes、evidence_refs、training_eligibility.planner_constraint | 现有颜色引文到 910 秒为止，遗漏 930–949 秒清楚的黑段演示；Mask 引文到 1530 秒，遗漏后面的 TEX02 调整。 | 对黑白闪动补本次连续帧和手动预览证据；Mask 绑定与后续材质调节分别引用。检索可保留，但不应把存在混类的整份流程无差别当作 planner 硬约束。 |

### 后续验证应怎样使用这些结论

1. 先分清纹理作者阶段与 Unity 组装阶段。复现粗细变化可先在纹理里实现，不必为了满足错误的 output_contract 添加一个 OutlineVariation 粒子对象。
2. 对颜色做一个独立能力检查：同一可辨轮廓，在固定预览时刻分别呈现亮段与黑段；黑段应保留可见形体，Alpha 的变化单独核对。验证 Fixed 与 Blend 的区别时保持寿命、材质和发射条件一致。
3. 对 Mask 单独核对源资源的 RGB/A 数据、材质实际使用通道以及边缘效果；使用同一时刻、同一镜头的启用/禁用对照，标定被处理的边缘。fx_mask_010 的名字和 RGB 缩略图不能替代通道检查。
4. 把尺寸、颜色、时长等工程值与源快照分栏保存。不要为了匹配当前工程，把 0.25、0.14 或自定义蓝色写成老师原值；也不要把源教程的 Start Size=15 直接搬成任意工程的 X 尺寸。

这些是后续实验建议。本次没有执行这些实验，没有修改当前编译器或颜色实现，没有提升教程整体学习、源复刻或目标工程验收状态。

## 8. 新增图像清单

所有单帧文件均保留 1280×720 全画面，文件名时间与 FFmpeg 首帧 PTS 一致。全部图像已通过当前会话的图像展示工具实际打开查看，细节联系图已检查标签和画面是否遮挡。

| 类别 | 新增原分辨率帧 |
|---|---|
| Photoshop，6 张 | [353](frame_353.000s.png)、[361](frame_361.000s.png)、[369](frame_369.000s.png)、[377](frame_377.000s.png)、[389](frame_389.000s.png)、[397](frame_397.000s.png) |
| 生命周期/渐变/闪动，10 张 | [819](frame_819.000s.png)、[827](frame_827.000s.png)、[843](frame_843.000s.png)、[851](frame_851.000s.png)、[875](frame_875.000s.png)、[880](frame_880.000s.png)、[883](frame_883.000s.png)、[899](frame_899.000s.png)、[939](frame_939.000s.png)、[947](frame_947.000s.png) |
| Mask，4 张 | [1518](frame_1518.000s.png)、[1524](frame_1524.000s.png)、[1526](frame_1526.000s.png)、[1548](frame_1548.000s.png) |

| 联系图 | 内容与缩放 |
|---|---|
| [contact_texture_0333_0397.jpg](contact_texture_0333_0397.jpg) | 17 个全画面缩略格，333+4n 秒，至 397 秒；1600×1265 |
| [contact_lifetime_0811_0965.jpg](contact_lifetime_0811_0965.jpg) | 21 格，811+8n 秒至 963 秒，另加 965 秒；1600×1518 |
| [contact_mask_1518_1550.jpg](contact_mask_1518_1550.jpg) | 17 格，1518+2n 秒，至 1550 秒；1600×1265 |
| [contact_flicker_native_0902_000_0902_767.jpg](contact_flicker_native_0902_000_0902_767.jpg) | 连续 24 帧；源 Game 裁切框 (35,412)-(560,690)，缩至 350×186；每格按解码 PTS 标注；1400×1296 |
| [contact_flicker_scrub_0930_0949.jpg](contact_flicker_scrub_0930_0949.jpg) | 930–949 秒每秒一格；同一 Game 裁切缩至 400×212，附 (443,312)-(556,339) 的播放字段；1600×1420 |
| [detail_particle_inspector.png](detail_particle_inspector.png) | 827/843/851 秒；裁切 (1040,125)-(1279,431)，最近邻 2 倍；1434×646 |
| [detail_gradient_modes.png](detail_gradient_modes.png) | 875/880/883/899 秒；裁切 (715,131)-(945,254)，最近邻 2 倍；1840×280 |
| [detail_mask_material.png](detail_mask_material.png) | 1518/1526/1548 秒；裁切 (1040,151)-(1279,422)，最近邻 2 倍；1434×576 |
| [detail_source_labels.png](detail_source_labels.png) | 827 秒标题、1518 秒层级、1524 秒选择器、377 秒 PS 最小值对话框；各格标注 2/3 倍最近邻放大；1320×790 |

原始视频、字幕、流程和现有证据图均未覆写。报告中的“观察”来自图像读取，“字幕”来自已有自动转写，“工程推断/建议”不作为原教程已验证事实。

## 9. 交付复核

- 目录核对通过：仅 1 份 Markdown 报告、20 张全画面 PNG、9 张联系图/细节图，共 30 个新增文件；没有额外脚本、JSON 或视频。
- Pillow 解码校验通过：29/29 张图片有效；20/20 张单帧尺寸为 1280×720。
- 报告链接校验通过：29 个不同的图片链接全部指向本目录内实际存在的文件。
- 输入完整性核对通过：原视频、part03.zh.srt、procedure_spec.json 的 SHA-256 与第 2 节审计开始时快照完全一致；ProcedureSpec 仍可正常解析。
- 图像展示与实际判读已经执行，未用上述文件检查代替视觉观察；没有运行 Unity、Beads 或 Git 命令。以上检查不构成 Unity 复刻、性能或专业视觉质量验收。
