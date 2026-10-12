## ERR-VFXCOLOR-001

- 日期：2026-09-07；任务：`vfx-2df.42.3`。
- 现象：真实 URP 参数对照中的闪电明显偏暗，QFX 主体内部为黑色；增加训练轮数无法修正实际执行中的颜色/材质配置。
- 代码根因：旧编译器将同一 StartColor 同时写到 Main.startColor、ColorOverLifetime 首键和材质 Tint；对灰色0.5形成三次乘法。QFX GO_Crystal 还保留黑色 DissolveColor 和0.7的DissolveEdgeWidth，Shader需要 TEXCOORD0.z、TEXCOORD1.xy、Noise、Emission 输入，不能只替换_MainTex就认定完整匹配。
- 修复：增加完整显式生命周期 Gradient（颜色/Alpha键及Blend/Fixed）和 `material_color_mode=preserve_template`，新教程只在粒子初始色施加Prompt色。旧缺省字段保留原行为；源导出保留确定性渐变、标记随机颜色分布缺口；回读比较全部键和模板颜色，不只比较终点。
- 实验：`particle_color_calibration_r002` 为11/11编译、11/11回读、446真实URP有效帧。API中的灰色乘积从0.125变为0.5，蓝色从(0.005832,0.125,1)变为(0.18,0.5,1)，白色恒等对照不变。线性项目中灰色前景R均值由23变124，像素值还受色彩空间转换，不等同于直接将上述浮点数乘255。
- 材质对照：仅分离颜色使QFX变亮但黑色内芯仍在；官方URP粒子模板、同一贴图和独立通道下主体实心可见。该模板为明确的校准实验选择，不冒充当前自动资产排序的输出，不改原QFX资产。
- 资格：当前报告仅 `pass_color_execution_only`，不批准完整教程复现、专业审美或正向SFT。
- 复核：Python端与C#使用一致的空渐变内容判定；随机TwoColors的最大颜色等于目标常量时，旧回读Native实测错误pass，新增模式校验后准确mismatch。中间色键篡改也被拒绝。校准报告新增所有控制样例的完整帧及材质错误门，教程使用有符号像素差区分黑形体与背景。
- 后续：Fixed R003修正首段键值后，3/3编译/回读、123帧及先亮/黑/再亮机制通过。源RGB/Alpha键未完整恢复，试验参数仍inferred；正常选材入口继续由42.4接入，不做隐藏模板回退。
- 状态：颜色执行与局部机制已验证；完整教程和自动配方选择尚未完成。

## ERR-VFXCAPTURE-003

- 日期：2026-09-07；任务：vfx-2df.42.3，后续vfx-2df.42.5。
- 现象：Fixed与Alpha-only源导出重建各41帧逐像素一致；Blend API字段一致但最大通道差5。严格源往返报告保留failed。
- 区分实验：同Prefab、seed、相机和参数，原样重复拍摄original_a/original_b出现最大通道差13，全帧最大MAE约0.0774；original_b与重建体差3。不能只归因于源导出，尚不能说明具体Native时间差来源。
- 当前处理：保存source_roundtrip_pixel_report.json与repeatability_report.json，不提高阈值放行。后续记录实际Particle年龄/颜色及更新阶段，保留脚本动态材质语义。
- 状态：open，捕获重复性待进一步校准；不影响已实测的Fixed局部源往返结论，不外推所有Prefab。

## ERR-UNITY-072

- 日期：2026-09-07；任务：`vfx-2df.42.3`；工程：EffectDemo 2022隔离执行项目。
- 原始命令：`unity run .../EffectDemoPromptHumanR001 --editor-version 2022.3.62f3 -- -nographics -executeMethod EffectDemoParticleColorCalibration.PrepareAndCompile -prefabGraphBatchRequest .../particle_color_calibration_r001/compile_request.json`。
- 原始错误：退出码1，四个旧字段样例报 `Particle gradient mode must be Blend or Fixed`，新字段样例通过。
- 根因：Unity JsonUtility 将未出现的嵌套序列化类实例化为空对象，`gradient != null` 无法区分旧Graph与新数据。
- 修复：`EffectDemoParticleColorGradient.HasData` 按模式或键数据检测内容；空对象维持旧逻辑，带数据对象仍严格校验模式、键数、顺序和数值。
- 复验：保留R001失败日志与产物，R002全11个样例编译/回读通过，旧灰色三次乘法和白色对照未改变。
- 预防：可选Unity嵌套DTO必须验证实际反序列化行为，不能依赖C# null假设；必须同时跑旧格式与新格式。
- 状态：resolved。

## ERR-VFXDATA-022

- 日期：2026-09-07；任务：`vfx-2df.42.3`；来源：Part03制作教程局部视频核对。
- 旧记录问题：把354至397秒Photoshop图层复制/反相误写成Unity必须创建OutlineVariation；把qi (1)/trail002的RGB Mask操作归入MainBolt并强制cutout_control；把Fixed黑白闪动弱化为普通Alpha渐隐。
- 实际证据：`knowledge/sources/SRC-2026-GAMEVFX-001/episode_01雷之呼吸/visual/material_color_audit_20260907/audit_report.md`；20原分辨率关键帧和9联系图，包含902秒的24连续帧，实际可见亮白、黑形体、灰蓝、再亮白。源Unity为2019.4系列，完整补丁/管线/所有曲线键仍未知。
- 修正：步骤加入制作阶段，Photoshop步骤指向LightningShapeTexture；Mask指向SourceQiTrail且不再假设A通道或Alpha Clip；主体不强制独立OutlineVariation层；Fixed模式保留为事实，实际试验键值列为inferred step_010。旧JSON快照保存至R002/source_procedure_before_video_audit.json。
- 预防：知识提取必须绑定操作软件、选中对象、Inspector字段和源时间码；字幕不能单独决定层级、Shader功能或纹理通道。
- 状态：记录已纠正，完整源场景和材质复现仍待后续验证。

## ERR-VFXPIPELINE-001

- 日期：2026-09-07
- 任务：`vfx-2df.42.2` 可行性评估与 Prompt 执行对照。
- 原始命令：`effectdemo_render_source.ps1 -Requests .../tutorial_lightning_effectdemo2022_r001/render_requests_assessment_20260907.json -ProjectPath .../EffectDemoPromptHumanR001 -UnityEditor .../2022.3.62f3c1/Editor/Unity.exe -NoUpm -PlayModeRuntime`。
- 实际结果：24 个有效帧，图像序列资格 true；新增运行时环境记录显示 `active_render_pipeline_type=no_active_srp`、`configured_render_pipeline_type=no_loaded_default_srp_asset`。工程配置引用 URP，但该次截图没有运行 URP。
- 初次 UPM 复验：不使用 `-NoUpm`、使用 ASCII 路径别名，以及将 staging 包清单对齐当前权威工程的 URP 14.0.12 后，均出现 `Failed to resolve packages: The "path" argument must be of type string. Received undefined. No packages loaded.`。官方 CLI 正常启动也返回退出码 1；UPM 日志记录 `project:resolve-packages` 的 `params: {}`。后续确认 params 为空是正常请求结构，不是缺少工程路径的证据。
- 其他环境事实：旧 2022.3.16f1 路径已经不存在；本次隔离验证使用实际安装的 2022.3.62f3c1。权威项目包清单已是 14.0.12，但 ProjectVersion 仍标记 2022.3.16f1c1，应区分文件声明与实际运行版本。
- 弯路记录：此前把 `-NoUpm` 当成保留既有 URP 包图的恢复方案，并以脚本编译、Camera.Render 成功证明目标管线可用。运行时实测推翻了这个结论。ASCII 别名与包清单对齐没有修复 UPM，普通隐藏 Editor 启动未产生请求日志，已仅停止本任务启动的进程。
- 根因实证：两个已安装 Editor（2022.3.62f3c1、2022.3.50f1c1）的独立空工程均复现同错。只读 IPC 转发记录证明 project/editor/builtin/dotnet 路径完整。对官方 UPM 脚本仅在内存增加异常栈日志，定位到 `getDeprecatedGlobalConfigRoot -> path.join(process.env.ALLUSERSPROFILE, "Unity/config")`。当前批处理环境没有 ALLUSERSPROFILE；不是 Prefab、包清单、中文路径或账号权限问题。没有修改 Unity 安装文件或系统环境。
- 修复：新增 `workspace/tools/effectdemo_unity_process.ps1`，8 个 EffectDemo 启动入口共用。仅在缺失时从 Windows CommonApplicationData 补齐子进程继承环境，保留已有值，并在正常/异常退出后恢复。停止用 `-NoUpm` 规避 UPM；它仍可用于显式诊断，但不代表目标管线运行。
- 复验：同一最小工程从退出码 1 变为 0；正常 UPM 对 staging 解析返回 200。`prompt_execution_regression_urp_r002` 在真实 UniversalRenderPipeline 实例下完成 4/4 编译、4/4 API 回读和 218 有效帧，颜色/方向/时长及同 seed 对照全部通过。`Camera.Render()` 在本次 Unity 2022/URP14 实测可用，没有仅凭推测改用其他渲染 API。
- 证据门禁：保留活跃/配置资产类型，新增 `RenderPipelineManager.currentPipeline` 的实例类型、预期类型和匹配布尔值。管线不匹配时，即使 PNG 有效，图像/完整视觉训练资格也必须 false。真实反例在 32/32 有效帧下返回 `render_pipeline_mismatch`，两项资格均 false。旧未记录实例 Pipeline 的截图需要重新核验。
- 复核修正：独立代码审查发现请求显式填写 `expected_render_pipeline_type=no_active_srp` 可使缺失实例与占位字符串相等。新增 Unity Editor `EffectDemoPipelineGateProbe`，使用合成帧/上下文调用实际 WriteManifest 隔离此门禁，修复前两项训练资格错误为 true、退出码 1；增加实例非空前置后，两项均 false、退出码 0。`pipeline-null-gate-before/after.json` 仅为合成单元测试记录，不是截图或训练样本。
- 测试：最终 544 项 Python 测试通过（包括环境填补/保留/异常恢复、资产类型不等于运行实例的反例、受限验收修订入口）；正常回放没有 C# 编译错误或捕获异常。Editor 启动仍有旧 Hub licensing handshake 警告，后续连接本版许可客户端并正常完成，不声称日志完全无警告。
- 日志：`upm-probe-20260907-minimal.log`、`upm-probe-20260907-editor50.log`、`upm-probe-20260907-ipc.jsonl`、`upm-probe-20260907-env-fixed.log`、`prompt-execution-urp-r002-runtime.log`、`prompt-execution-urp-r002-pipeline-negative.log`。
- MCP 补充：CLI 未发现 Pipeline 实例后，只调用 `manage_editor/get_project_root` 检查连接；返回无法连接。未通过 MCP 修改场景或资产。
- 状态：resolved，批处理 UPM 与目标 URP 捕获已恢复；本批画面仍偏暗且动态材质证据不完整，不是专业质量正例。

## ERR-VFXDATA-021

- 日期：2026-09-07
- 任务：`vfx-2df.42.2` 生成链真实性评估。
- 实测：固定 seed=123、同一雷电 ProcedureSpec，两条相反 Prompt 的 graph_id 不同，但 nodes、components、asset_bindings 完全相同。
- 根因：Prompt 解析只写入元数据，实际参数仍由流程文件固定值决定；旧测试只验证字段存在、ID 或解析结果，未检查实际执行对照。
- 修复：增加有范围限制的颜色、静态平面方向、明确时长控制，并保存逐字段前后差异与未支持意图；增加同 seed、固定资产和独立 runtime seed key 的对照验证。
- 标注修复：静态 Shader 启发式不再批准正向训练；复用相同材质不再自动视为失败；inferred 步骤不进入已支持教程约束，SFT 即使被手工置 true 也会因 inferred 步骤被排除。
- 执行修复：Vertex Streams 从集合比较改为保序比较；真实 Unity 反例将 Position,Color,UV 改为 Position,UV,Color 后准确返回 `renderer[n0001].active_vertex_streams differ (order is significant)`。Custom Data 未导出的源 Prefab 显式标为未支持，防止仅保存流名称却宣称可完整重建。
- 复验：颜色/方向/时长、静态标签资格、inferred 约束的 5 个旧实现失败用例修复后通过；四个生成候选 Unity 编译和 API 回读 4/4 通过；实际连续帧对照见 `generated/prompt_execution_regression_r001/regression_report.json`。
- 后续复验：ERR-VFXPIPELINE-001 已定位并修复，正常 URP R002 的七项参数对照门全部通过；状态为 `pass_parameter_controls_only`。整体成品、Planner SFT 和正向生成资格仍未批准。
- 状态：resolved，参数执行与资格隔离已完成；完整教程材质行为继续由后续任务验证。

## ERR-UNITY-071

- 日期：2026-09-04
- 任务：`vfx-2df.7` 双层 Mesh 刀光 PrefabGraph 首批回读。
- 工程：`workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`。
- 原始现象：`layered_slash_family_r001` 为 `8/8` 编译成功且 `8/8` Mesh 路径正确，但 Prefab API 回读全部为 `particle.parameters differ`。
- 根因：Graph 同时写入 `shape_enabled=false` 和 `shape_type=Sphere`；Unity 在 Shape 模块关闭时规范化回读为 `shape_type=disabled`。Mesh、材质和 Shader 均已正确绑定。
- 修复：刀光生成器在 Shape 关闭时显式写入 `shape_type=disabled`，新建 R002 复验，不覆盖 R001 失败证据。
- R002 复验：Shape 枚举修复后 `8/8` 编译、`8/8` Mesh 路径回读通过，但 Play Mode 全部 `near_blank`；相机四个候选视角均为零可见像素。
- 追加根因：`SwordSlash.mat` 的 Hovl Shader 依赖原 Prefab 配置的自定义 Particle vertex streams 和材质驱动参数；PrefabGraph 当前只复现通用粒子字段，虽然 Mesh/Shader/纹理引用完整，运行时仍被 Shader 裁掉。
- 追加修复：R003 保留 `Slash4.fbx`，改用已在 EffectDemo 批次验证过的 QFX 粒子材质，并显式绑定 `Trail68.png` 到 `_MainTex`，避免把未建模的 Hovl vertex-stream 状态冒充通用可复现资产。
- 预防：PrefabGraph 中关闭的可选模块必须写入与 Unity API 回读一致的规范化枚举；编译通过不能替代 API 字段一致性。
- R003 复验：保留 `Slash4.fbx`，使用 QFX 粒子材质并显式绑定 `Trail68.png` 后，`8/8` 编译、Mesh 回读、Prefab API 回读和 Play Mode 可见性通过，Shader 为已验证的 QFX 粒子 Shader。
- 最终状态：resolved。

## ERR-VFXDATA-019

- 日期：2026-09-04
- 任务：`vfx-2df.7` 刀光外主刃/内辅刃专业 Teacher。
- 原始现象：刀光层次 A/B 技术门禁通过，但如果只比较过曝像素比例，两侧差异为 0，无法表达“内外同长同亮”。
- 根因：QFX 材质没有把当前颜色强度推到绝对过曝阈值；过曝像素数量不是刀光主次层级的稳定代理。
- 修复：保留过曝比例为诊断，正式动态门禁使用主刃可见宽度保留和高亮横向跨度收缩；同时用 Graph 精确验证外层尺寸/Alpha 比例。
- 复验：正确层级保留 100% 主刃可见宽度，高亮横向跨度减少 `0.575`，外层尺寸与 Alpha 比例门禁通过，Teacher 状态 `verified`。
- 预防：刀光层级应测量沿攻击方向的高亮跨度和主轮廓保留，不能只用绝对过曝阈值。
- 状态：resolved。

## ERR-VFXDATA-018

- 日期：2026-09-04
- 任务：`vfx-2df.35` 完整爆炸 staged rhythm 专业 Teacher。
- 原始现象：同时起播/分层起播两侧 `2/2` 技术通过，晚段残留增益通过，但首版 `outer_onset_seconds` 两侧都为 0，导致节奏报告 blocked。
- 影响：实际联系表中首帧差异清楚，但固定径向 onset 指标无法证明分层顺序，规则不能晋级。
- 根因：结构化 Core 的尖角和光晕本身越过固定外围半径，绝对像素 onset 无法区分 Core 轮廓与 Shockwave/碎片层；继续调半径会过拟合当前纹理和相机。
- 修复：绝对 onset 保留为诊断值，不作为层身份门禁；正式门禁组合 Graph 的 `Core < Support < Hit < Residual` 启动顺序、画面早期外围重叠下降和晚段可见时间延长。
- 复验：分层延迟为 `0.00/0.04/0.07/0.20s`，早期外围可见均值下降 `0.00481`，最后可见时间延长 `0.20s`，全部技术和节奏门禁通过，Teacher 状态 `verified`。
- 预防：完整节奏不能仅由绝对像素半径推断层身份；必须联合 Graph 时间参数、同种子动态差异和晚段收束证据。
- 状态：resolved。

## ERR-VFXDATA-017

- 日期：2026-09-04
- 任务：`vfx-2df.35` Core 材质 Teacher 的四层批量迁移。
- 原始现象：`layered_explosion_material_ablation_r001` 为 `8/8` 技术通过，但首版材质规则迁移 `0/8`；edge density gain 为负，和隔离 Teacher 结果相反。
- 影响：四层材质样本不能进入 Core 材质模型训练。
- 根因：首版沿用 `0-0.45s` 峰值窗口；Shockwave 在 `0.04-0.06s`、Debris 在 `0.07-0.08s` 启动，完整四层的外围结构覆盖了 Core 纹理差异。材质指标实际测到的是组合峰值，不是 Core 材质。
- 修复：从每个 Graph 读取 Support 的 `start_delay_max`，将材质统计窗口截止到 `support_delay-0.005s`，只使用外围层启动前的 Core-only 帧；不修改任何视觉阈值。
- 复验：8 对全部通过；bbox fill reduction 为 `0.33-0.34`，edge density gain 为 `0.04-0.05`，中心亮度保留比例为 `0.75-0.83`。随后材质模型 R001 在独立 R011 上为 `8/8` 分布内。
- 预防：单层材质规则在完整 Prefab 中必须依据层启动时间选择无污染窗口；不能用完整组合峰值代替单层材质证据。
- 状态：resolved。

## ERR-VFXDATA-016

- 日期：2026-09-04
- 任务：`vfx-2df.35` 结构化 Core 纹理接入后的 R010 四轴回归。
- 原始现象：R010 为 `8/8` 编译、Prefab API 回读和 Play Mode 技术通过，但模型分布门禁只有 Core `1/8`，Residual、Shockwave、Debris 均为 `0/8`。
- 影响：不能证明结构化 Core 纹理与其他三轴兼容，也不能将其晋级为默认生成资产。
- 根因：四个窄轴模型均从完整四层合成画面提取视觉特征；Core 纹理替换会同时改变其他轴的输入，即使对应层参数完全未改，模型仍会判定 OOD。这是跨层特征耦合，不是三个层同时发生视觉退化。
- 修复：将 `explosion_family_adapter.v3` 的默认 Core 纹理恢复为已回归的 `FX_Glow_1.TGA`，结构化纹理保留为 `CORE_TEXTURE_CANDIDATE`；Teacher 仍为 verified，但列入 gated teacher rule，不进入默认生成。
- 复验：Residual、Shockwave、Debris 模型移除全局图像特征后复用同一批 R010 帧；Shockwave 与 Debris 均由 `0/8` 恢复为 `8/8` 分布内。Residual 首次仍为 `0/8`，进一步确认训练捕获是 `512x512 / 0.05s`，R010 综合捕获是 `640x640 / 0.025s`，活跃帧比例直接受采样间隔影响；新增 `residual_fixed_orthographic_v1` 并合并第二批 8 对后，匹配协议的 R010 恢复为 `8/8` 分布内。Core 仍需材质专用模型。
- 预防：任何单层材质升级都必须同时执行层内 Teacher 和完整组合跨轴回归；窄轴模型不得长期依赖完整合成画面特征。
- 状态：partially resolved；Shockwave/Debris/Residual 已解耦并通过，Core 待材质模型和 R011 独立回归。

## ERR-VFXDATA-015

- 日期：2026-09-04
- 任务：`vfx-2df.35` 爆炸核心材质结构专业 Teacher 复刻。
- 原始现象：`professional_teacher_explosion_material_r001` 的编译、贴图回读、Prefab API、Play Mode、轮廓填充和中心亮度门禁均通过，但首版因 `visible_luma_std_gain=-0.0294` 被判为 blocked。
- 影响：实际已形成不规则轮廓和软边的结构化纹理被错误拒绝，不能进入材质 Teacher catalog。
- 根因：亮度标准差是在透明裁切后的可见像素内统计；结构化纹理去掉大量暗背景后，可见像素亮度反而更均匀。该指标不能证明“不是整块高亮贴片”，与专业规则的视觉含义不一致。
- 修复：保留亮度标准差为诊断值，不再作为门禁；材质结构门禁改为同材质、同粒子参数下同时满足轮廓填充率下降、边缘密度增加和中心亮度保留。
- 复验：结构化纹理相对平坦光盘的 bbox fill 降低 `0.3461`、edge density 增加 `0.0521`、中心亮度保留比例 `0.8057`，所有技术与材质结构门禁通过。
- 预防：透明纹理的内部亮度统计必须区分 Alpha 裁切与真实明暗层次；不能把可见像素标准差单独作为纹理结构质量真值。
- 状态：resolved。

## ERR-VFXDATA-014

- 日期：2026-09-04
- 任务：`vfx-2df.35` 四层爆炸 Shockwave 静止/外扩专业 Teacher 迁移。
- 原始现象：`layered_explosion_shockwave_ablation_r001` 首次统计为技术门禁 `8/8`，但专业规则迁移 `0/8`；首帧到峰值的差异半径增长仅 `0.118-0.176`，低于单环 Teacher 的 `0.20`。
- 影响：清楚可见且持续外扩的 8 个单环被错误排除，不能进入 Shockwave 窄轴训练。
- 根因：Play Mode 请求的第 0 帧在截图时已进入粒子生命周期，较大的初始环已经扩张，导致“首帧到峰值”系统性低估完整增长；完整四层画面的半径同时会被 Debris 和 Residual 污染，不适合作为 Shockwave 单层门禁。
- 修复：保持固定正视、正交尺寸、种子和同帧时间，改在静止/外扩成对差异图中计算 `p90-p10` 内外圈径向分离；径向增长和分离阈值仍沿用已验证 Teacher 的 `0.20/0.15`，未降低标准。
- 复验：8 对内外圈峰值径向分离为 `0.258-0.267`，差异外缘单调比例为 `0.95-1.00`；技术门禁 `8/8`、专业规则迁移门禁 `8/8`，联系表显示单一圆环而非序列图九宫格。
- 预防：多层 Prefab 的单层规则必须优先使用同种子成对差异隔离目标层；捕获首帧不等于粒子出生时刻，不能把首帧半径直接当初始半径。
- 状态：resolved。

## ERR-UNITY-070

- 日期：2026-09-04
- 任务：`vfx-2df.35` 四层爆炸 Shockwave 静止变体批量编译。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`。
- 原始命令：`effectdemo_compile_prefab_graph_batch.ps1 -Request .../layered_explosion_shockwave_ablation_r001/compile_request.json -ProjectPath .../EffectDemoPromptHumanR001`。
- 原始错误：Unity Package Manager 返回 `Failed to resolve packages: The "path" argument must be of type string. Received undefined. No packages loaded.`，进程退出码 `1`。
- 影响：首轮未进入 PrefabGraph 编译器，没有生成任何静止环编译结果。
- 根因：本轮任务不需要解析或改动 UPM 包，但批处理默认启动了 UPM；项目已有完整 `Library` 和锁定包状态，UPM 的外部解析异常成为无关阻塞。
- 修复：按现有离线批处理约定增加 `-NoUpm`，保留同一请求和同一 staging 工程重跑。
- 复验：静止环变体 `8/8` 编译通过、`8/8` 计划贴图回读一致；随后 `8/8` Prefab API 回读通过，Play Mode 捕获完成且无材质渲染错误。
- 预防：已准备完成且不涉及包变更的 staging 批处理统一使用 `-NoUpm`；如任务涉及包增删或锁文件变化，则必须先恢复 UPM 正常解析，不能用该参数掩盖包错误。
- 状态：resolved。

## ERR-VFXDATA-013

- 日期：2026-09-04
- 任务：`vfx-2df.29.8` / `vfx-2df.38.10` 爆炸 Residual-off/on 专业 Teacher 迁移。
- 原始现象：`layered_explosion_residual_ablation_r001` 的 8 对数值增益都达到残留门槛，但只有 2/8 通过技术门禁；其余 6 对失败项为 `same_camera_view=false`。
- 影响：不同视角的像素差异不能归因于 Residual，R001 不能进入训练。
- 根因：Capture v2 对每个 Prefab 独立评估 front/side/top；Residual 是否可见会改变总可见面积，从而让两个受控变体选中不同镜头。
- 修复：`EffectDemoRuntimeCaptureController.RequestItem` 新增 `forced_camera_view`；只有受控成对请求显式设为 `front`，普通 Prefab 仍使用多视角自动选择；manifest 中将 mode 记为 `forced_request_view`。
- 复验：`layered_explosion_residual_ablation_r002` 的 8/8 对均为同镜头、同帧数、早期帧近似不变，技术门禁 8/8、残留增益门禁 8/8；晚段活跃比例增益 `0.2632-0.3514`，最后可见时间延长 `1.10-1.30s`。
- 预防：单变量视觉对照不得让自动取景成为第二变量；成对实验必须共享视角、种子、分辨率、时间点和边界拟合策略。
- 状态：resolved。

## ERR-UNITY-069

- 日期：2026-09-04
- 任务：`vfx-2df.35` 将已验证四层爆炸批次从 staging 转入权威 EffectDemo。
- 工程：`UnityDemo/EffectDemo`；Unity 项目结构校验。
- 原始命令：`unity projects verify "UnityDemo/EffectDemo" --format json`。
- 原始错误：`META_MISSING` at `Assets/Generated`，提示 Unity 会为缺少 `.meta` 的资产目录分配新 GUID。
- 根因：首次只复制了 `Assets/Generated/LayeredExplosionFamilyR005/` 及其自身 `.meta`，但权威工程中上级 `Assets/Generated/` 原先不存在，未同步 staging 的 `Assets/Generated.meta`。
- 修复：从 staging 复制 `Assets/Generated.meta` 到权威工程，并校验 SHA-256 一致。
- 复验：再次执行 `unity projects verify` 扫描 17768 个文件，`errors=0`、`warnings=0`。R005 的 8 个 Prefab 和 32 个生成材质均保留。
- 预防：复制新 Unity 资产子树时，除子树内部 `.meta` 外，还必须检查每一个新建父目录的同级 `.meta`；完成前必须运行 Unity 项目结构校验。
- 状态：resolved。

## ERR-UNITY-068

- 日期：2026-09-04
- 任务：`vfx-2df.35` 四层爆炸 Core-off 成对消融。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；失败批次 `layered_explosion_core_ablation_r001`。
- 原始命令：使用 `effectdemo_readback_prefab_graph.ps1` 回读 `layered_core_pair_000_pfg_3ee2e4caad02d2ddfaf3`的 `CoreOff.prefab`。
- 原始错误：`InvalidOperationException: Unity API readback differs from input Graph.`；结构化差异为 `nodes[CoreOff[0]] unexpected hierarchy path`。
- 根因：Prefab 文件名 `CoreOff.prefab` 使 Unity 将根对象名规范化为 `CoreOff`，与 Graph 中的 `GeneratedRoot[0]` 不同。
- 修复：消融候选改为独立目录下的 `GeneratedRoot.prefab`，新建 `layered_explosion_core_ablation_r002`复验。R002 结构门禁通过，但 Core-off 8/8 不可见，说明外围三层材质过弱，因此仍不入训练。
- 最终复验：替换 Shockwave/Debris/Residual 为可响应粒子色的 QFX 材质与真实源贴图后，`layered_explosion_family_r004` 为 8/8 技术通过；`layered_explosion_core_ablation_r003` 的 Core-off/Core-on 为 8/8 技术通过和 8/8 核心增益通过，亮度/局部对比增益范围约 `0.046-0.064`。
- 预防：生成 Prefab 的文件名、根对象名和 Graph 根路径必须一致；“层存在”不等于“层可见”，每个新拓扑都必须用关闭 Core 后仍可见的消融对证明外围层有效。
- 状态：resolved。

## ERR-UNITY-067

- 日期：2026-09-04
- 任务：`vfx-2df.35` 爆炸族专用四层 PrefabGraph 生成器。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；失败批次 `layered_explosion_family_r002`。
- 原始命令：使用 `effectdemo_readback_prefab_graph.ps1` 回读 `layered_explosion_000_pfg_29e0897e61af3d5fb478`。
- 原始错误：`InvalidOperationException: Unity API readback differs from input Graph.`；结构化差异为 `nodes[GeneratedRoot[0]] unexpected hierarchy path`。
- 影响：R002 虽已 8/8 编译，但未继续运行捕获，不进入技术成功集。
- 根因：生成 Graph 的根名与层级路径使用 `GeneratedLayeredExplosion`，而编译产物根节点按 Prefab 文件名规范化为 `GeneratedRoot`。
- 修复：生成器统一根节点名称和所有 `hierarchy_path` 前缀为 `GeneratedRoot[0]`；新批次使用 `layered_explosion_family_r003`，不覆盖失败证据。
- 复验：R003 产生 8 个 CoreFlash/ ShockwaveRing/ DebrisBurst/ ResidualSmoke 四层 Graph 和 VFXSpec；8/8 编译、8/8 贴图计划回读、8/8 Prefab API 回读、8/8 Play Mode 通过，每个 51 帧，无 C# / Shader / 运行异常。
- 预防：无 parent Graph 的根名必须与输出 Prefab 名对齐；新拓扑首条样本必须在扩批前完成 Unity API 回读；读回 mismatch 不得被编译 pass 覆盖。
- 状态：resolved。

## ERR-UNITY-066

- 日期：2026-09-03
- 任务：`vfx-2df.29.8` 首条专业审美 Teacher 爆炸核心受控复刻。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；URP `14.0.9`；失败批次 `professional_teacher_explosion_core_r005`。
- 原始命令：`effectdemo_compile_prefab_graph.ps1 -Graph .../professional_teacher_explosion_core_r005/graphs/empty_core.json -OutputPrefab Assets/Generated/ProfessionalTeacherExplosionCoreR005/empty_core/GeneratedRoot.prefab -ProjectPath .../EffectDemoPromptHumanR001 -NoUpm`；补齐材质后继续执行 `effectdemo_readback_prefab_graph.ps1` 读回 `reinforced_core`。
- 原始错误：首次编译报 `FileNotFoundException: Particle material template could not be loaded: Assets/QFX/ProjectilesFX/VFX_Resources/Materials/Nature/MFX_Flare_4.mat`；补齐后强化版回读报 `InvalidOperationException: Unity API readback differs from input Graph`，差异为 `particle[n0001].parameters differ`。
- 影响：R005 不允许进入 Play Mode 和 Teacher readiness，未产生伪验证审美标签。
- 根因：隔离工程已有 QFX Shader 和 `FX_Glow_1.TGA`，但缺少配套 `MFX_Flare_4.mat/.meta`；另外，实验一度关闭 `Color over Lifetime`，Unity API 回读会将未启用模块的 `end_color_rgba` 归一为起始色，与 Graph 中的透明结束色不一致。
- 修复：从权威 `UnityDemo/EffectDemo` 按原相对路径复制 `MFX_Flare_4.mat` 和 `.meta` 到 staging，SHA-256 均一致；R006 恢复 `color_over_lifetime_enabled=true`，保留受控 Core alpha 差异。
- 复验：`professional_teacher_explosion_core_r006` 两个 Graph 均为编译 `pass`、贴图计划回读匹配、Prefab API 回读 `pass`、Play Mode `34/34` 有效帧且错误洋红0；强化核心在同一 `0.2982s` 帧的中心亮度和局部对比度增益分别为 `0.24285` 和 `0.24217`，门禁全通过；`professional_aesthetic_teacher_readiness_r002` 为 `ready`、`teacher_ready_count=1`。
- 预防：专业 Teacher 复刻在编译前必须验证 Material/Shader/Texture/.meta 依赖闭包；不得用会被 Unity 丢弃或归一的未启用模块字段作受控变量；新试验使用新 `r00x` 目录保留失败证据。
- 状态：resolved。

## ERR-VFXDATA-012

- 日期：2026-09-03
- 任务：`vfx-2df.38.7` 主动复核多选时备注被清空。
- 工程与服务：评审数据 `workspace/data/vfx_generation/reviews/prefab_active_review_full_r005`；服务 `workspace.tools.vfx_generation.prefab_active_review`；本地地址 `http://127.0.0.1:8801/`。
- 原始现象：人工在备注框输入额外判断后点击反馈选项，页面重新渲染反馈区，未提交的备注被清空。
- 根因：多选交互的 `renderReview` 每次都从 `saved?.notes` 回填 textarea；当前条目的未确认备注没有独立的前端草稿状态。
- 修复：新增 `pendingNotes` 与 `pendingNotesDirty`；备注输入事件即时更新待提交草稿，选项切换、清除选择和重新渲染读取待提交备注；确认成功后才清理草稿并写入服务端。已保存条目的旧备注仍可兼容读取。
- 复验：浏览器输入“主体仍然可见，材质边缘需要单独确认”后点击 `应该更差` 和 `材质有问题`，备注始终保留，两个选项同时选中，进度未提交；主动复核定向测试 `9/9` 通过，全量 Python 测试 `394/394` 通过，浏览器控制台 `0 error/0 warning`。
- 预防：任何交互重渲染前必须区分 saved state 与 pending state；备注、选项和时间轴均不得在未确认时被服务端状态覆盖；复合反馈必须由“确认本条”统一提交。
- 状态：resolved。

## ERR-UNITY-065

- 日期：2026-09-03
- 任务：`vfx-2df.38.5` MPB 与 Shader global 完整动态材质插桩。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；回归 `runtime_capture_v2_regression_r004_global_mpb`。
- 原始命令：`workspace/tools/effectdemo_render_source.ps1 -Requests .../runtime_capture_v2_regression_r004_global_mpb/render_requests.json -ProjectPath .../EffectDemoPromptHumanR001 -NoUpm -PlayModeRuntime`，随后 `runtime_capture_regression finalize`。
- 原始现象：受控 script_material 探针已经得到 `global_shader_state_status=instrumented`、`has_unenumerated_property_block_values=false`、10 次 global delta，但仍为 `full_visual_training_eligible=false`；moving 探针因测试 Shader 新增 global 后未设置，画面 near-blank；回归报告 blocked。
- 影响：完整 global/MPB 证据不能晋级 full visual；同时测试 Shader 的未初始化 global 让 moving 可见性回归失败。
- 根因：旧门禁无条件排除所有 MonoBehaviour，不能区分受控时长脚本与未知脚本；moving 探针使用同一 Shader 但没有提供所需 global，且不能注册为“完整追踪”以免造成假阳性。
- 修复：新增 `IEffectDemoCaptureTimingProvider`，只有实现显式时长契约的脚本才不算未知时序；script_material 探针提供 1 秒契约。moving 探针直接设置 global 以恢复渲染，但不经过追踪器，故仍保持 `not_instrumented_missing_global_write`。回归门禁改为受控探针必须 full，其他类别仍不得 full。
- 复验：`runtime_capture_v2_regression_r005_global_mpb` 全部质量门禁通过；受控探针为 `full_visual_evidence`，11/11 有效帧、global value 1、global delta 10、MPB 未知 false；moving 可见但 full=false；instant/ground/ui 均保持 partial。Unity 日志无 C#、Shader 或运行异常。
- 预防：自定义脚本不得仅凭类型存在就永久阻塞，也不得默认视为完整；只有时长契约、global 写入追踪和 MPB 属性登记三者均满足时才允许 full visual。
- 状态：resolved。

## ERR-VFXDATA-011

- 日期：2026-09-03
- 任务：`vfx-2df.38.7.1` 命中类语义标签归一化与 r010 人工复核结算。
- 原始现象：类型词表同时存在 `impact/爆点/命中` 与 `hit/命中/受击`，表达同一类命中受击/爆点表现；r011 初版结算摘要按旧动作表生成，漏记了 11 条“特效元素错误”。
- 影响：类型分类空间重复，人工结算摘要不能完整反映元素维度修正；若直接训练会把同一命中类拆成两个类别。
- 修复：正式类型只保留 `impact`，中文统一为“命中/爆点”；`hit`、`命中/受击`、`爆点/命中` 仅作为兼容别名。新增正确的归一化结算摘要，伪标签同步分离元素字段与类型字段，`explosion` 不再作为元素候选。
- 数据产物：r010 已完成 32/32，r011 为 32 条 human_gold、0 exclusions；当前正式数据集 `prefab_five_layer_full_r009` 为 technical 2115、visual 102、AI pseudo 1188、human_gold 32；下一主动学习池 `prefab_active_full_r007` 为 70 个候选取 32；当前页面 `prefab_active_review_full_r014` 为 32 条，类型选项中 `hit=0`、`impact=1`，中文为“命中/爆点”。
- 复验：数据集 Schema/重复/AI 混入/覆盖门禁全 0；Python 全量测试 411/411 通过；Unity `projects verify` 为 0 errors / 0 warnings；页面图片加载失败 0、页面控制台无页面错误。
- 预防：新类型先经过语义归一化再进入词表；兼容别名必须有回归测试；元素、类型和颜色使用独立字段与训练任务；结算摘要必须按当前批次 `allowed_actions` 生成。
- 状态：resolved。

## ERR-VFXDATA-011

- 日期：2026-09-03
- 任务：`vfx-2df.38.7` Prefab 主动复核多选与确认交互。
- 工程与服务：评审数据 `workspace/data/vfx_generation/reviews/prefab_active_review_full_r005`；服务 `workspace.tools.vfx_generation.prefab_active_review`；本地地址 `http://127.0.0.1:8801/`。
- 原始现象：旧页面点击任一中文反馈按钮就立即提交，只能单选，无法同时记录“应该更差+材质有问题”等复合判断，也没有统一确认动作。
- 根因：前端按钮直接调用保存接口，反馈 schema 和后端只接受单个 `action`。
- 修复：前端增加待提交 `pendingActions`、多选按钮状态、`aria-pressed`、`确认本条` 和 `清除选择`；后端增加可选 `selected_actions` 兼容字段，保留旧 `action` 为首要动作。质量方向互斥，`AI判断正确` 单独使用，`无法播放/无法判断` 与其他选项互斥；多个问题合并为一个反馈记录并联合生成训练任务。
- 复验：浏览器实测两个问题同时选中时显示“待确认”，反馈进度不变且未发送保存请求；确认按钮默认禁用，确认后才提交；主动复核定向测试 9/9 通过，全量 Python 测试 394/394 通过，页面控制台 0 error/0 warning。
- 预防：结论保存必须经过显式确认；UI 待提交状态与服务端 `selected_actions` 一一对应；旧 v1 反馈仍按单动作兼容读取，新的复合反馈不得拆成多个独立样本。
- 状态：resolved。

## ERR-VFXDATA-010

- 日期：2026-09-03
- 任务：`vfx-2df.38.7` Prefab 主动复核反馈并发保存。
- 工程与服务：评审数据 `workspace/data/vfx_generation/reviews/prefab_active_review_full_r005`；服务 `workspace.tools.vfx_generation.prefab_active_review`；本地地址 `http://127.0.0.1:8801/`。
- 原始现象：连续提交同一 Prefab 的两个中文动作时，两个请求同时读取并直接覆盖 `feedback_store.json`。文件出现两个 JSON 文档交错，无法解析；当时 `feedback.jsonl` 保留了最后一次完整记录，首个 JSON 文档保留了较早修订。
- 根因：ThreadingHTTPServer 允许并发 POST，但 `save_feedback` 没有进程内锁；`write_text` 直接写最终文件，读者可能看到半写入文件，且并发请求之间存在丢失更新窗口。
- 修复：新增进程内 `RLock` 包围 read-modify-write；JSON 和 JSONL 统一先写同目录临时文件，再用 `os.replace` 原子替换；新增并发保存回归测试，验证 JSON 可解析、两个 revisions 都保留、latest 与 JSONL 一致。
- 数据恢复：停服后保留损坏原文件为 `workspace/progress/prefab-active-review-full-r005-feedback-store-corrupt-r001.json`；从损坏文件中的首个合法 JSON 文档和 `feedback.jsonl` 合并恢复 2 条修订，最终 latest 为最后一次 `无法播放`，并重写合法 store/JSONL。
- 复验：恢复后的 store JSON 可解析，`records=1`、`revisions=2`、JSONL latest ID 一致；评审页重新加载为 `prefab_active_review_full_r005`，进度 `1/16`，自动跳到第 2 条，图片 `640x360`，浏览器控制台 0 error/0 warning；主动复核定向测试 6/6 通过。
- 预防：服务重启或批次切换前先检查 store/JSONL；保存接口必须原子写入并串行化；反馈页面应避免重复提交导致无意义修订，但修订记录不能静默丢失。
- 状态：resolved。

## ERR-UNITY-062

- 日期：2026-09-03
- 任务：`vfx-2df.38.7` 修复 `Sword Slash 1` Capture v2 取景过远与视角错误。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoFullAssetsR001`；Unity `2022.3.16f1c1`；URP `14.0.9`；权威工程 `UnityDemo/EffectDemo`。
- 原始命令：`python -B -m workspace.tools.vfx_generation.full_prefab_capture_batch --baseline-root workspace/data/vfx_generation/datasets/prefab_graph_full_r002 --project-root UnityDemo/EffectDemo --output-root workspace/data/vfx_generation/captures/sword_slash_framing_r001 --batch-id sword_slash_framing_r001 --prefab-path "Assets/Hovl Studio/Sword slash VFX/Prefabs/Sword Slash 1.prefab" --previous-manifest workspace/data/vfx_generation/captures/full_prefab_capture_r002/capture_batch_manifest.json`；随后 `powershell -ExecutionPolicy Bypass -File workspace/tools/effectdemo_render_source.ps1 -Requests workspace/data/vfx_generation/captures/sword_slash_framing_r001/render_requests.json -ProjectPath workspace/unity-render-staging/EffectDemoFullAssetsR001 -NoUpm -PlayModeRuntime`。
- 根因：通用相机没有区分主体层和支撑层，也只有 front/side/top 三个世界轴视角；刀光类 Mesh 粒子应优先按主体 Mesh 包围盒和自身朝向取景，不能用全效果最大运动范围决定相机距离。时序上又把循环支撑层的最长发射周期误当成刀光视觉时长。
- 修复：新增独立 `subject_bounds`，对 Mesh ParticleSystemRenderer 和 slash 主体命名进行识别；相机选择优先主体包围盒，加入主体法线正反方向候选；slash 使用正交相机和稳定边距。对循环且无持续发射的主体，按 `delay+startLifetime` 估算单次视觉窗口；短特效将目标采样数提高到 20，并将最小间隔降到 `0.01s`；manifest 记录主体/组件时长和是否覆盖。批次工具新增 `--prefab-path` 单条重捕，评审工具新增 `--capture-override` 指定替换 manifest。
- 复验：`sword_slash_framing_r001` 为 1/1 候选、31/31 有效帧、0 无效帧、0 裁切、0 运行时错误；主体包围盒约 `9.59x7.10x7.10`，峰值可见面积 `0.0313976`，约为旧值 15.3 倍；峰值帧能显示完整蓝色弧形刀光。进一步的 `sword_slash_timing_r002` 记录组件最长周期 `4s`、主体窗口和最终总时长均为 `0.3s`，采样间隔 `0.015s`、21/21 有效帧、0 裁切、0 运行错误，峰值帧为 `frame_009_0_135.png`。Unity 日志 `Tundra build success`，无新增 C# 错误；仅保留已有 `ParticleDropdownController.audio` CS0108 警告。
- 预防：Capture 质量门禁继续保存全包围盒和主体包围盒，不把取景失败转成审美负例；发现方向性主体时优先按 `capture_category` 重捕单条并在评审批次中通过 override 更新，必须同时核对像素面积、裁切、实际图片和浏览器控制台。
- 状态：resolved。

## ERR-VFXDATA-003

- 日期：2026-08-30
- 任务：`vfx-2df.18.5` 自动识别 Shader CustomEditor 依赖并校验材质贴图闭包
- 工程：权威工程 `UnityDemo/EffectDemo`；工具 `workspace/tools/vfx_source_ingest.py`；真实样本 `Trains_FX_All_001/ArtResources/FX/Battle/Fx_com_sheilder`。
- 原始命令：`python -m workspace.tools.vfx_source_ingest --source UnityDemo/EffectDemo/Assets/VFXSourceIngest/Trains/Trains_shield_001 --output-dir .../Trains_shield_001_integrity_r002 --source-unity-project UnityDemo/EffectDemo --resolve-project-guids`。
- 原始现象：历史来源 manifest 中的 `Trains_shield_001` 路径已不在当前工程，但工具把空输入写成 `material_count=0`、`gate=passed`、`shader_count=0` 的假阳性报告。
- 根因：摄入器只在扫描后派生报告，没有在入口验证 source path 是否存在或扫描结果是否为空；完整性检查也只枚举所选目录内 `.mat`，未追踪 Prefab 指向的选区外共享材质。
- 修复：入口不存在或无可摄入资产时立即失败；材质完整性审计扩展为选中资产加 Prefab GUID 直接引用的外部 Material。新增 `ingest_integrity_report.json`，对 `m_Texture` GUID 的缺失/错误类型和全 Assets 材质 GUID 重复设为失败门禁；同时记录 texture/shader/script/mesh 等 GUID 引用类型和 Shader `CustomEditor` 目标解析状态。
- 复验：`workspace.tests.test_vfx_source_ingest` 16/16 通过，新增覆盖空路径、选区外材质、未解析 `m_Texture`、重复 Material GUID、显式许可 ShaderGUI 受控复制。真实 `Fx_com_sheilder` 复验为 3 Material、36 个 `m_Texture` 槽（9 resolved、27 合法 unbound）、0 重复 Material GUID、`LWGUI.LWGUI` 在目标 `Assets/Editor/ThirdParty/LWGUI/LWGUI.cs` 可用。
- 预防：不允许以零文件、零材质或零 Shader 的报告宣称摄入完成；完整性检查必须沿 Prefab -> Material -> Texture/Shader 直接依赖跨目录追踪。`CustomEditor` 缺失是 Inspector 依赖，需标为 `needs_manual_dependency`，不能混同为运行时贴图丢失。
- 状态：resolved。

## ERR-UNITY-061

- 日期：2026-09-02
- 任务：`vfx-2df.38.4` 新 Prefab 首批 Capture v2。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoFullAssetsR001`；Unity `2022.3.16f1c1`；`-noUpm -PlayModeRuntime`。
- 原始命令：`effectdemo_render_source.ps1 -Requests .../full_prefab_capture_r001/render_requests.json -ProjectPath .../EffectDemoFullAssetsR001 -NoUpm -PlayModeRuntime`。
- 原始错误：执行到 61/64 时，`EffectDemoRuntimeCaptureController.ExecuteAfterLateUpdate` 重新抛出 `ArgumentException: An item with the same key has already been added. Key: _InvFade`；来源为 `EffectDemoMaterialStateRecorder.CompareProperties` 的 `ToDictionary`。批次不再推进，Unity 进程保持运行，人工终止后包装脚本返回退出码 `-1`。
- 根因：`BuildDescriptors` 已用 HashSet 收集 Shader 属性名，却忽略 `names.Add(name)` 的返回值，仍把第三方 Shader 重复声明的 `_InvFade` 写入属性数组；比较阶段假定属性名唯一并直接 `ToDictionary`。
- 影响：前三个 Hovl Sword Slash Prefab 未生成 manifest；这是捕获器聚合错误，不是 Prefab 不可播放或审美负例。已有 61 条结果保留在 r001，不并入正式五层视觉集。
- 修复：属性描述采集只在 `names.Add(name)` 成功时写入；比较阶段新增 `LastPropertyByName`，按属性名分组并确定性保留最后值，兼容外部 Shader 的重复声明。完整重建同一 64 条 r002，不覆盖 r001。
- 复验：r002 完成 64/64 Capture v2、1411 个有效帧、0 无效帧、0裁切、0运行错误；57 条 `visual_feature_ready`、7 条 `technical_only`。重复属性契约测试通过。
- 预防：第三方 Shader 属性名不能假定唯一；所有外部列表转 Dictionary 前必须显式定义重复键策略。批次中断不得把缺失输出转换成技术或审美负例。
- 状态：resolved。


## ERR-UNITY-054

- 日期：2026-08-30
- 任务：`vfx-2df.18.12.2.1` 为 EffectDemo 2022 材质时间线候选重建 WebGL 动态评价入口
- 工程：权威工程 `UnityDemo/EffectDemo`；最终隔离构建工程 `workspace/unity-render-staging/EffectDemoWeb2022R008`；Unity `2022.3.16f1c1`；URP `14.0.9`；输出 `workspace/Builds/WebGL/VfxTrainingPlayer2022MaterialR005`。
- 原始命令：`powershell -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1 -ProjectPath ...EffectDemoWeb2022R002 -OutputPath ...VfxTrainingPlayer2022MaterialR003 -TrainingReviewBundle .../webgl_review_bundle.json -AuthoritativeProjectPath UnityDemo/EffectDemo`。
- 原始错误：`UnityEditor.dll assembly is referenced by user code, but this is not allowed.`；禁用复制的 `Assets/VFXSourceIngest/Compat/UnityBuiltinAssemblies/UnityEngine.UI.dll` 后，`ParticleImage` Runtime 又报 `UnityEngine.UI does not exist`、`MaskableGraphic` / `VertexHelper` 找不到。
- 根因：R002 在 `-noUpm` 下不加载内置 `com.unity.ugui`，此前为让 `ParticleImage` 编译而放入的插件 DLL 引用了 `UnityEditor.CoreModule`。该 DLL 可以通过 Editor 编译，却作为用户程序集进入 WebGL linker，Player 侧必然失败；只复制 PackageCache 或临时以 embedded package 启动正常 UPM 也不能稳定建立该依赖图。
- 修复：最终 staging 只保留 UGUI `Runtime` 源码及 `UnityEngine.UI.asmdef` 于 `Assets/VFXSourceIngest/Compat/UnityUGUI/Runtime/`，不复制 UGUI `Editor` 目录；R008 不包含旧 `UnityEngine.UI.dll` 插件。`build_vfx_web_player.ps1` 新增可选 `-UsePackageManager`，默认保持原 `-noUpm` 行为，避免把包管理器策略硬编码为唯一入口。主工程的 Prefab、材质、贴图、Shader 和包清单均未改动。
- 复验：R008 先通过 `unity projects verify`（0 error / 0 warning），再获得 `Build Finished, Result: Success` 和 Unity 退出码 `0`；manifest 为 `prefabCount=3`、`trainingLinkedPrefabCount=3`、`truthCaptureMode=play_mode_runtime`，产物包含 data `3,087,892` bytes、framework `373,136` bytes、wasm `17,257,982` bytes。浏览器在 `http://127.0.0.1:8786/` 嵌入 `http://127.0.0.1:8784/`，实际收到 Unity 2022 `f1c1` catalog/runtime 事件；`FX_BossTips`、`Fx_com_sheilder` 可见且有非零活动粒子，`Fx_Gun_Fire` 保留为固定镜头主体过小的技术/视觉风险。
- 预防：任何为 `-noUpm` staging 增补的 Unity Runtime 类型，先检查程序集引用链；禁止把含 `UnityEditor*` 的预编译 DLL 当作 Player 兼容层。优先使用只含 Runtime 源码与 asmdef 的隔离兼容层，并以真实 WebGL 浏览器统计和像素截图验收。旧插件文件即使平台禁用也会与同名 asmdef 冲突，新 staging 必须不携带该文件。
- 状态：resolved。


## ERR-UNITY-053

- 日期：2026-08-30
- 任务：`vfx-2df.18.15` 为 near-blank MaterialTrajectory 恢复 UI/ParticleImage 上下文
- 工程：权威工程 `UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoWeb2022R002`；Unity `2022.3.16f1c1`；URP `14.0.9`
- 原始现象：两个使用 `AssetKits.ParticleImage.ParticleImage` 的 UI Prefab 在执行器中没有普通 `Renderer`，引入 Runtime 后 `-noUpm` 编译报 `UnityEngine.UI does not exist`、`MaskableGraphic` 和 `VertexHelper` 找不到；即使脚本编译后，UI 截图仍为纯背景。
- 根因：`-noUpm` 绕过了 staging 的内置 `com.unity.ugui` 程序集；UI Graphic 使用组件级 `mainTexture` 和 Canvas 网格，不是普通 Renderer 的 `sharedMaterials`/MPB；隔离捕获相机为容纳 UI RectTransform 自动移动到约 `z=-203`，但原 `farClipPlane=100` 将 UI 完全裁掉。
- 修复：当时 staging 以一个复制的 `UnityEngine.UI.dll` 使 ParticleImage Runtime 得以编译；执行器增加 Graphic 材质匹配、World Space Canvas、组件纹理绑定和基于 ParticleImage 实际 `Position/Size/Color/UV` 的捕获 Mesh 代理；CanvasRenderer 的 UI MPB 请求如实适配为材质控制并在结果写入 `effective_control_scope=material`；捕获相机远裁剪面提升为 `1000`。该 DLL 后续被证明不适用于 WebGL Player，最终 Player 侧兼容策略见 `ERR-UNITY-054`；主工程源 Prefab、材质和贴图序列化引用未改动。
- 复验：staging 编译日志 `effectdemo-particleimage-context-compile-final.log` 为 `Tundra build success` 且无 CS 错误；正式 `material_trajectory_context_r030` 为 28/28 pass、308/308 有效帧、0 Schema error、0 candidate leak、0 RenderTexture leak、10 条可见并可进入图像监督；`mtc_045` 可见面积最大约 `0.994`，`mtc_054` 最大约 `0.0084`；Unity 日志无新增 `Material trajectory execution failed` 或运行时异常。
- 预防：`-noUpm` staging 必须显式检查 UGUI/其他内置包的 ScriptAssemblies；UI Graphic 不能按 MeshRenderer 处理，必须保留组件纹理和 Canvas/Particle 网格上下文；相机重定位后必须重新校验 near/far clip；MPB 控制不可伪装成 CanvasRenderer 真值，必须记录有效控制范围。
- 状态：resolved


## ERR-VFXDATA-002

- 日期：2026-08-29
- 任务：`vfx-2df.18.19` Prefab 动态截图时间轴。
- 原始现象：循环或长 Duration 粒子被采到 8 秒，最大帧间隔 0.25 秒，人工评价页出现过长截图序列。
- 根因：默认 `max_duration_seconds=8`、`max_interval_seconds=0.25`；循环粒子的 Duration 被直接视为完整审查窗口。
- 修复：默认改为最长 3 秒、最多每 0.1 秒一帧；新 run `trains_prefab_playmode_r004_short_window` 重新采集全部 79 条可独立播放 Prefab。
- 复验：79/79 ready、最长 3.0 秒、最大相邻采样间隔约 0.1 秒；浏览器中 `FX_BossTips` 为 0.00s、0.10s 至 3.00s 共 31 帧。
- 预防：评价/训练预览窗口与源特效的理论循环总时长不同；长循环只保留起势、峰值和早期残留窗口。
- 状态：resolved。


## ERR-VFXDATA-001

- 日期：2026-08-29
- 任务：`vfx-2df.18.19` 全量 Prefab 动态评价与 WebGL 复核。
- 原始现象：评价页将 `trains_fx_005_eff_glow_box_blue` 标记为“当前无有效输出/未纳入 WebGL”；用户在 Unity Editor 中确认该 Prefab 可以播放。
- 影响：旧批次把 79 条 `particle_playable` 中的 20 条误排除，只渲染和构建了 59 条；未采集被错误表达得接近“无法播放”，会污染人工评价与后续训练样本选择。
- 根因：旧 case eligibility 将 source manifest 的 `source_missing` / `unknown` dependency edge 作为 Play Mode 候选硬门槛，即使 Unity 审计已证明 Prefab 无 Missing Material、无 Missing Script 且有自包含 ParticleSystem/Renderer。
- 修复：`prefab_structure_dataset` 改为以 Unity audit 的 `technical_status=particle_playable` 决定 Play Mode 候选；source dependency health 继续作为来源完整性风险保留，不再否决运行验证。重新执行 `trains_prefab_playmode_r003_all_particle_playable`，重建 r003 数据集、79 条 WebGL catalog 与 `prefab_human_review_r005_all_webgl`；已有 `trains_fx_001_fx_acid` 人工反馈通过 Schema 迁移保留。
- 复验：79/79 candidate `ready`、1420/1420 valid PNG；`Eff_glow_box_blue` 为 11/11 valid frame、材质时间线 ready、auto-eval warn（固定镜头主体面积 0.003845，不是播放失败）。浏览器从空页面直接选择该条后，WebGL 运行同名 Prefab、路径匹配、有 14 个活动粒子且画面可见。
- 预防：来源依赖扫描、独立 Play Mode、固定镜头可见性与人工审美是不同维度。source edge 异常不得覆盖 Unity 的实际可播放性；无帧只能写“待验证”，不能写“无法播放”。
- 状态：resolved。


## ERR-UNITY-051

- 日期：2026-08-29
- 任务：`vfx-2df.18.19` 全量 Prefab 人工评价页接入 Unity 2022 WebGL 动态预览。
- 工程：隔离 staging `workspace/unity-render-staging/EffectDemoWeb2022R002`；Unity `2022.3.16f1c1`；URP `14.0.9`；输出 `workspace/Builds/WebGL/VfxTrainingPlayer2022PrefabReviewR002`。
- 原始命令：`Unity.exe -noUpm -batchmode -quit -projectPath ...EffectDemoWeb2022R002 -buildTarget WebGL -executeMethod VfxPrefabWeb.Editor.VfxWebPlayerBuilder.BuildFromCommandLine`。
- 原始错误：`Shader error in 'VFX/YOYO Shader URP': Couldn't open include file 'Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl'. at line 145`；首次构建仍显示 `Build Finished, Result: Success`，但 YOYO 的 GLES3 program 为 0。
- 影响：59 条 WebGL catalog 中的 `source_prefab_037_fx_jk_zidan02` 与 `source_prefab_038_fx_jk_zidan03` 通过 4 个材质引用 YOYO shader，不能把该错误当成未使用 shader 忽略。
- 根因：staging 以 `-noUpm` 构建，Unity 2022 中国版不会为 registry URP 包挂载 `Packages/com.unity.render-pipelines.universal/...` include 路径；复制 `Library/PackageCache` 和 `Library/PackageManager/ProjectCache` 都不能建立该虚拟 package include 映射。尝试正常 UPM 启动还复现 ERR-UNITY-046：`Failed to resolve packages: The "path" argument must be of type string. Received undefined. No packages loaded.`。
- 修复：仅在 staging 的同 GUID `YOYO Shader.shader` 中，将该 package include 改为 `UnityCG.cginc` 的等价兼容宏（纹理采样、对象到裁剪/世界空间、世界视线向量）；主工程 shader、manifest 与材质均未改动。URP/Core/Config package cache 和本地 overlay 仅用于 staging 诊断。
- 复验：最终 WebGL 日志 `shaderErrors=0`，含 `Compiling shader "VFX/YOYO Shader URP"` 与 `Build Finished, Result: Success`；`vfx_web_build_manifest.json` 为 Unity `2022.3.16f1c1`、`prefabCount=59`、`trainingLinkedPrefabCount=59`。浏览器选择 `trains_fx_024_fx_conecold` 后，iframe 内实际切换到 `Fx_conecold` 并显示动态蓝色粒子；选择 YOYO 关联的 `trains_fx_136_fx_jk_zidan02` 时运行时有 2 个 Renderer、重播峰值有 68 个粒子。
- 预防：WebGL 构建不能只看 exit code 或 manifest。先以 Prefab 依赖闭包确认报错 shader 是否被实际 catalog 引用；若 staging 必须 `-noUpm` 且 UPM 正常解析复现 ERR-UNITY-046，环境兼容改动只能存在于 staging，并在浏览器中验证受影响样本后记录限制。
- 已知非致命警告：WebGL console 仍报告源 Prefab 的 `The referenced script on this Behaviour ... is missing!`。这是导入源的上下文缺失信号，不会被页面或训练数据改写为人工质量结论；相关条目继续保留技术状态和上下文限制。
- 状态：resolved。


## ERR-UNITY-050

- 日期：2026-08-28
- 任务：`vfx-2df.18.14` MaterialTrajectory 全量课程执行
- 工程：`UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoWeb2022R002`；Unity `2022.3.16f1c1`
- 原始现象：R001 第 13 条抛出 `InvalidOperationException: Material Mat_xingzhe_glow [MaterialTrajectoryRuntime] does not expose property _UseUIAlphaClip.`。
- 影响：`.mat` YAML 的历史保存字段被误当作当前可执行 Shader 参数，课程规格不成立。
- 根因：Material Binding Audit r2 只记录 Texture 槽；生成器从 YAML 读取 float/color 时没有与 `Shader.GetProperty*` 当前 API 求交集。
- 修复：Audit 升级 r3，记录每个 Material 当前 Shader 的属性名与类型；生成器只保留类型匹配的 float/range/int/color/vector，并区分 Color/Vector。保留 R001 失败证据，生成 R002。
- 复验：r3 审计 730 Material、36,343 Shader 属性；`Mat_xingzhe_glow` 的 49 个有效属性不含 `_UseUIAlphaClip`。R002 100/100 执行通过、0 Schema error。
- 预防：不得把 Unity YAML 保存字段等同于当前 Shader API；任何材质参数课程必须使用 Unity API 属性审计过滤。
- 状态：resolved

## ERR-UNITY-052

- 日期：2026-08-29
- 任务：`vfx-4w2` Trains Prefab 导入断链复核与 EffectDemo 审计修复
- 工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`
- 工具：Unity 2022.3.16f1c1、Unity Pipeline、`workspace.tools.bd_guard`、PowerShell 源/目标 YAML 对照
- 原始现象：Prefab 审计 r2 报告 73 个 Prefab、114 个缺失材质槽；用户反馈部分 Trains 特效之前可播放、当前导入后不可见。另发现两个 Shared TMP 资产包含 `<<<<<<<`、`=======`、`>>>>>>>` SVN 冲突标记。
- 根因：审计器把 Renderer 的合法空材质槽 `{fileID: 0}` 和嵌套 Prefab 中的源空槽计为缺失；两个孤立 TMP 资产是未完成冲突合并的无效 Unity YAML。严格源/目标对照后，只有 1 个非零材质引用真正断链，且源工程本身也缺少该 GUID。
- 修复：`EffectDemoPrefabPlayabilityAudit.cs` 升级到 r3，按 Renderer `GlobalObjectId`/组件 fileID 读取源 Prefab 的序列化材质槽，分别记录真实缺失材质、原生空槽和缺失 Shader；将两个无引用冲突资产完整备份至 `workspace/repair-quarantine/unity-conflict-assets-20260829` 后移出 `Assets`。
- 编译复验：Unity Pipeline `recompile_status` 返回 `completed`、`failed=false`、`errors=[]`；首版 fileID 比较的 `long/ulong` 歧义已修复。
- 审计复验：259 个 Prefab，126 个直接可播放，94 个上下文依赖，37 个空/无效；`missing_material=1`、`serialized_empty=113`、`missing_shader=0`。唯一断链为 `Fx_xingzhe_zhuangunzi` 的 `6bca70b520d27ed41b9f612c4b3334cb`，源工程无对应资产，不做猜测绑定。
- 已知限制：实时 Pipeline 调用同步执行完整审计会超过默认 5 秒并返回超时，但 Editor 继续完成并写入报告；通过延迟回调和文件时间确认报告已生成。该次没有覆盖已有人工反馈，也没有把源缺失引用伪装成可用材质。
- 预防：审计材质槽必须同时检查序列化 `{fileID: 0}`、嵌套 Prefab 源组件和非零 GUID；导入工具必须把源工程缺失、目标缺失、脚本上下文缺失分开记录；Unity 工程 Assets 内禁止保留未解决 VCS 冲突标记。
- 状态：resolved


## ERR-UNITY-049

- 日期：2026-08-28
- 任务：`vfx-2df.18.14` MaterialTrajectory 批量容错
- 原始现象：全量 R001 在第 13 条 LateUpdate 回调抛属性错误后停在 12/100，Unity 不退出。
- 根因：父执行器用 `yield return StartCoroutine(ExecuteAfterLateUpdate(...))`；嵌套协程异常由 Unity 调度器记录，未回传到外层手动 `IEnumerator.MoveNext` 容错层。
- 修复：父迭代器手动驱动 LateUpdate 子迭代器；异常在父 `MoveNext` 中抛出，由逐条容错写 error result 后继续。
- 复验：定向批次先执行已知坏规格 `mtc_013`、再执行正常 `mtc_014`；前者写 `error`，后者 `pass`，Unity 正常退出。R002 全量 100 条正常完成。
- 预防：需要逐项隔离的批处理不能把关键异常边界交给嵌套 `StartCoroutine`；必须让异常回到批次控制器。
- 状态：resolved


## ERR-UNITY-048

- 日期：2026-08-28
- 任务：`vfx-2df.18.14` MaterialTrajectory Play Mode 启动
- 原始错误：进入 Play Mode 后 `NullReferenceException` at `ConfigureCaptureRig`；`requestManifest` 为 null，batch 进程不退出。修复序列化后，正例又被错误投影为 `negative_trajectory`。
- 根因：Bootstrap 在 Domain Reload 前通过普通字段传入 request/spec/Material/Texture，重载后字段丢失；Unity 对可序列化嵌套 class 的 JSON null 又会恢复为空对象。
- 修复：request 与 prepared item 全部设为 Unity 可序列化字段；可选 clamp 和 negative mutation 用显式 `has_*` 标志，不以引用 null 表达；启动失败主动 `EditorApplication.Exit(1)`。
- 补充弯路：主 Editor 热导入同时变化的 Runtime/Editor 脚本时，曾短暂出现 Bootstrap 已引用 `has_negative_mutation` 而旧 Assembly-CSharp 尚未包含该字段的 `CS1061`；同一次 Asset Refresh 随后重新编译 Runtime，再编译 Editor，连续出现 `Tundra build success` 并完成程序集重载。最终 staging 全量编译日志也为 success。
- 复验：后续 smoke/full 均正常进入 Play Mode、完成并主动退出；正例不再出现虚假 `negative_trajectory`。
- 预防：Editor Bootstrap 到 Play Mode 的状态必须考虑 Domain Reload；可选嵌套对象使用显式存在标志。
- 状态：resolved


## ERR-UNITY-047

- 日期：2026-08-28
- 任务：`vfx-2df.18.14` MaterialTrajectory staging 编译
- 原始错误：`Assets/VFXCapture/EffectDemoMaterialTrajectoryExecutor.cs(7,7): error CS0246: The type or namespace name 'Newtonsoft' could not be found`。
- 根因：主工程当前 PackageCache 有 Newtonsoft，但旧 staging 在 `-NoUpm` 下没有该可选包引用；执行器对外部 JSON 包形成了不必要依赖。
- 修复：执行器和 Bootstrap 改用 Unity 内置 `JsonUtility`；Python request 将 nullable clamp 转成 `has_min/has_max + value` 结构化适配。
- 复验：staging Tundra 编译成功，后续全部 smoke/full 正常运行。
- 预防：Unity 训练运行时代码优先使用工程保证存在的 API；可选 UPM 包必须在隔离工程验证，不依赖主工程 Library 偶然状态。
- 状态：resolved


## ERR-UNITY-046

- 日期：2026-08-28
- 任务：`vfx-2df.18.14` 新建隔离 staging 首次启动
- 原始命令：Unity `-batchmode -projectPath .../EffectDemoMaterialTrajectoryR001 -executeMethod EffectDemoMaterialTrajectoryBootstrap.StartFromEnvironment`。
- 原始错误：`Failed to resolve packages: The "path" argument must be of type string. Received undefined. No packages loaded.`；退出码 1。
- 根因：空 Library 的 Unity 2022 中国版 UPM 在该 embedded package 组合上收到空 resolve 参数；新 staging 尚无可复用 PackageCache。
- 修复：改用此前已完整解析并验证的 `EffectDemoWeb2022R002` staging，同步主工程最新 `Assets/Packages/ProjectSettings`，使用 `-NoUpm` 保持已有包图。
- 复验：后续 Unity 批次均通过启动与 Tundra 编译，R002 全量退出码 0。
- 预防：Unity 2022 隔离执行优先复用已验证 PackageCache；新空 Library 必须先单独完成包解析验收，不能与训练批次首次运行合并。
- 状态：resolved


## ERR-UNITY-045

- 日期：2026-08-28
- 任务：`vfx-2df.18.14` MaterialTrajectorySpec Unity 执行器
- 工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`；Unity `2022.3.16f1c1`；URP `14.0.9`
- 原始操作：Unity Editor 监测 `Assets/VFXCapture/EffectDemoMaterialTrajectoryExecutor.cs` 后自动编译。
- 原始错误：`Assets\\VFXCapture\\EffectDemoMaterialTrajectoryExecutor.cs(302,25): error CS1061: 'IEnumerator' does not contain a definition for 'Dispose'`；第 308 行同错。
- 影响：`Assembly-CSharp` 编译停止，MaterialTrajectory smoke 不能启动。
- 根因：`System.Collections.IEnumerator` 接口不声明 `Dispose()`；编译器生成的迭代器通常同时实现 `IDisposable`，但不能通过 `IEnumerator` 静态类型直接调用。
- 修复：两处清理改为 `(routine as IDisposable)?.Dispose()`，既释放支持清理的迭代器，也兼容只实现 `IEnumerator` 的实现。
- 复验：当前 Unity Editor 重新导入脚本后日志出现 `Tundra build success (2.39 seconds), 9 items updated, 645 evaluated`，随后完成 `Reloading assemblies after finishing script compilation`，不再出现该 `CS1061`。
- 弯路：尝试 `dotnet build Assembly-CSharp.csproj --no-dependencies` 做独立复验，但 Unity 生成工程依赖尚未单独产出的 `com.xuanxuan.*`、URP Editor 等程序集而报 `CS0006`；该命令不能替代当前工程的 Unity/Bee 编译，改以正在运行的 Unity Editor Tundra 结果验收。
- 预防：手动驱动非泛型 `IEnumerator` 时只通过 `IDisposable` 安全转型释放；Unity 工程编译以 Editor/Bee 或完整 Unity batchmode 为准，不把缺生成依赖的单项目 `dotnet build` 结果误判为源码错误。
- 状态：resolved


## ERR-UNITY-044

- 日期：2026-08-28
- 任务：`vfx-2df.18.11` EffectDemo 逐帧材质状态时间线
- 工程：`UnityDemo/EffectDemo`；Unity `2022.3.16f1c1`
- 原始命令：`powershell -ExecutionPolicy Bypass -File workspace/tools/effectdemo_render_source.ps1 -Requests .../material_state_probe_r001/render_requests.json -ProjectPath .../EffectDemoWeb2022R002 -NoUpm -PlayModeRuntime`
- 原始现象：采集器在每个采样点 `yield return new WaitForEndOfFrame()`；Unity 2022 `-batchmode` 进入 Play Mode 后停在第一帧，不生成 PNG、capture manifest 或 material timeline，进程持续不退出。去掉 `-batchmode` 并隐藏 Editor 仍无法可靠恢复该 yield。
- 根因：Unity 的 `WaitForEndOfFrame` 依赖可渲染 Game View/帧尾调度，在 batchmode 或隐藏 Editor 环境中不会稳定恢复；它不适合作为自动训练采集屏障。
- 修复：`EffectDemoRuntimeCaptureController` 设置 `[DefaultExecutionOrder(32000)]`，采样请求在其他脚本 Update/LateUpdate 后由控制器 LateUpdate 执行；同一回调内先读取 Material/MPB，再 `Camera.Render`。时间线记录 `capture_order=late_update_barrier -> material_snapshot -> camera_render`，manifest 记录 `material_capture_sync=late_update_execution_order_32000`。包装脚本恢复 batchmode，并修复相对 `-logFile` 未解析为绝对路径的问题。
- 复验：受控探针在 batchmode 生成 `11/11` PNG、11 帧 material timeline、30 条 delta，捕获贴图替换、Keyword、Material 实例、MPB 和溶解变化；5 个真实 Trains Prefab 生成 `119/119` PNG 和 `5/5` ready timeline，且正确报告 `0` delta；全部 timeline 和 run manifest Schema 校验 `0 errors`。
- 预防：自动化采集禁止在 batchmode 使用 `WaitForEndOfFrame`；必须记录实际同步机制。任何“帧尾”声明都要用会完成的真实运行样本验证，进程退出和证据文件缺一不可。
- 状态：resolved


## ERR-UNITY-043

- 日期：2026-08-28
- 任务：`vfx-2df.18.12.2` 将 WebGL 训练播放器纠正到 EffectDemo 2022
- 工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`；Unity `2022.3.16f1c1`；URP `14.0.9`
- 原始命令一：`unity install-modules --editor-version 2022.3.16f1c1 --module webgl --yes --accept-eula --proxy http://127.0.0.1:7897 --format json`
- 原始命令二：`Unity.exe -noUpm -batchmode -quit -projectPath .../EffectDemoWeb2022R001 -buildTarget WebGL -executeMethod VfxPrefabWeb.Editor.VfxWebPlayerBuilder.BuildFromCommandLine ...`
- 原始错误：Unity CLI 实际使用国际版 revision `d2c21f0ef2f1` 的 `2022.3.16f1` WebGL 安装器；R001 构建退出码为 `0`，但浏览器报 `Invalid serialized file version. Expected version: 2022.3.16f1. Actual version: 2022.3.16f1c1`、`Failed to initialize player` 和 `SendMessage: object VfxWebPlayer not found`。
- 影响：文件存在、CLI 模块清单和 WebGL 构建成功都不能证明 Player 可运行；R001 页面目录为 0，不能作为训练复核入口。
- 根因：中国版 Editor revision 为 `2f3f1b3bde89`，序列化版本带 `f1c1`；Unity CLI 从国际版 `modules.json` 安装了 `f1` PlaybackEngine，Editor 与 PlayerSupport 二进制不匹配。
- 修复：从 Unity 中国 `2022.3.16` 官方发布页读取 `https://download.unitychina.cn/download_unity/2f3f1b3bde89/TargetSupportInstaller/UnitySetup-WebGL-Support-for-Editor-2022.3.16f1c1.exe`；直接下载后验证 Authenticode `Valid`，签发者为优三缔科技（上海）有限公司；覆盖安装到同一 Editor。为排除 Bee/IL2CPP 缓存，创建全新 `EffectDemoWeb2022R002` 隔离副本重新构建，并换用新端口避免浏览器 IndexedDB 旧缓存。
- 复验：R002 WebGL 构建退出码 `0`，日志包含 `Build Finished, Result: Success`；manifest 的 `unityVersion=2022.3.16f1c1`，Catalog 为 5 个 EffectDemo Trains Prefab；浏览器 `http://127.0.0.1:8772/` 显示 `Unity 2022 Web`、`5 / 5 项`、运行时已连接；`FX_qiangkouhuo` 在 `0.25x`、约 `0.07s` 实际显示橙色枪口火焰。R002 Wasm `12,234,972` bytes。
- 已知警告：默认 5 项含源 Missing Script，WebGL 还警告 Physics Module stripped；UI 将条目标记为“需要上下文”，不允许未绑定材质时间线时记录训练反馈。
- 预防：中国版 `f1c1` Editor 的平台模块必须来自同 revision 的 Unity 中国发布页；不得以模块目录、CLI `modules` 字段或 build exit code 单独验收，必须检查浏览器序列化版本、Catalog、运行时错误和真实像素。构建后换端口或清缓存，避免 IndexedDB 复用旧 Player 数据。
- 状态：resolved


## ERR-UNITY-032

- 日期：2026-08-28
- 任务：`vfx-adl` Unity WebGL Prefab 特效播放器重复构建
- 工具：Unity CLI `build`、Unity Licensing Client
- 原始命令：`pwsh -NoProfile -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1`
- 退出码：最终 `0`
- 环境：Windows；主工程 `E:/UnityVFX/EffectDemo6.0`；Unity `6000.5.9f1`；URP `17.5.0`
- 完整错误：启动阶段先记录 `HandshakeResponse reported an error: Unsupported protocol version '1.18.3'`、`Failed to handshake to channel: LicenseClient-luxinyu` 和 `LicensingClient has failed validation; ignoring`。
- 影响：Unity CLI 将三行识别为 `editorErrors`，但 Editor 随后启动版本匹配的 `LicenseClient-luxinyu-6000.5.9`，不阻塞编译或 WebGL 构建。
- 根因：机器上已有共享 Licensing Client 的协议版本与 Unity `6000.5.9f1` 不匹配；Editor 会自动回退到版本内置客户端。
- 修复：不绕过授权；等待日志出现版本匹配客户端成功握手、entitlement 解析和有效许可证，再继续构建。
- 复验：多次构建均出现后续 `Successfully connected to LicensingClient on channel: LicenseClient-luxinyu-6000.5.9`、`Successfully resolved entitlement details`、`Build Finished, Result: Success`，Unity 退出码 `0`。
- 预防：不能只因前置 handshake error 判定授权失败，也不能无条件忽略；必须同时检查后续成功握手、entitlement、构建结果和退出码。若任一缺失则停止并处理许可证。
- 状态：mitigated



## ERR-UNITY-031

- 日期：2026-08-28
- 任务：`vfx-adl` Volume Profile 生成器幂等性复验
- 工具：Unity CLI `build`、`AssetDatabase.AddObjectToAsset`
- 原始命令：`pwsh -NoProfile -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1`
- 退出码：Unity Editor `1`；Unity CLI `6`
- 环境：Windows；主工程 `E:/UnityVFX/EffectDemo6.0`；Unity `6000.5.9f1`；URP `17.5.0`
- 完整错误：`Couldn't add object to asset file because the MonoBehaviour 'Bloom' is already an asset`，随后 `UnityException: Adding asset to object VfxWebVolumeProfile failed`，`executeMethod ... BuildFromCommandLine threw exception`。
- 影响：修复 Volume 子资产后的第一次重复构建在资产准备阶段停止；已有首版 WebGL 输出未被删除或破坏。
- 根因：使用 `AssetDatabase.IsSubAsset(component)` 判断组件是否已经持久化；该 API 对当前已加载 Volume 子资产返回了不适合此场景的结果，导致重复调用 `AddObjectToAsset`。
- 修复：改为检查 `AssetDatabase.GetAssetPath(component)`；只有路径为空的内存对象才执行 `AddObjectToAsset`。
- 复验：单独资产准备退出码 `0`；随后多次重复 WebGL 构建均成功，Volume Profile 组件没有重复，`Build Finished, Result: Success`。
- 预防：Unity 子资产生成器的幂等性必须用实际 AssetDatabase 路径或 `AssetDatabase.Contains` 判断，并至少执行两次完整生成/构建复验；不能只在首次创建上验证。
- 状态：resolved



## ERR-UNITY-030

- 日期：2026-08-28
- 任务：`vfx-adl` Unity WebGL Prefab 特效播放器 Volume 配置
- 工具：Unity CLI `build`、URP Volume Profile、构建后 Analytics
- 原始命令：`pwsh -NoProfile -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1`
- 退出码：构建 `0`，但日志含构建后异常
- 环境：Windows；主工程 `E:/UnityVFX/EffectDemo6.0`；Unity `6000.5.9f1`；URP `17.5.0`
- 完整错误：构建成功后 `UnityEditor.Rendering.Analytics.VolumeProfileOverridesAnalytic.TryGatherData` 在 `volumeComponent.GetType()` 抛出 `NullReferenceException`。
- 影响：首版 WebGL 文件成功生成，但构建日志不干净；`VfxWebVolumeProfile.asset` 的 Bloom、Tonemapping、ColorAdjustments 没有可靠持久化，不能作为稳定后处理配置。
- 根因：代码调用 `profile.Add<T>()` 后只保存父 `VolumeProfile`，没有将三个 `VolumeComponent` 作为子资产加入 AssetDatabase；重新导入后 `components` 列表变为三个 `fileID: 0`。
- 修复：生成前清理 null component；新建组件后调用 `AssetDatabase.AddObjectToAsset(component, profile)`，再保存资产。
- 复验：YAML 中三个组件引用均为非零 fileID，Bloom/Tonemapping/ColorAdjustments 子对象完整；后续成功构建日志不再出现该 `NullReferenceException`。
- 预防：任何包含 ScriptableObject 子对象的 `.asset` 生成器都必须验证子对象是否真实成为 sub-asset；保存后重新导入并检查引用，不能只看内存中的列表。
- 状态：resolved



## ERR-UNITY-029

- 日期：2026-08-28
- 任务：`vfx-adl` Unity WebGL Prefab 特效播放器
- 工具：Unity CLI `install-modules`、Unity Hub 安装日志、`curl.exe`
- 原始命令：`unity install-modules --editor-version 6000.5.9f1 --module webgl --yes --accept-eula --retries 2 --format json`
- 退出码：`1`
- 环境：Windows；主工程 `E:/UnityVFX/EffectDemo6.0`；Unity `6000.5.9f1`；URP `17.5.0`；Unity CLI `1.0.0-beta.6`
- 完整错误：Unity CLI 返回 `INSTALL_FAILED: 1 个项目安装失败`；`unity logs` 显示 `Module webgl failed to install: Response status was 404`；Hub 日志确认官方 URL 被地域重定向到 `download.unitychina.cn`，对象键 `TargetSupportInstaller/UnitySetup-WebGL-Support-for-Editor-6000.5.9f1.exe` 尚不存在。
- 影响：首次无法安装 Web Build Support，因此不能生成真实运行 Prefab 的 WebGL 构建；未修改 Unity 项目资产。
- 根因：Unity 中国 CDN 尚未同步 `6000.5.9f1` 的 WebGL 模块，不是磁盘空间、权限、项目或 WebGL 代码问题。
- 修复：先用 `curl.exe --proxy http://127.0.0.1:7897` 对官方 URL 做 HEAD，确认返回 `200 OK` 和 `Content-Length: 1103357320`；再执行 `unity install-modules ... --proxy http://127.0.0.1:7897`。
- 复验：代理安装退出码 `0`；`WebGLSupport` 目录存在且约 `5.51 GB`；`unity editors --installed --format json` 显示 `6000.5.9f1` 的 `modules` 为 `Web`。
- 预防：模块安装收到快速 404 时先查 `unity logs` 和 Hub `info-log.json`，区分地域镜像未同步与安装器故障；使用 Unity CLI 显式 `--proxy`，不要全局修改系统代理；安装后必须同时验证模块清单和 PlaybackEngines 目录。
- 状态：resolved



## ERR-UNITY-028

- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 模型/粒子角色重构
- 工具：C# Editor 命令局部编辑、Unity recompile
- 现象：将 FastStrike 从 Mesh 承载切换为局部 Billboard 粒子时，插入新方法后旧 `ConfigureBladeLayer` 方法体残留为孤立代码块，导致 C# 语法结构不完整。
- 根因：局部文本替换只插入了新方法，没有同步删除旧方法签名/方法体边界。
- 影响：角色分工重构第一次无法编译，不能验证 Core/Dark 模型、FastStrike 粒子的区分。
- 修复：恢复完整 `ConfigureBladeLayer` 签名和方法体，单独保留 `ConfigureStrikeLayer`；重新编译。
- 复验：角色分工测试 `7/7 OK`；Unity recompile `failed=false`；配置命令成功；返回角色为 `model_carried_layer` / `localized_strike_particle`；Console error `0`。
- 预防：新增 Editor 方法时必须读取完整相邻区域，检查签名/大括号配对；契约测试后再触发 Unity 编译；不要用宽泛文本替换覆盖方法边界。
- 状态：resolved



- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 模型/粒子职责重构
- 工具：Unity Editor ParticleSystemRenderer、配置命令、确定性截图
- 现象：第一次结构纠偏把 Core、Dark、FastStrike_A/B 全部改成完整刀光 Mesh 承载，仍与教程不一致；教程的快速打击层应使用更简单贴图和局部粒子反馈。
- 根因：把“主体和暗底复制模型”的教程事实过度推广到快速冲击层，没有区分连续轮廓和短时局部反馈。
- 影响：快速层继承完整主体形状，画面会产生重复刀光/重影，命中层职责不清。
- 修复：保留 CoreBody/DarkBase 的 Mesh ParticleSystem；FastStrike_A/B 改为 Billboard ParticleSystem，使用局部发射形状、简单快速层材质、0.10/0.14s 延迟、短生命周期和空间错位。
- 复验：角色分工测试 `7/7 OK`；配置返回 Core/Dark 为 `model_carried_layer`、FastStrike 为 `localized_strike_particle`；Console 0；角色分离截图 manifest 已生成。
- 预防：制作前先判断层是否定义连续轮廓；模型用于主体/支撑，粒子用于局部/短时/离散反馈；每层记录承载方式和关闭后的预期变化，不能只记录层名和数量。
- 状态：resolved



- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 刀光层结构重构
- 工具：Unity Editor ParticleSystem API、确定性模拟和截图
- 现象：重构配置命令在粒子系统仍处于播放态时修改 `main.duration`，Unity Assert：`Setting the duration while system is still playing is not supported`。
- 根因：配置命令没有在修改 Main 模块前停止并清空粒子系统。
- 影响：命令返回配置结果，但 Console 出现 Assert，不能作为干净结构验证证据。
- 修复：进入 `ConfigureBladeLayer` 后先调用 `ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear)`，再设置 duration、delay、lifetime 和其他模块。
- 复验：重新编译成功；配置命令成功；Console error 0；重构干净截图和 manifest 生成成功。
- 预防：任何 Editor 配置命令在修改正在播放的 ParticleSystem Main/Emission/Shape 前，必须显式 StopEmittingAndClear；采样前后都检查 Console。
- 状态：resolved



- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 刀光贴图筛选和材质绑定
- 工具：资源库扫描、Pillow Alpha 分析、Unity `import_asset`、`set_material_properties`、`get_material_properties`
- 现象：首轮材质三份纹理槽全部为 `null`；后来直接用同一张旧 Orange 主体贴图冒充 Base/Mask/Dissolve，未完成候选筛选和职责分离。
- 根因：资产准备只做了材质占位和颜色参数，没有执行“候选贴图 -> 通道/透明分析 -> 正式导入 -> 材质引用 -> 回读”的完整数据链；并错误地把本地制作的授权记录当成资源进入工程的阻塞条件。
- 影响：第一轮截图不能验证真实刀光纹理，材质层次和方向性溶解没有可信输入。
- 修复：从资源库分析候选 Alpha 包围盒和透明比例，选择 `Slash_01.tga` 作为主体、`Particle_Gradient_Slash_01.png` 作为快速层、`trail0092.png` 作为暗底/流动；从各自 Alpha 生成独立 Mask，通过 Unity `import_asset` 获取 GUID，再分别绑定 Core/Dark/FastStrike 的 Base、Mask 和 Dissolve 槽。
- 复验：三份材质回读均显示具体纹理 asset path/GUID，`unknown[]=[]`；`projects verify` 0 errors/0 warnings；Console error 0；带贴图六帧和 manifest 已生成。
- 预防：本地制作允许资源直接进入 Unity，但必须记录来源和用途；对外发布时另行检查分发状态。每份材质必须回读 Base/Mask/Dissolve 非空，不能用同一张图无证据承担所有功能。
- 状态：resolved



- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 刀光复刻主体 Mesh 绑定
- 工具：Unity Editor C# 命令、AssetDatabase、FBX MeshImporter
- 现象：用 `AssetDatabase.LoadAssetAtPath<Mesh>` 读取复制的 FBX，并直接访问/添加 CoreBody 的 MeshFilter 时，命令报“没有 MeshFilter attached to CoreBody”。
- 根因：FBX 路径对应模型主资产/子资源集合，不能假设主对象可直接转为 Mesh；粒子承载对象与静态 Mesh 承载职责混在同一对象也增加了组件访问边界。
- 影响：候选主体模型第一次绑定失败，场景保持脏但未保存错误结构。
- 修复：使用 `AssetDatabase.LoadAllAssetsAtPath` 遍历并取得第一个 Mesh 子资源；在 `CoreBody/CoreMesh` 创建独立 MeshFilter + MeshRenderer，CoreBody 保留 ParticleSystem。
- 复验：配置命令成功；层级回读显示 CoreMesh 两个组件；模拟返回 `staticMeshPresent=true`；六帧截图和 manifest 写入成功；Console error 0。
- 预防：FBX 进入 Unity 前必须枚举/检查子 Mesh、轴向、Pivot、UV 和包围盒；粒子与静态承载体分开；不要把组件存在性假设为已满足。
- 状态：resolved

## ERR-UNITY-024

- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 刀光复刻 Editor 命令维护
- 工具：C# 文件编辑、Unity `recompile_status`
- 现象：插入 `LoadFirstMesh` helper 时误替换 `ConfigureBladeLayer` 方法签名，只剩方法体，Unity 报大量 CS1519、CS0106、CS1022 语法错误。
- 根因：按相邻文本片段做替换时没有确认被替换文本是否包含方法签名，编辑后未立即读取附近代码结构。
- 影响：所有自定义 Editor 命令暂时无法注册，不能执行 Mesh 绑定或截图模拟。
- 修复：读取文件 85–155 行，恢复完整 `private static object ConfigureBladeLayer(...)` 签名；重新编译并轮询 `recompile_status`。
- 复验：`recompile_status` 返回 `completed, failed=false, errors=[]`；配置命令成功；Console error 0。
- 预防：C# Editor 命令编辑后立即读取变更区域；先跑静态契约测试，再调用 Unity 编译；禁止用可能吞掉方法声明的宽泛替换。
- 状态：resolved



- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 刀光复刻层级骨架
- 工具：Unity CLI `create_gameobjects`
- 现象：创建 `BladeRoot` 子对象时把 `/BladeRoot` 作为 `parent` 传入，Pipeline 将其解析为 Git Bash 当前盘符下的文件系统路径 `C:/Program Files/Git/BladeRoot`，返回找不到 GameObject。
- 根因：`parent` 参数要求 Unity ObjectRef/GlobalObjectId，不能凭层级路径格式猜测。
- 影响：第一次子对象创建失败；没有修改或删除已有场景对象。
- 修复：使用创建根对象返回的 `GlobalObjectId_V1-2-f6e1b96d959d47946908849b8afc820b-1489055133-0` 作为 parent，四个子对象随后创建成功。
- 复验：层级回读显示 `BladeRoot/CoreBody`、`DarkBase`、`FastStrike_A`、`FastStrike_B` 四层；每层包含一个 ParticleSystem 和 ParticleSystemRenderer；场景保存成功。
- 预防：Unity CLI 对象引用优先使用返回的 GlobalObjectId；命令 schema 和返回 handle 必须保留，不能把层级路径当作通用引用。
- 状态：resolved



- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 刀光复刻材质准备
- 工具：Unity CLI `create_asset`、`set_material_properties`、`get_material_properties`
- 现象：首次为三份材质设置 `_SrcBlend` 时返回 `unknown property`，虽然 Shader CBUFFER 已有该字段，但材质无法回写源混合状态。
- 根因：Shader `Properties` 块遗漏 `_SrcBlend` 声明；仅在 HLSL CBUFFER 声明不足以让 Unity 材质暴露属性。
- 影响：CoreBody、DarkBase、FastStrike 的 Alpha/Add 混合职责无法可靠落盘，不能进入层级制作。
- 修复：在 Shader `Properties` 中补充 `[Enum(UnityEngine.Rendering.BlendMode)] _SrcBlend`，重新导入后重新设置三份材质。
- 复验：三份材质 `set_material_properties` 均返回 `_SrcBlend`、`_DstBlend` applied 且 `unknown[]` 为空；`get_material_properties` 回读正确；Console error 0；projects verify 0 errors/0 warnings。
- 预防：Shader 新增 CBUFFER 参数时必须同步检查 Properties；材质写入后必须检查 `unknown[]` 并回读资产，不能只看 CLI success。
- 状态：resolved



- 日期：2026-08-26
- 任务：`vfx-t3m` 阶段 4 刀光复刻 Shader 资产准备
- 工具：Unity CLI `projects verify`、`list_shaders`、`get_shader_properties`、Python unittest、Git Bash
- 现象：新建 `BladeReproduction/Shaders/BladeSurface.shader` 后，首次项目校验报告目录和 Shader 缺少 `.meta`；首次契约测试还发现混合状态未由材质控制、Custom Data 未接入 UV、溶解没有明确方向坐标。
- 根因：新增 Unity 资产尚未完成元数据生成；第一版 Shader 只建立了属性外观，没有闭合教程所需的三个行为契约。
- 影响：项目完整性校验暂时失败；不能直接进入材质和层级制作。
- 修复：等待 Unity Editor 导入并生成目录/文件 `.meta`；补充 `_SrcBlend`、`_DissolveDirection`，让 `input.customData.xy` 参与 UV 流动，并让方向坐标参与 Dissolve 阈值。
- 复验：契约测试 `3/3 OK`；`list_shaders` 显示 `VFX/Blade/BladeSurface` 且 `isSupported=true`；`projects verify` 为 `0 errors, 0 warnings`；Unity Console `0 errors`。
- 预防：新增 Unity 资产后先检查 `.meta` 和项目校验；Shader 行为先用契约测试覆盖透明混合、Custom Data 和方向性溶解，再进入材质/场景制作；CLI 命令必须先查询可用命令和参数 schema，不能猜命令名。
- 状态：resolved



- 日期：2026-08-25
- 任务：`vfx-t3m` 两小时刀光教程 `70:00–90:00` 补学
- 工具：旧版 `workspace/tools/transcribe_orange_blade_70_80_segment.py`、FFmpeg、faster-whisper
- 现象：`70:00–80:00` 学习记录实际引用了 `01:10–01:20` 音频；`80:00–90:00` 字幕为空，导致教程窗口被错误标记为无有效语音证据。
- 根因：旧脚本直接使用 `audio/BV1mjvxBgESJ_01-10_to_01-20.wav`，却把时间偏移写成 `70*60`；未从完整 `BV1mjvxBgESJ_16k_mono.wav` 按绝对时间切片复核。
- 影响：上一轮审计低估了 `70:00–90:00` 的直接教程证据，阶段 3 不应据此停止学习或开始猜测。
- 修复：从完整 02:08:01 音频准确切出 `4200–4800s` 和 `4800–5400s`，使用本地缓存 faster-whisper small 模型重新生成 `BV1mjvxBgESJ_70-80_audio_relearn.srt` 和 `BV1mjvxBgESJ_80-90_audio_relearn.srt`。
- 复验：两段转写均完成，语言识别为中文；新增记录确认暗层、两层延后快速打击层、`0.1s` 延迟、Alpha/Add、Mask 方向和 UV 调整等教程内容。
- 预防：转写脚本必须显式接收源音频绝对路径、切片起止秒和时间偏移；运行前用 `ffprobe` 校验切片范围，输出中记录源文件、起止秒和模型路径；空字幕不得直接解释为无语音。
- 状态：resolved


- 日期：2026-08-25
- 任务：`vfx-dew` Unity刀光截图工具
- 工具：Unity CLI Pipeline `simulate_orange_slash_at_time`
- 现象：批量采样首次传入项目路径 `E:\\E:\\UnityVFX\\EffectDemo6.0`，全部返回 `Not a Unity project`。
- 根因：循环命令误把已包含盘符的绝对路径再次拼接；与 Unity 场景或截图无关。
- 影响：本轮未执行采样或写入截图。
- 修复：恢复使用已确认的连接工程路径 `E:\\UnityVFX\\EffectDemo6.0`。
- 复验：八个时间点的确定性模拟均成功，找到 4 个 ParticleSystem 和静态 Mesh。
- 预防：批量命令固定使用单一绝对项目路径，执行前打印并检查路径格式。
- 状态：resolved

## ERR-UNITY-019

- 日期：2026-08-25
- 任务：`vfx-dew` Unity刀光截图工具
- 工具：Unity CLI Pipeline `capture_game_view`
- 现象：截图请求传入 `--save-path`，返回 `capture_game_view 没有参数 --save-path。您是指 --save_path 吗？`。
- 根因：Pipeline 参数使用下划线命名，批量命令误用连字符。
- 影响：确定性模拟成功但八张截图均未写入。
- 修复：改用 `--save_path`，保留 `source=camera`、1280x720 和 Main Camera 参数。
- 复验：待完成正确参数采集后验证 PNG 文件和 manifest。
- 预防：批量调用前从 `unity command --query capture_game_view` 读取 schema，不凭 CLI 习惯猜参数名。
- 状态：mitigated


- 日期：2026-08-24
- 任务：`vfx-2zo.3` 烟花
- 工具：文件编辑
- 现象：修复烟花脚本时误编辑了中文源工程 `E:/Unity特效人工智能学习/UnityDemo/EffectDemo6.0`，而不是当前主工程 `E:/UnityVFX/EffectDemo6.0`。
- 根因：两个工程存在同名脚本，编辑前没有执行主工程路径确认。
- 影响：源工程脚本被同步修改；ASCII 主工程未立即得到修复；没有破坏场景资源。
- 修复：将修复后的脚本显式复制到 ASCII 主工程，并将后续制作目标固定为 `E:/UnityVFX/EffectDemo6.0`。
- 验证：后续只对 ASCII 项目执行 `unity command --project-path E:/UnityVFX/EffectDemo6.0`；待编译完成后重新发现 `build_fireworks`。
- 预防：每次编辑 Unity 脚本前先读取/确认绝对路径；源工程和主工程同名文件禁止凭相对路径编辑。
- 状态：mitigated

## ERR-VISUAL-001

- 日期：2026-08-25
- 任务：`SRC-2026-GAMEVFX-001` 第01集逐帧视觉学习
- 工具：文件 Read 图片展示、浏览器替代页、PIL、FFmpeg
- 现象：Read 工具读取 JPG/PNG 时不返回可人工判读的图像内容；尝试本地 HTTP 页面时，环境已有多个 Python 服务占用端口并映射到其他根目录，出现 404，替代浏览器通道未能建立稳定复核页。
- 根因：抽帧文件本身正常，但当前会话的图片展示通道没有返回图像；浏览器替代服务端口被旧进程占用，路径根目录不一致。
- 影响：无法在当前通道完成逐张人工视觉标注；不影响视频、音频、转写和帧文件生成。
- 调查与复验：PIL 可正常打开帧，格式为 JPEG/PNG，尺寸 `640x360`；`file` 检查通过；9段共447张帧的相邻帧像素差异非零，Part01-09平均相邻变化约 `15.39–38.86`，证明视频内容和抽帧真实变化。报告保存为 `frames/visual_analysis_report.json`。
- 修复/替代：生成客观帧统计报告和 `frames/dense_manifest.json`，保留人工视觉门禁为未通过；不把像素统计或字幕推断冒充人工视觉学习。
- 预防：视觉任务必须同时保留原视频、关键帧、展示通道状态和人工判读结论；展示通道失败时只能标记 blocked，不得升级为 visual verified。
- 状态：blocked_environment

## ERR-VISUAL-002

- 日期：2026-08-26
- 任务：`vfx-t3m` 刀光参考/Unity 连续画面复核
- 工具：Read 图片展示、Browser Use 本地 HTTP 复核页、Unity CLI 场景查询
- 现象：当前会话的图片展示通道和浏览器 WebView 偶发不可用；Read 返回空结果，浏览器打开本地对比图时返回 `browser guest not attached (webview not ready)`。同时 additive 加载 `SampleScene` 与 `BladeReproduction` 后，场景中存在两个同名 `Main Camera`，按名称截图会造成取景来源不确定。
- 根因：展示宿主连接状态不稳定；截图场景没有强制唯一相机和唯一对象引用。
- 影响：无法可靠确认参考帧或 Unity 帧的主体轮廓、方向、材质和节奏；已有 PNG、manifest、像素统计只能作为机器证据，不能升级为人工视觉通过。
- 修复方案：建立统一“视觉可见性标准”；每次任务先用已知 PNG 做展示 smoke test，再以唯一目标相机和唯一对象引用采集连续帧；展示通道未实际呈现画面时将状态保持为 `blocked_environment`。
- 复验要求：成功呈现参考和 Unity 的起势、峰值、收束三个时间点后，记录相对路径、时间点、展示通道、可见观察和置信度；在此之前不写入视觉结论、不关闭 `vfx-t3m`。
- 预防：禁止用文件存在、可解码、像素差异、HTTP 200、Unity 命令成功或元数据统计代替人工观看；additive 场景必须检查重复相机并使用 GlobalObjectId/唯一名称绑定截图。
- 状态：blocked_environment

### ERR-VISUAL-002 结论修正

- 用户复核确认：`E:/UnityVFX/EffectDemo6.0/Assets/Art/VFX/BladeReproduction/Evidence/Captures_TimingTrial/` 中的 Unity 截图内容是正确的。
- 修正判断：Unity `capture_game_view`、PNG 文件和当前刀光截图证据有效；失败的是本模型会话的 Read/图片展示接口没有把 PNG 视觉内容可靠呈现给模型。此前将“我无法读取”扩大表述为“截图内容不可靠”是错误的。
- 后续规则：用户或其他可见通道确认截图正确时，保留 Unity 截图为有效工程证据；仅将模型视觉读取状态记为 `model_visual_read_blocked`，不得否定 PNG 或 Unity 结果本身。模型未实际看到画面时，不得补写具体视觉观察。



- 日期：2026-08-24
- 任务：`vfx-2zo.3` 烟花
- 工具：Unity CLI Pipeline `write_text_file` / `import_asset`
- 现象：使用 `write_text_file` 传入带 `\n` 的脚本内容后，文件最初被写成包含字面量反斜杠和 `n` 的单行 C#，Unity 报 `CS1056 Unexpected character '\\'` 等编译错误；修正为真实换行后，直接 `import_asset` 覆盖又遇到文件被 Unity 占用。
- 根因：CLI JSON/参数层对文本换行进行了额外转义；同时 Unity 编译期间锁定当前脚本文件。
- 影响：自定义烟花命令未及时注册，Editor 编译状态延长；未破坏场景资源。
- 修复：先用 ASCII 主工程中的绝对路径确认文件，再用真实多行内容写入工程外临时文件 `E:/UnityVFX/VfxFireworksCommands.tmp.cs`，通过 Pipeline `import_asset --source ... --path Assets/Editor/VfxFireworksCommands.cs --confirm true` 导入；等待 `editor_status` 为 `ready` 后重新查询命令表。
- 验证：Console 最新错误为 0；`configure_fireworks_launch` 和 `create_fireworks_particles` 已注册并执行成功；场景层级、Launch 参数和 Play Mode 已复核。
- 预防：多行 C# 不直接依赖命令行转义；优先使用真实文件内容加 Pipeline 导入；导入后必须等待 `compiling=false`、`domainReloadInProgress=false`、`status=ready`，再发现和执行命令。
- 状态：resolved

## ERR-UNITY-012

- 日期：2026-08-24
- 任务：`vfx-2zo.3` 烟花
- 工具：Unity CLI Pipeline
- 现象：导入扩展后的烟花 Editor 脚本时，编译/域重载期间 `editor_status` 短暂出现网络错误，Pipeline 请求断开。
- 根因：Unity 正在重新编译程序集并重启/重绑定 Pipeline Server，服务端在域重载窗口不可用。
- 影响：不能在该窗口查询命令或执行配置；未造成场景或脚本数据损坏。
- 修复：等待 `editor_status` 返回 `status=ready`、`compiling=false`、`domainReloadInProgress=false` 后重新查询命令表；随后五个阶段命令均注册成功并执行。
- 验证：Console error 数量为 0；五个 `configure_fireworks_*` 命令成功；五阶段参数回读成功；Play Mode 进入/退出成功；`projects verify` 为 0 errors、0 warnings。
- 预防：Unity 脚本导入后禁止固定时间立即调用命令；必须按状态条件等待，再重新发现命令。
- 状态：resolved


- 日期：2026-08-24
- 任务：`vfx-v29.1` 全量模型索引两模型验收
- 工具：Git Bash `/usr/bin/time`
- 原始命令：`/usr/bin/time -p python -m workspace.tools.model_index.cli build-all --root E:/Unity特效人工智能学习/resource --output E:/Unity特效人工智能学习/workspace/data/model_index/full --limit 2 --blender C:/Program Files/Blender Foundation/Blender 5.0/blender.exe --timeout 300 --json`
- 退出码：127
- 环境：Windows 10；Blender 5.0；工程 `E:/Unity特效人工智能学习`
- 完整错误：`/usr/bin/bash: line 15: /usr/bin/time: No such file or directory`
- 影响：首次验收未启动 Blender，资源未修改；输入资源校验快照已生成。
- 根因：该 Git Bash 环境没有 `/usr/bin/time` 可执行文件。
- 修复：改用 Python `time.monotonic()` 包装 CLI 主函数测量耗时。
- 复验：Python `time.monotonic()` 包装的真实两模型命令退出码 0，2/2 成功，耗时 7.430 秒；`--resume` 再跑 2/2 skipped，耗时 2.404 秒。
- 预防：Windows Git Bash 中不假定 GNU time 存在；耗时统计使用 Python 标准库或 shell 内建 `time`。
- 状态：resolved

## ERR-UNITY-013

- 日期：2026-08-24
- 任务：`vfx-2zo.3` 烟花视觉复核
- 工具：Unity CLI Pipeline `editor_play` / 自定义播放命令 / `screenshot`
- 现象：在未确认 Play Mode 状态时调用 `play_fireworks`，第一次请求短暂断连；随后截图连续一致，实际捕获的是静态 Game 视图，不能证明烟花峰值已被截图。
- 根因：Play Mode 切换和 Pipeline 域状态存在时序窗口；五个 ParticleSystem 设置为 `playOnAwake=false`，直接进入 Play Mode 不会自动播放。
- 影响：第一次截图证据无效；未修改错误场景数据。
- 修复：增加显式 `play_fireworks` 命令；严格等待 `editor_status=playing` 后调用；在约 `0.65s`、`0.90s`、`1.60s` 分别截图，并对 PNG 做像素差异检查。
- 验证：三张运行截图差异区域非空且覆盖画面主体范围；性能统计和 `projects verify` 均成功。
- 预防：任何视觉截图前必须确认 `editor_status=playing`，显式触发非 `playOnAwake` 的粒子系统，并至少采集两个时间点做差异检查。
- 状态：resolved

## ERR-MODEL-INDEX-002

- 日期：2026-08-24
- 任务：`vfx-v29.1` 工作区测试
- 工具：Python pytest
- 原始命令：`python -m pytest workspace/tests -q`
- 退出码：1
- 环境：Windows 10；Python 3.14；工程 `E:/Unity特效人工智能学习`
- 完整错误：`No module named pytest`
- 影响：无法用 pytest 重复运行测试；不影响仓库既有 unittest 测试入口。
- 根因：当前 Python 环境未安装 pytest，项目也未声明 pytest 依赖。
- 修复：使用仓库现有标准库命令 `python -m unittest discover -s workspace/tests -p 'test_*.py'`。
- 复验：完整 unittest 套件 49 项全部通过。
- 状态：resolved

## ERR-VFXLIB-001

- 日期：2026-08-25
- 任务：`vfx-hzm` VFX.library 视觉参考媒体索引
- 工具：Python `workspace.tools.vfx_library_index` CLI
- 原始命令：`python -m workspace.tools.vfx_library_index.cli scan --root E:/BaiduNetdiskDownload/VFX.library --output E:/Unity特效人工智能学习/workspace/data/resource_index/vfx_library --source-id SRC-2026-VFXLIB-001`
- 退出码：1
- 完整错误：`UnboundLocalError: cannot access local variable 'probe_media' where it is not associated with a value`
- 影响：真实扫描未开始；仅生成了输入媒体快照，未读取/修改外部媒体内容。
- 根因：为实现 `--no-probe` 时留下的占位语句 `del probe_media` 删除了函数参数绑定，导致后续列表推导引用未绑定局部变量。
- 修复：移除错误的 `del probe_media`，保留参数并将其传递到单文件记录函数；新增 `probe_media=False` 回归测试。
- 复验：`python -m unittest workspace.tests.test_vfx_library_index_scanner -v`，4 项全部通过；待重跑真实扫描。
- 预防：命令行参数增加后必须覆盖默认路径和显式禁用路径；真实大批量扫描前先运行最小 fixture 和 CLI smoke test。
- 状态：resolved


## ERR-VFXLIB-004

- 日期：2026-08-25
- 任务：`vfx-430` VFX.library 第一批连续画面复核
- 工具：本地 `review_server_cli`、浏览器复核容器、本地 PNG 读取
- 现象：复核服务可以启动，但浏览器打开 `http://127.0.0.1:8877/` 时返回 `browser guest not attached (webview not ready)`；直接读取标准化 PNG 仍返回空结果。
- 根因：当前会话的浏览器显示容器未附着，图像读取工具也没有返回像素画面；不是 FFmpeg 抽帧失败。
- 影响：本轮不能可靠查看连续画面，未写入任何视觉观察，未创建高置信度卡片，未启动 Unity 实验。
- 修复：保留本地复核服务、真实帧映射和队列状态；等待浏览器容器恢复后从 `review_queue.json` 首项继续。不能用尺寸、亮度或文件存在性替代视觉判读。
- 复验：服务启动命令已执行；此前首帧曾成功返回 `/frames/b61f997fe187_start.png`，本轮浏览器重新附着失败；PNG 读取仍为空。
- 预防：视觉观察必须同时满足可见画面、连续时间点和证据绑定；任一显示层阻塞时保持任务进行中，不把机器统计升级为视觉事实。
- 状态：blocked


- 日期：2026-08-25
- 任务：`vfx-430` VFX.library 连续画面视觉复核
- 工具：浏览器图像读取/截图服务；本地 `review_server_cli`
- 现象：FFmpeg 能生成 PNG 代表帧，但直接图像读取返回空结果；本地浏览器截图曾报 `browser screenshot activity capture failed for guest`，无法稳定判读连续画面。
- 根因：阻塞位于显示/查看层，而不是媒体解码层；浏览器直接加载原始 GIF/视频和截图服务的活动捕获路径不稳定。
- 影响：只能完成机器抽帧和客观量化，不能形成绑定时间点的视觉观察；来源保持 `experimental`，批次保持 `partial`。
- 修复：新增本地连续画面复核插件，将证据时间点标准化为 PNG，通过仅监听 `127.0.0.1` 的 HTTP 服务提供队列、时间点、播放、逐帧和观察保存；服务不读取或修改外部素材目录。
- 复验：连续读取器测试 2/2、服务清单测试 2/2、观察记录测试 3/3 通过；CLI `--help` 成功；待在浏览器中实际打开本地服务并确认帧画面后，才允许生成高置信度视觉观察。
- 预防：后续视觉复核统一使用工作区内标准化 PNG 和本地服务；每条观察必须绑定 `relative_path`、`sha256`、时间标签和置信度，禁止把机器候选或队列顺序当作视觉事实。
- 状态：mitigated


- 状态：mitigated

## ERR-VFXLIB-005

- 日期：2026-08-25
- 任务：`vfx-430` VFX.library 连续画面复核服务诊断
- 工具：`review_server_cli`、Python HTTP 客户端、浏览器复核容器、Pillow
- 现象：首帧 PNG 可由 Pillow 正常打开为 `400x400 RGBA`；复核服务 `/api/manifest` 和 `/frames/b61f997fe187_start.png` 均返回 HTTP 200；浏览器新建页面仍返回 `browser guest not attached (webview not ready)`。
- 根因：媒体解码、PNG 文件、HTTP 服务和帧映射均正常，失败边界位于当前会话浏览器宿主的 WebView 附着层。
- 影响：可以独立验证媒体和服务，但当前会话无法通过浏览器宿主完成可视判读；不得把 HTTP 200 或 PNG 存在性当作视觉观察。
- 修复：增加 `/health` 健康检查；保留独立 HTTP/Pillow 验证路径；复核服务改为可在新端口启动，避免复用失效页面或残留会话。
- 复验：Pillow 读取成功；`/api/manifest` 返回 200；首帧 URL 返回 200；`/health` 接口用于后续启动诊断。
- 预防：视觉复核诊断按媒体层、文件层、HTTP 层、浏览器宿主层分层；只有浏览器实际呈现画面后才写视觉观察。
- 状态：mitigated

## ERR-UNITY-015

- 日期：2026-08-25
- 任务：`vfx-8su` / `EXP-2026-010` Orange课程刀光正式源切换与视觉门禁
- 工具：Unity CLI Pipeline `create_orange_slash_ab` / `recompile_status` / `instantiate_prefab` / `capture_game_view` / `get_component_properties`
- 现象：早期正式生成器把 `Assets/Art/VFX/Samples/ResourceSmokeTest/Meshes/SM_VFX_Slash_Curve.FBX` 当作 Orange 刀光主体来源；重建后旧场景实例未自动替换，导致回读和截图仍可能对应旧状态。初次运行三帧像素差异为空，不能证明刀光；组件回读还显示旧实例的 MeshRenderer 材质为 null。
- 根因：验证样本目录与正式课程源资产边界未隔离；Prefab 资产重建不会自动刷新场景实例；首次生成时把未持久化的内存 Material 直接绑定到正式对象，造成保存/重载后的引用不可靠。
- 影响：产物不能升级为 verified；之前的截图只能作为失败证据，不能称为课程刀光完成。
- 修复：将资源库原始 `resource/特效模型/600特效模型/UE4特效模型FBX/刀光/SM_VFX_Slash_Curve.FBX` 及实际检索到的刀光/Spark 贴图复制到 `Assets/Art/VFX/Orange/Slash/Source/`；生成器改为只读取该目录；删除旧 A/B/ribbon 生成路径；正式产物改为 `OrangeSlash_Final.prefab`；重建前删除旧实例并重新实例化；Material 创建后保存并从资产路径重新加载再绑定。
- 验证：源模型 hash `42fa5e1099f8d31e5966f68d56f1f3501754b2d3b66fc34619cca2133a7dfc97` 与资源索引一致；`recompile_status failed=false`；`projects verify errors=0 warnings=0`；Prefab YAML 已出现有效 Material GUID；最新场景层级包含 `SlashBody`、`SlashMotion`、`DarkSupport`、`Highlight`、`HitPoint`。运行截图已保存，但浏览器视觉读取未成功，人工轮廓门禁仍未完成。
- 预防：正式效果禁止引用 `ResourceSmokeTest`；Prefab 重建后必须删除并重载场景实例；必须同时检查源资产路径、Prefab YAML GUID、运行状态和人工视觉截图；文件存在、像素变化和组件层级不能替代轮廓门禁。
- 状态：mitigated

## ERR-UNITY-016

- 状态：resolved

## ERR-UNITY-017

- 日期：2026-08-25
- 任务：`vfx-8su` / `EXP-2026-010` 相机取景与动态视觉门禁
- 工具：Unity CLI `get_component_properties` / `set_component_properties` / `capture_game_view` / `save_scene`；Blender FBX 检查；Pillow
- 现象：Main Camera 原为正交相机，位置 `(0,0,-5)`、单位旋转、正交尺寸 `3`；刀光主体在画面中心但只占约 `102x89` 像素。将正交尺寸改为 `1.15` 后保存，Play Mode 新截图与旧空帧仍无像素差异。
- 根因：原相机取景确实过远，但空画面/不可判读问题不只由取景造成；材质、实例状态、渲染可见性或 Play Mode 时序仍有未闭合边界。
- 影响：相机修正只能作为诊断结果，不能作为视觉修复完成；Orange 实验继续保持 `experimental`。
- 修复：通过 `set_component_properties` 将 Camera 的 `orthographic size` 调为 `1.15`；通过 `save_scene` 持久化；不继续修改粒子和材质参数。
- 复验：`save_scene` 成功；场景 YAML 中确认 `orthographic size: 1.15`；FBX 包围盒检查为约 `1.919x1.682x0.645`；Play Mode 截图请求恢复后成功保存，但与旧空帧差异为 `None`。
- 预防：视觉门禁必须同时检查模型包围盒、相机位置/旋转/投影、实例状态、材质绑定和连续运行帧；相机调整后必须重新验证主体占屏和人工轮廓，不能仅凭相机参数变化宣布修复。
- 状态：mitigated

## ERR-VISUAL-003

- 日期：2026-08-27
- 任务：`vfx-t3m` BladeReproduction 连续 UV 主体候选
- 工具：Blender 5.0 headless、Unity CLI Pipeline `import_asset` / `configure_blade_reproduction_skeleton` / `capture_game_view`、Codex 原生图片读取。
- 现象：早期派生 OBJ 在 Blender 预览可见尖端弧线，但 Unity 运行截图一度变成浅弧；另一版 OBJ 开启 `_TipFadeWidth` 或 `_CoreBandStrength` 时出现沿弧线的密集条纹/分段，DarkBase 也被同类问题污染。
- 根因：第一版 OBJ 使用了错误的导出平面轴；后续 UV 写入按 loop 的顺序错误映射，导出面引用发生 UV 环绕，导致 Shader 按 `input.uv` 计算的端部渐隐和核心带跨面跳变。
- 影响：不能把 Blender 静态预览当作 Unity 视觉验收；条纹会破坏主体连续性和层级，早期截图只能保留为失败证据。
- 修复：生成器 `workspace/tools/generate_blade_arc_mesh.py` 改为 Unity 可见平面轴，并按每个 `mesh.loop` 的顶点索引重建连续 `uv.x`；最终使用 `SlashArc_Bezier_ContinuousUV.obj`，保留错误 OBJ 但不再绑定。DarkBase 关闭 UV 端部渐隐并清空纹理。
- 复验：Blender 读取最终 OBJ 的 `UV_RANGE=0..1`，每个相邻 quad 的 U 连续递减；Unity 编译 `failed=false`、项目校验 `0 errors/0 warnings`、Console error `0`；V5 `frame_0420/0600/0700/0820.png` 经 Codex 原生图片通道实际查看，不再出现该 UV 条纹。
- 预防：派生 Mesh 进入 Unity 前必须同时检查 Blender 实际预览、OBJ UV loop 数据和 Unity 运行截图；不要只检查顶点/包围盒或 Blender 单张预览。
- 状态：resolved

## ERR-UNITY-039

- 日期：2026-08-28
- 任务：`vfx-2df.18.3` EffectDemo 渲染入口编译恢复
- 工具：Unity 2022.3.16f1 Editor、Assets Refresh、`EffectDemoCliCommands.cs`
- 原始错误：`Assets\Editor\EffectDemoCliCommands.cs(119,9)`、`(128,43)`、`(130,43)` 均报 `CS0104: 'Object' is an ambiguous reference between 'UnityEngine.Object' and 'object'`。
- 根因：渲染入口为读取环境变量新增 `using System;` 后，原有未限定的 `Object` 同时匹配 `System.Object` 与 `UnityEngine.Object`。
- 影响：Editor 脚本无法编译，当前项目的资源刷新和后续渲染命令会被阻断。
- 修复：将三处引用显式改为 `UnityEngine.Object`，包括 `DestroyImmediate` 与 `AssetDatabase.LoadAssetAtPath<T>` 泛型参数。
- 复验：当前响应中的 Editor 完成脚本刷新；日志尾部无新的 `CS0104`、`error CS` 或 `Compilation failed`；`unity projects verify` 为 `0 errors / 0 warnings`。
- 预防：同一文件同时使用 `System` 与 `UnityEngine` 时，所有 Unity 对象类型使用显式限定或别名；新增 using 前先检索同名类型。
- 状态：resolved

## ERR-UNITY-040

- 日期：2026-08-28
- 任务：`vfx-2df.18.4` 导入特效材质贴图与 Inspector 依赖恢复
- 工具：`workspace.tools.vfx_source_ingest`、Unity 2022.3.16f1 Editor、LWGUI 1.10.0、`unity projects verify`
- 原始现象：导入材质显示贴图丢失。扫描发现 `Trains_IgnoreEffectPrefab_002` 中 69 条 `m_Texture` GUID 无法解析；覆盖重导入后又发现相同源材质被复制到多个样本根目录并保留同一 GUID，`projects verify` 报 4 个 `GUID_DUPLICATE`。此外 `ColorDefault.shader` 的 `CustomEditor "LWGUI.LWGUI"` 无法找到对应 ShaderGUI，材质 Inspector 无法创建自定义面板。
- 根因：旧 IgnoreEffectPrefab 批次没有完整共享贴图闭包；共享池把 Shader/贴图去重但 sample Material 保留源 GUID，跨样本重复；源工程的 LWGUI/YOYO ShaderGUI 是 Editor 依赖，默认脚本依赖排除后未随 Shader 进入目标工程。更深一层的最终根因是：共享贴图生成新 GUID 时把 PNG/TGA 的源 `.meta` 替换成通用 `DefaultImporter`，Unity 能按 GUID 找到文件，却不会把它加载为 `Texture2D`；因此静态 YAML/GUID 扫描会产生“贴图已恢复”的假阳性。
- 修复：用共享闭包覆盖重导入 `Trains_IgnoreEffectPrefab_002`；导入器保留材质在各样本目录，但为每份材质生成目标侧唯一 GUID，并重写 Prefab/材质引用到 Shared Shader/贴图；共享资产 rebasing 改为保留源 `.meta` 的 `TextureImporter`/`ModelImporter` 等完整配置，只替换 GUID；失效 Shared 池先移动到 `workspace/repair-quarantine` 再重建。将源工程 MIT 许可的 LWGUI 核心 Editor 代码、图标、许可证及 `YOYOShaderGUI.cs` 导入 `Assets/Editor/ThirdParty/`；对 Unity InspectorWindow UIElements 越界做一次性窗口重建，标记保存在 Library 且执行后删除。
- 复验：全量刷新后 Unity `Material.GetTexture` 审计记录 `730` 个材质、`1093` 个真实绑定纹理槽，`710` 个材质至少有一张实际加载贴图；Shared 的 `612` 个贴图均为 `TextureImporter`、`0` 个 `DefaultImporter`。全量数据集的 `1421/1421` 条材质贴图 case 绑定均有本地 tag 与 slot role；项目校验为 `0 errors / 0 warnings`。
- 预防：材质属于样本参数所有权，不能跨样本复用源 GUID；复制 Unity 资产并更换 GUID 时必须保留原 Importer 配置，禁止用通用 DefaultImporter 替换贴图/模型 `.meta`。每批导入后必须同时检查 `m_Texture` GUID 解析率、材质 GUID 重复、Shader CustomEditor、Shader include、Importer 类型和 Unity `Material.GetTexture` 实际回读；文件存在和 GUID 可解析都不能替代 Editor API 验证。
- 状态：resolved

## ERR-UNITY-041

- 日期：2026-08-28
- 任务：`vfx-2df.18.10` 真实 Play Mode 自适应特效截图
- 工具：Unity 2022.3.16f1 Play Mode、`EffectDemoRuntimeCaptureController`、`EffectDemoRuntimeCaptureBootstrap`、`workspace.tools.vfx_source_render`
- 原始现象：首批训练截图使用固定 `0.05/0.25/0.75/1.5s`，并在 `-batchmode -quit` 下调用 `ParticleSystem.Simulate` 后 `Camera.Render`；manifest 还错误记录 `play_requested=true`。短特效峰值可能被跳过，长特效采样过稀；Animator、Animation、Timeline、MonoBehaviour、协程、脚本触发、挂点和 Player Loop 均未真实运行，导致正常效果被误判为空帧。
- 根因：快速粒子预筛被误当成最终运行时证据；采样计划是 run 级固定数组，没有根据每个 Prefab 的组件时长生成。
- 修复：新增隔离副本真实 Play Mode 捕获控制器；通过 Player Loop 预跑收集动态 bounds，再重置并截图。每个 Prefab 独立读取 ParticleSystem `startDelay/duration/startLifetime/loop`、Animator/Animation clip 和 PlayableDirector duration，目标 10 个区间，间隔限制 `0.02~0.25s`，最长 8s；循环效果截一个周期。全部细帧进入 capture manifest，联系表只均匀抽取最多 6 个关键帧。离线 manifest 改为 `capture_mode=editor_particle_simulation`、`play_requested=false`，真实证据为 `capture_mode=play_mode_runtime`、`play_requested=true`。
- 复验：`Fx_acid` 实际识别为 1.0s 循环周期，生成 `0.0~1.0` 共 11 帧、间隔 0.1s，并记录 5 个粒子系统的 sampling basis。首批 16 个候选真实采集 `340/340` 有效帧、0 候选错误；duration 范围 `0.3~8.0s`，interval 范围 `0.03~0.25s`。离线空帧的 `Fx_zombie_boss_skill_1_DG` 在真实播放约 1.231s 出现画面。Unity 副本编译退出码 0；32 项测试通过；正式项目校验 0 errors/0 warnings。
- 预防：最终训练截图禁止仅靠 `ParticleSystem.Simulate`；capture manifest 必须记录 capture mode、Play Mode 状态、duration、loop、interval、全部实际时间点和 sampling basis。固定时间点只能作快速预筛，不能升级为训练真值。
- 状态：resolved

## ERR-UNITY-042

- 日期：2026-08-28
- 任务：`vfx-2df.18.12` WebGL Prefab 播放器训练标注接入
- 工程：`E:/UnityVFX/EffectDemo6.0`，Unity `6000.5.9f1`，WebGL
- 原始命令：`powershell -ExecutionPolicy Bypass -File workspace/tools/build_vfx_web_player.ps1`
- 原始错误：`VfxWebPlayer.cs(575,39)/(619,66)/(648,66): error CS0619: 'Object.GetInstanceID()' is obsolete: 'Use GetEntityId instead.'`，Unity 脚本编译退出码 `1`，外层 Unity CLI build 退出码 `6`。
- 影响：新增 WebGL 材质状态指纹代码无法编译，旧构建仍可由本地服务读取，但不包含训练标注和材质状态接入。
- 根因：Unity `6000.5.9f1` 已将 `Object.GetInstanceID()` 标记为编译期错误；材质和贴图身份哈希沿用了旧版 Unity API。
- 修复：三处身份读取改为 Unity 6 的 `GetEntityId().ToString()`；指纹只作为同一次 WebGL 播放中的兼容性变化信号，不作为 EffectDemo 2022 材质真值。
- 复验：重新执行同一构建命令，Unity C#、Player 和 IL2CPP/WebGL 全部通过，最终退出码 `0`；构建保持 `5` 个 Prefab、约 `54.4 MB`，Wasm `44,931,701` bytes。浏览器刷新后运行时成功连接，训练关联和动态评价区域可见，BladeReproduction 在约 `0.67s` 实际可见，运行指标包含 WebGL 材质变化计数；Console 无新增 Runtime error，只有既有 URP Edge Adaptive Spatial Upsampling 非致命警告。
- 预防：Unity 6.5 新增运行时代码不得沿用 `GetInstanceID()`；跨 Unity 版本的身份字段必须在目标 Editor 实际编译，静态 Python 契约测试不能替代 C# 编译。
- 状态：resolved

## ERR-UNITY-029

- 日期：2026-08-27
- 任务：`vfx-t3m` 最终截图 manifest 沉淀
- 工具：`python -m workspace.tools.unity_capture`、Python JSON 写入、Unity CLI `capture_game_view`。
- 原始命令：`python -m workspace.tools.unity_capture --root E:/UnityVFX/EffectDemo6.0/Assets/Art/VFX/BladeReproduction/Evidence/Captures_FinalCandidate_V2 --frames workspace/data/experiments/vfx-t3m/blade_reproduction_final_candidate_v2_frames.json ...`。
- 现象：首次 frames JSON 尾部写入了字面量 `\\n`，报 `json.decoder.JSONDecodeError: Extra data: line 50 column 2 (char 882)`；修正 JSON 后，manifest 仍错误显示 `valid_frame_count=0` 和 `missing capture file`，虽然 Unity 截图已真实存在。
- 根因：`write_manifest` 将 `output.parent` 当作帧验证根目录，忽略 CLI 的 `--root`，相对帧名被解析到 `workspace/data/experiments/vfx-t3m/` 而不是 Unity capture 目录。
- 影响：记录层会错误否定有效截图；如果未复验，可能把截图链路误判为失败。
- 修复：`workspace/tools/unity_capture.py` 的 `write_manifest` 增加可选 `root`，CLI 显式传递 `args.root`；新增跨目录 capture root 单测。用 V5 重新生成 manifest。
- 复验：`workspace.tests.test_unity_capture` 与 `workspace.tests.test_blade_shader_contract` 共 `8/8 OK`；`blade_reproduction_final_candidate_v5_manifest.json` 报告 `12` 有效帧、`0` 无效帧；截图仍通过 Codex 原生图片通道实际复核。
- 预防：manifest 输出目录和截图目录不同时，必须显式传入 capture root；记录工具失败不能推翻已实际看到的 Unity 画面，必须定位到证据路径解析层。
- 状态：resolved

## ERR-UNITY-030

- 日期：2026-08-27
- 任务：`vfx-ryl` EffectDemo 2022 Unity CLI 接入
- 工具：PowerShell 包装脚本、Unity 2022.3.16f1 batchmode
- 原始命令：`powershell -ExecutionPolicy Bypass -File .\workspace\tools\effectdemo_cli.ps1 -Action create`
- 现象：首次包装脚本返回退出码 `127`，没有生成 log；直接使用等价 Unity 参数运行则成功。
- 根因：PowerShell 数组中的 `-logFile` 路径由连接表达式拆成了三个参数，Unity 将后续 token 当作无效启动参数。
- 修复：预先用 `Join-Path` 计算 `$resolvedLog`，再将完整路径作为单个参数传给 `Start-Process -Wait -PassThru`。
- 复验：同一包装命令退出码 `0`；日志包含 `EffectDemo CLI smoke effect created` 与 `Exiting batchmode successfully now!`；`unity projects verify` 为 0 errors、0 warnings。
- 预防：PowerShell 启动外部程序时先打印/检查最终参数数组；路径拼接不要直接放在数组元素表达式中。
- 补充环境日志：Unity 同次启动还输出 `LicensingClient has failed validation`、`Access token is unavailable`；该授权客户端问题未阻止本次 batchmode 命令，未改动许可证或绕过认证。后续需在需要长时间 Editor/Pipeline 会话前按本机 Unity Hub 账号/许可证流程处理。
- 状态：resolved

## ERR-UNITY-031

- 日期：2026-08-27
- 任务：`vfx-n8l` EffectDemo 2022 Pipeline 适配
- 工具：Unity 2022.3.16f1、Unity CLI `unity run` / `unity command`、UPM 本地嵌入包解析
- 原始命令：`unity run "E:/Unity特效人工智能学习/UnityDemo/EffectDemo" --editor-path "C:/Program Files/Unity/Hub/Editor/2022.3.16f1/Editor/Unity.exe" --timeout 180 -- -executeMethod EffectDemoCliCommands.CreateCliSmokeEffect`
- 现象：在 `Packages/` 添加任意 `file:` 本地包后，Unity 2022 UPM 请求 `resolve-packages` 返回 500：`The "path" argument must be of type string. Received undefined.`；相同机器上的 `workspace/unity-verification` 本地包也复现，说明不是 Pipeline 源码单独导致。CLI 同时报告 LicensingClient 签名验证和 access token 更新日志，Editor 以代码 1 退出。
- 影响：Package Manager 不能完成本地包首次解析，因此本轮无法让 2022 Editor 编译 Pipeline 程序集、启动 Pipeline Server 或发现 `unity command`。
- 已完成修复：嵌入 `Packages/com.unity.pipeline` 0.5.0-exp.1 源码快照，保留来源记录；将包最低 Unity 版本改为 2022.3；移除 Runtime asmdef 对可选 Input System 的硬引用；为 `PhysicsMaterial`/`PhysicMaterial` 和 `Material.rawRenderQueue` 添加跨版本条件处理；添加 `create_cli_smoke_effect` / `remove_cli_smoke_effect` 注册命令。
- 复验：`-noUpm` batchmode 可完成现有工程脚本编译并以代码 0 退出，但 UPM 不加载嵌入包，不能作为 Pipeline 通过证据；正常 UPM 启动和 `unity run` 均稳定复现上述阻塞。
- 2026-08-28 补充：在完全独立的 `EffectDemoTrainingR001` 渲染副本中移除 `com.unity.pipeline`、`com.xuanxuan.nb.fx` 两个 `file:` 依赖并移走 `packages-lock.json` 后，UPM 仍以空参数 `params: {}` 调用 `project:resolve-packages` 并返回同一 500，证明该机故障不只由本地包触发。首批源特效渲染命令本身不依赖 UPM/Pipeline，改用显式 `-noUpm` 后成功导入资产并输出 16 个候选、64 张有效帧；此证据仅证明离线 Camera.Render 链路，不用于宣称 Pipeline 可用。
- 后续：先修复本机 Unity 2022 UPM 对 `file:` 包的 500 错误，再用正常 UPM 启动检查 `Unity.Pipeline*.dll`、`unity command --query cli_smoke` 和 `unity run --command create_cli_smoke_effect`。不得用 `-noUpm` 将 Pipeline 标记为可用。
- 状态：resolved

## ERR-UNITY-032

- 日期：2026-08-27
- 任务：`vfx-n8l` EffectDemo 2022 Pipeline CodeAnalysis 引用
- 工具：Unity 2022.3.16f1 Editor 编译、Pipeline 包导入日志
- 原始错误：`RoslynCompilationService.cs`、`AccessibilityValidator.cs`、`InPlaceReloadProcessor.cs`、`OverrideFileValidator.cs`、`SourceCodeTransformer.cs` 大量 `CS0234/CS0246`，包括 `Microsoft.CodeAnalysis.CSharp`、`SemanticModel`、`SyntaxNode` 找不到。
- 根因：Pipeline 快照中的 5 个 CodeAnalysis DLL `.meta` 使用 Unity 6 `PluginImporter.serializedVersion: 3`；Unity 2022 虽然导入 DLL 文件，但没有将其加入 `Unity.Pipeline` 程序集的预编译引用列表。Editor 在转换前已打开，旧编译缓存仍在内存中。
- 修复：将 `Microsoft.CodeAnalysis.dll`、`Microsoft.CodeAnalysis.CSharp.dll`、`System.Collections.Immutable.dll`、`System.Reflection.Metadata.dll`、`System.Runtime.CompilerServices.Unsafe.dll` 的 `.meta` 转换为 Unity 2022 兼容的 `serializedVersion: 2` 格式；UPM 已成功解析并在 `packages-lock.json` 记录 `com.unity.pipeline` embedded 条目。
- 当前复验：打开中的 Editor 仍显示转换前错误；`Library/ScriptAssemblies/Unity.Pipeline.dll` 尚未生成。必须关闭并重新打开该 2022 项目，让 Unity 重新导入 DLL 和编译程序集后再判断结果。
- 预防：修改插件 `.meta` 后不得只等待旧 Editor；必须重启或触发完整 AssetDatabase reimport，再检查 Pipeline 程序集、Console 和 `unity command`。
- 补充复验：关闭并重新打开 Unity 2022.3.16f1 后，CodeAnalysis DLL 已进入引用；`Unity.Pipeline.dll` 成功生成，Pipeline Server 在 `127.0.0.1:7801` ready，`create_cli_smoke_effect` 执行成功，Console 无 Error。
- 状态：resolved

## ERR-UNITY-033

- 日期：2026-08-27
- 任务：`vfx-2df.16` Unity 特效源文件摄入解析器原型
- 工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`
- 工具：Unity CLI `projects verify`；Python `workspace.tools.vfx_source_ingest`
- 原始命令：`unity projects verify E:/Unity特效人工智能学习/UnityDemo/EffectDemo --format json`
- 现象：首次把 `E:/Trains/Unity/Assets/ArtResources/IgnoreEffectPrefab` 复制到 `Assets/VFXSourceIngest/Trains/Trains_IgnoreEffectPrefab_001` 后，Unity CLI 报 2 个 `META_MISSING`：`Assets/VFXSourceIngest` 和 `Assets/VFXSourceIngest/Trains` 父目录缺少 `.meta`。
- 根因：摄入工具只复制了源目录文件和已有 `.meta`，但没有为新建的 Unity 父级导入目录生成 folder meta。
- 影响：项目结构校验失败；即使 Prefab 文件存在，也不能把导入包作为 Unity 可验证样本。
- 修复：`workspace/tools/vfx_source_ingest.py` 增加 folder `.meta` 生成；随后进一步增加 `--copy-dependency-closure`，按 GUID 递归复制 Prefab 依赖的 Material、Texture、Mesh、Shader、Shader Graph、VFX Graph 和动画资源，并保留各资产 `.meta`。脚本依赖默认只记录为 `ignored`，避免把游戏项目代码链带入训练工程造成编译风险。
- 复验：重新摄入首批 Trains Prefab 后，`source_sample.json` 记录 `files=219`、`material=99`、`texture=84`、`mesh=2`、`shader=2`、`external_dependencies=0`、`missing_dependencies=0`、`ignored_dependencies=3`、`builtin_dependencies=4`；四个 JSON 输出均通过 schema 校验；`unity projects verify E:/Unity特效人工智能学习/UnityDemo/EffectDemo --format json` 返回 `success=true`，`errors=0`、`warnings=0`、`filesScanned=584`。
- 预防：任何工具只要在 Unity `Assets/` 下新建目录，都必须同步创建 folder `.meta`；任何从外部 Unity 工程搬运 Prefab 的任务，默认使用依赖闭包模式，至少补齐材质、贴图、模型和 shader，再做渲染和训练标注。
- 状态：resolved

## ERR-UNITY-034

- 日期：2026-08-27
- 任务：`vfx-2df.16` / `Trains IgnoreEffectPrefab` 材质错误定位
- 工程：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`
- 工具：Python `workspace.tools.vfx_source_ingest`、PowerShell 文本核对
- 现象：用户确认“prefab 不是没有，而是材质还是不正确”。核对后发现，`Mat_jiatelin_01.mat` 里的 `m_Shader` GUID 为 `606eaaa6316a4f89834cf35717f11834`，而早期导入批次 `_001/_002` 里的 `ColorDefault.shader.meta` GUID 发生错位，且 `ColorDefault.shader` / `FrameAnimation.shader` 都依赖 `../ShaderLibraries/PixelPeerlessCommon.hlsl`，当时导入包未包含该本地 include 库。
- 根因：复制 shader 资源时未保留 Unity 正确的 `.shader.meta` 命名和原始 GUID；同时依赖闭包只跟 GUID，不跟本地 `#include` 路径，导致 shader 公共库未被搬运。
- 影响：材质虽然存在，但它们指向的 shader 不是源工程里同一个 shader，Unity 里会表现为材质不正确或渲染异常，不能作为可信训练样本。
- 修复：修正导入器的 shader `.meta` 复制逻辑，改用 `Path(str(file) + ".meta")` 保留原始 shader GUID；新增本地 `#include` 解析，递归复制 `ShaderLibraries/PixelPeerlessCommon.hlsl` 等 include 文件，并保留其 `.meta`。重新生成 `_003` 批次后，`ColorDefault.shader.meta` GUID 已恢复为 `606eaaa6316a4f89834cf35717f11834`，`PixelPeerlessCommon.hlsl` 也已进入导入包。
- 复验：`workspace.tests.test_vfx_source_ingest` 4/4 通过；`source_sample.json` 记录 `files=220`、`shader=2`、`shader_include=1`、`external=0`、`missing=0`；`Mat_jiatelin_01.mat` 的 shader GUID 与导入包内 `ColorDefault.shader.meta` 一致；`unity projects verify E:/Unity特效人工智能学习/UnityDemo/EffectDemo --format json` 仍为 `errors=0`、`warnings=0`。
- 预防：凡是 Unity shader 资产，必须同时检查三件事：shader 主文件、对应 `.meta` GUID、本地 `#include` 链；不要把“文件存在”误当成“shader 语义已正确”。后续材质验证必须看 shader GUID 是否与源工程对齐。
- 状态：resolved

## ERR-UNITY-035

- 日期：2026-08-27
- 任务：`vfx-t3m` TutorialTextureTrial 候选链路与 1:1 复刻边界
- 工具：FFmpeg/教程抽帧、PowerShell、Python `eval`、Blender 5.0 headless、Unity CLI Pipeline、C# Editor 配置命令、Codex 原生图片读取。
- 现象与原始错误：教程 `70:00–80:00` 首次按 `70–80s` 取证而不是按 `4200–4800s` 取证；辅助 `eval` 命令出现嵌套引号解析错误；C# 配置阶段出现 `CS1612`、`CS1061`；自动创建 ParticleSystem 的尝试失败；环 Mesh 首版轴向错误；截图命令重复传入 `--height`；对 inactive 对象使用 `GameObject.Find` 返回空引用；TutorialTextureTrial 最终截图只显示白/青矩形和粉色矩形，没有 Core 或 Outer 刀光轮廓。
- 根因：时间单位和脚本参数边界未先核对；局部文本修改与 Unity API/结构体写入方式不匹配；CLI 对运行时组件创建覆盖不足；Mesh 导出平面轴与 Unity 相机不一致；批量参数重复拼接；inactive 层级对象不适合用普通 `GameObject.Find`；更根本的原因是用截图派生贴图、自建 Mesh 和自有 Shader 替代了缺失的原始 Shader/材质/贴图/模型。
- 影响：中间的编译、几何和截图链路曾多次阻断；即使后续 `projects verify`、Console 和 manifest 正常，候选仍未形成可辨认刀光，不能作为教程 1:1 复刻证据。
- 修复：将教程时间统一换算为绝对秒并重新抽帧；修正 `eval` 引号和 C# 方法边界/API 调用；改用 C# Editor 命令配置已存在的 ParticleSystem；修正 Mesh 可见轴和 UV loop 映射；删除重复 `--height`；使用显式层级句柄处理 inactive 对象；保留失败截图并停止继续用近似资产补差距。
- 复验：教程 `4200–4800s` 证据已重新生成；BladeReproduction 主工程 `E:/UnityVFX/EffectDemo6.0` 编译失败标志为 `false`、Console error 为 `0`、项目校验为 `0 errors/0 warnings`，但 Codex 实际读取 `Captures_TutorialTextureTrial/frame_0600_clean.png` 后确认视觉失败；该候选被否决，任务继续保持 `in_progress`。
- 预防：抽帧前用 `ffprobe` 和绝对时间标签校验单位；批量 CLI 执行前查询 schema 并检查重复参数；编辑 C# 方法时读取完整边界并先跑契约测试；进入 Unity 前验证 Mesh 轴、UV loop 和 inactive 引用；任何“复刻”必须同时具备原始 Shader/include、材质、贴图、Mesh、时序和多帧实际视觉对照，不能用文件存在或 CLI 成功替代。
- 状态：mitigated

## ERR-UNITY-036

- 日期：2026-08-28
- 任务：`vfx-2df.18` EffectDemo 导入 Prefab 批量渲染入口
- 工具：PowerShell `workspace/tools/effectdemo_render_source.ps1`
- 原始命令：`powershell -ExecutionPolicy Bypass -File .\workspace\tools\effectdemo_render_source.ps1 -Requests .\workspace\data\vfx_generation\runs\trn_ignore_effect_prefabs_003_r001\render_requests.json -LogFile .\workspace\progress\effectdemo-source-render-trn-003-r001.log`
- 现象：脚本在 Unity 启动前报 `Join-Path : Cannot bind argument to parameter 'Path' because it is an empty string.`，位置为参数块中的 `$PSScriptRoot` 默认工程路径。
- 根因：PowerShell 在参数默认值求值阶段没有提供 `$PSScriptRoot`，导致默认路径表达式依赖空字符串。
- 影响：未启动 Unity、未写入任何截图，也没有修改 Prefab、材质或贴图；渲染链路被脚本初始化阻断。
- 修复：把 `$ProjectPath` 与 `$LogFile` 的默认路径计算移到参数绑定后的脚本体，改用 `$MyInvocation.MyCommand.Path` 派生脚本目录。
- 复验：待重新启动同一渲染请求，并检查 Unity 日志、capture manifest 和截图文件。
- 预防：PowerShell 脚本不要在 `param()` 默认值中依赖 `$PSScriptRoot`；涉及脚本相对路径时，在参数绑定完成后再解析 `$MyInvocation`。
- 状态：mitigated

## ERR-UNITY-037

- 日期：2026-08-28
- 任务：`vfx-2df.18` EffectDemo 导入 Prefab 批量渲染入口
- 工具：Unity 2022.3.16f1 batchmode、`workspace/tools/effectdemo_render_source.ps1`
- 原始命令：`powershell -ExecutionPolicy Bypass -File .\workspace\tools\effectdemo_render_source.ps1 -Requests .\workspace\data\vfx_generation\runs\trn_ignore_effect_prefabs_003_r001\render_requests.json -LogFile .\workspace\progress\effectdemo-source-render-trn-003-r001.log`
- 现象：Unity 以 `1073741845` 退出，日志明确显示 `It looks like another Unity instance is running with this project open.`；进程 `20280` 正在打开 `UnityDemo/EffectDemo`。`unity status` 与 `unity pipeline list` 均未发现可连接的 Pipeline Server。
- 根因：当前用户 Editor 占有同一项目的 UnityLockfile，且没有可用的实时 Pipeline 命令通道；Unity 不允许 batchmode 同时打开该项目。
- 影响：新的渲染命令尚未编译/执行，没有产生 capture manifest 或截图；不得将此退出码归因为 Shader、材质或 Prefab 渲染错误。
- 修复：不关闭用户 Editor。创建隔离的临时项目副本，仅用于编译和 `Camera.Render` 截图；渲染请求和产物继续指向原训练 run。
- 复验：待在隔离副本中启动 Unity，检查脚本编译、capture manifest、PNG 和联系表。
- 预防：启动 batchmode 前检查 UnityLockfile、运行中 Unity 进程和 `unity status`；如果用户项目已打开但实时命令不可用，使用隔离副本或等待用户主动关闭，禁止强制结束 Editor。
- 状态：mitigated

## ERR-UNITY-038

- 日期：2026-08-28
- 任务：`vfx-2df.19` EffectDemo 共享依赖池特效导入
- 工具：`workspace.tools.vfx_source_ingest`、Unity 2022.3.16f1 Asset Pipeline、`unity projects verify`
- 原始现象：首批 `Trains_acid_001`、`Trains_ice_spike_001`、`Trains_shield_001`、`Trains_thunder_ball_001`、`Trains_scene_explosion_001`、`Trains_scene_smoke_001`、`Trains_whirwind_001` 的工作区 manifest 报告复制成功，但实际 `Assets/VFXSourceIngest/Trains/*` 与 `Assets/VFXSourceIngest/Shared` 仅保留空目录或 folder `.meta`；同时 Unity 导入过 `Assets/VFXSourceIngest/Shared/dependency_index.json` 和各样本 `shared_dependency_report.json`，这些诊断 JSON 没有对应 `.meta`。Editor 还记录 `Shader error in 'Common/ColorDefault': Couldn't open include file '../ShaderLibraries/PixelPeerlessCommon.hlsl'.`
- 根因：共享索引和样本诊断报告被写入 Unity `Assets/`，但它们是工具元数据而非 Unity 资产；复制源工程的 folder `.meta` 会跨样本复用 GUID；早期共享 Shader 采用扁平路径，破坏了相对 `#include` 链。导入器还缺少“报告成功前，目标文件和 `.meta` 必须真实存在”的物理完整性门禁。
- 修复：共享索引默认移至 `Library/VFXSourceIngest/shared_dependency_index.json`，样本报告移至对应 `workspace/data/vfx_generation/sources/<sample>/shared_dependency_report.json`；目标 folder `.meta` 改为生成本地唯一 GUID；拒绝样本目录与 Shared 目录重叠；新增共享索引重建和复制后文件/`.meta` 完整性校验。Shader 与 HLSL 继续按 `Shared/ShaderPackages/Bundles/Shaders/...` 保留原相对目录。随后重新导入七个代表 Prefab。
- 复验：18 项摄入、渲染准备、run pipeline、反馈测试通过；七个目标样本实际含 `3-9` 个资产和各自 `.meta`，Shared 含 `32` 个资产，索引仅位于 `Library`；`unity projects verify E:/Unity特效人工智能学习/UnityDemo/EffectDemo --format json` 返回 `0 errors / 0 warnings`；材质 YAML 已指向当前 `ColorDefault.shader` GUID，`PixelPeerlessCommon.hlsl` 物理存在于相对 include 路径。对当前响应中的 Editor 执行 Assets Refresh 后，日志记录 `50.642s` 的成功资源刷新，刷新后日志尾部没有新的 `ColorDefault` include 错误、`ArgumentOutOfRangeException`、`NullReferenceException` 或 C# 编译错误。
- 已知限制：当前打开的 EffectDemo Editor 未暴露 Pipeline 命令，隔离副本的正常 UPM batchmode 仍受既有 `ERR-UNITY-031` 本机 `file:` 包解析错误阻断；该环境限制不影响已打开 Editor 中完成的资源刷新和项目结构校验。
- 预防：后续 200 个源特效必须先用 shared-pool dry-run，再小批导入并检查物理完整性、`projects verify`、Shared index 位置和 Shader include 链；不得把 manifest 成功或 JSON 存在当作导入成功。
- 状态：resolved
## ERR-VFXDATA-004

- 日期：2026-08-31
- 任务：`vfx-2df.18.17` Prompt 条件 Prefab 与 MaterialTrajectory 组合执行。
- 工程：权威工程 `UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始命令：`powershell -ExecutionPolicy Bypass -File workspace/tools/effectdemo_execute_material_trajectories.ps1 -Requests workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_composed_r002_human/execution_requests.json -ProjectPath workspace/unity-render-staging/EffectDemoPromptHumanR001 -NoUpm -LogFile workspace/progress/effectdemo-prompt-composition-r002-human.log`。
- 原始错误：6 个请求均写入 `Prefab has no Renderer or Graphic using source material`，例如 `Fx_scan_sub.prefab -> Mat_jinzita_02.mat`；Unity 进程正常退出，但没有任何候选形成有效的组合视觉证据。
- 根因：`prompt_candidate_retrieval` 先按 Prompt 对 Prefab 排序，再独立轮换正向 MaterialTrajectory；它没有确认轨迹的源材质是该 Prefab 直接 Renderer/Graphic 依赖。执行器正确拒绝了跨 Prefab 的无效材质绑定。
- 影响：`prompt_cartoon_blue_energy_impact_composed_r002_human` 是技术失败证据，不能进入质量、风格、偏好、图像或生成训练，也不能建立人工审美评价。
- 修复：检索器改为只从 `Prefab direct material paths ∩ positive train trajectory material paths` 生成组合；候选清单写入 `material_paths` 与 `binding_status=direct_prefab_renderer_material`，不足指定数量时明确失败而不回退到不兼容配对。
- 补充：第一次修复后的 `r003` Unity 已 6/6 执行通过，但 Python `material_trajectory_executor finalize` 报 `KeyError: 'curriculum_root'`；第二次 `r004` 补字段后，最终 schema 报 `execution_mode: 'prompt_composition' is not one of ['smoke', 'full', 'selected']`。根因是组合准备器没有完整复用执行器的请求溯源契约，并自造了不被 manifest schema 接受的执行模式。
- 补充修复：组合请求现在写入 `created_at`、`curriculum_root`、权威 `unity_project`、实际隔离 `execution_project` 和 `selection`；底层执行模式使用既有 `selected`，组合语义明确写入 `selection.kind=prompt_composition`，由关联的 Prompt composition manifest 表达。
- 复验：`r005` 的 Unity 2022 隔离执行 6/6 通过，`material_trajectory_executor finalize` 和 `prompt_composition_finalize` 均成功；最终为 6/6 technical pass、6/6 visible、资源审计干净。`workspace.tests.test_prompt_candidate_retrieval`、`test_prompt_composition_prepare` 与 `test_prefab_human_review` 共 13/13 通过。
- 预防：Prompt 组合必须把 Prefab、Renderer/Graphic、Material、Shader/Texture 和轨迹视为一条可审计依赖链；不得把两个各自真实的样本直接拼成未绑定的执行请求。`无法判断`、无画面和执行失败均只作技术排除，不作审美负标签。
- 状态：resolved。

## ERR-VFXDATA-005

- 日期：2026-08-31
- 任务：`vfx-2df.18.17` 组合候选人工评价批次。
- 原始现象：首次从 `r005` 组合运行建立评价批次时，OpenCV 报帧文件无法读取；随后又报 `KeyError: 'time_seconds'`。
- 根因：OpenCV `imread` 在本机含中文工作区路径下不能稳定读取 PNG；组合执行结果的帧时间字段实际为 `requested_time_seconds`，不是旧 Prefab review 的 `time_seconds`。
- 修复：评价工具改用 `numpy.fromfile + cv2.imdecode` 读取图像；组合批次按执行结果真实字段读取时间。新批次同时保留“组合候选（本次运行结果）”与“来源标签仅用于检索，不代表本次组合结论”的区分。
- 复验：组合评价批次 6 条、每条 11 帧、6 份 AI 草稿均已生成；浏览器实际加载确认标题、来源提示、单一备注框、6 条候选与帧序列均可见。
- 预防：跨平台/中文路径的图像工具不能假定 `cv2.imread` 可用；从不同运行 manifest 转入统一评价 UI 前必须按实际字段名读时间和路径。
- 状态：resolved。

## ERR-VFXDATA-006

- 日期：2026-08-31
- 任务：`vfx-2df.18.20` 受约束 Prompt 变异执行与粒子加材质组合轨迹。
- 工程：权威工程 `UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始现象：第一条 `magic_orb 4` 单材质蓝色轨迹与第二条 `Mat_daodan_01` 核心材质轨迹均技术通过，但蓝色像素峰值为 `0.0`；第三条单层粒子颜色轨迹通过且写入 `particle_color_changed`，画面仍近似橙色。随后批量材质属性变异 `r005` 在失败处理器内再次抛 `NullReferenceException`，结果文件缺失；重试 `r006` 写出结构化 error，真实原因是 `Track clamp count mismatch: 1 != 3`。
- 根因：`ColorDefault` 的主颜色会与 ParticleSystem 顶点色和贴图色相乘，单材质或单粒子层不能覆盖爆发主体；大尺寸的 Glow、火焰和冲击层使用多个直接绑定材质。新增规格将普通参数轨迹由 3 条缩为 1 条后，请求生成器仍硬编码 3 个 `track_clamps`。此外 `WriteFailure` 访问 Unity 已销毁 Material 的 `.shader`，遮蔽了原始错误。
- 修复：执行器增加可选 `particle_color_tracks`（按直接材质定位 ParticleSystem，设置 `Main.startColor` 并可关闭 `colorOverLifetime`）和 `material_property_tracks`（按材质路径克隆运行时材质并批量设置属性）；新增 `particle_color_changed` 与 `multi_material_property_changed` 信号和实际命中粒子数。变异请求的 clamps 从真实 `parameter_tracks` 派生；错误处理器安全读取被销毁 Unity 对象。所有源 Prefab、源材质、纹理和 Shader 均未写回。
- 复验：`r007` 以一个爆发 Prefab 同时命中 `5` 个 ParticleSystem、克隆并销毁 `4` 个运行时材质，预期/实际信号一致，`11/11` 有效帧、无资源泄漏，蓝色可见比例峰值从 `0.0` 提升至约 `0.239`。人工视觉确认起势/峰值存在蓝色火花，但后段仍有橙色残留，因此状态为 `technical_pass_pending_human_prompt_review`，未进入任何训练集。
- 预防：对“改色”目标必须同时审计 Renderer -> Material -> ParticleSystem 顶点色、Color over Lifetime、材质 HDR 乘色和贴图层；仅凭属性变更信号不能宣称色相达标。动态 request 中任何依赖数组必须由对应 spec 动态派生，禁止硬编码数量；失败写入也必须回避 Unity fake-null 对象访问。
- 状态：resolved。

## ERR-VFXDATA-007

- 日期：2026-09-01
- 任务：`vfx-2df.18.20` 蓝色爆发全层变异与 Prompt 条件评价。
- 原始现象：`r008` 全层变异在 Unity 目标解析阶段拒绝 `Mat_aidawang_02.mat`，提示 Prefab 没有使用该粒子颜色目标材质。
- 根因：变异器把真实材质路径 `Assets/VFXSourceIngest/Trains/Trains_FX_All_001/ArtResources/FX/juese/FX_A_aidawang/mat/Mat_aidawang_02.mat` 错写成了 `.../Effect/juese/...`；不能用相似目录名猜测或放宽绑定检查。
- 修复：改正路径，保留“Renderer/ParticleSystem 必须真实命中”的硬门禁；同时将爆发 Prefab 的 10 个直接材质层和 10 个粒子颜色层纳入一次性变异。
- 复验：`r009` 在隔离 Unity `2022.3.16f1c1` 中编译与执行通过，11/11 帧有效；命中5个实际粒子系统，4个运行时材质克隆清理完成，材质/贴图/RenderTexture均无泄漏；预期与实际轨迹信号一致；蓝色可见比例峰值 `1.0`、平均 `0.7196`。联系表确认前半段蓝色主体成立，后段快速消散。
- 训练边界：`r009` 仅为技术通过的 Prompt 变异候选，人工条件评价前 `prompt_condition_supervision=false`、`positive_generation_supervision=false`、`preference_training=false`；8794 页面中的“风格无法判断”不进入风格训练，整体“部分符合”不进入正向生成。
- 预防：跨工程 Unity 路径必须从当前 Prefab 审计的直接依赖读取；材质变异必须覆盖 Renderer 材质、ParticleSystem `Main.startColor`、`colorOverLifetime` 与材质 HDR 主色；像素指标只能证明候选信号，不能替代人工 Prompt 条件结论。
- 状态：resolved。

## ERR-VFXDATA-008

- 日期：2026-09-01
- 任务：`vfx-2df.27` 课程资料到 VFX Controller 训练样本适配
- 工程：`E:/Unity特效人工智能学习`；课程适配目标为 `workspace/data/vfx_generation`
- 原始命令：`python -m workspace.tools.vfx_generation.course_knowledge_adapter index --input knowledge/sources --input knowledge/cards --input knowledge/experiments --output-dir workspace/data/vfx_generation/course_knowledge/course_knowledge_r002 --index-id course_knowledge_r002`，随后导出课程 Controller 适配结果。
- 原始现象：`EXP-2026-105_刀光教程参数假设试验表.md` 的“覆盖审计结论”记录包含“不是已验证的刀光制作模板”和“尚未完成复现”，但旧状态识别逻辑只看到“已验证”词，错误标记为 `verified`，生成了不应存在的刀光课程先验。
- 根因：中文否定句中的 `已验证` 被正向关键词 `已验证` 无条件匹配；状态识别没有先处理“不是/并非/尚未/不等于已验证”语义。
- 影响：课程适配 r002 多生成一条 `slash` VFXSpec 先验。它仍因课程先验门禁没有进入 SFT，但会污染课程先验数量、族统计和后续复现候选，不能作为可信数据继续使用。
- 修复：在正向状态判断前新增中文否定验证模式，覆盖“不是已验证”“尚未完成复现”“不能称为 verified”等表达；重建 `course_knowledge_r003`、`course_controller_adapter_r003` 和 `course_controller_r003`。
- 复验：r003 课程索引 `input=1022`、`records=2651`、`verified=8`；适配器只保留 `EXP-2026-004` 烟花工程映射 `1` 条先验，刀光记录进入 `course_training_exclusions.jsonl`；Controller 数据集含课程先验 `1` 条和当前变异候选 `1` 条，`sft=0`；训练预检为 `blocked_insufficient_labels`，`labeled_family_count=0`，`weight_written=false`。相关定向测试 `11/11`、全量测试 `243/243` 通过。
- 预防：课程状态识别必须先执行否定语义过滤，再执行正向 verified 匹配；每次重建课程索引后都要比较先验数量、排除清单、特效族分布，并运行 Controller Schema 和训练预检；课程先验永远不直接进入正向 SFT。
- 状态：resolved
## ERR-UNITY-055

- 日期：2026-09-01
- 任务：`vfx-2df.34.2` PrefabGraph 到全新 Unity Prefab 编译器 smoke。
- 工程：权威工程 `UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始命令：`powershell -ExecutionPolicy Bypass -File workspace/tools/effectdemo_compile_prefab_graph.ps1 -Graph workspace/data/vfx_generation/generated/prefab_graph_smoke_r001/graph.json -OutputPrefab Assets/VFXGenerated/PrefabGraph/SmokeR001/GeneratedBlueImpact.prefab -Result workspace/data/vfx_generation/generated/prefab_graph_smoke_r001/compile_result.json -ProjectPath workspace/unity-render-staging/EffectDemoPromptHumanR001 -NoUpm -LogFile workspace/progress/effectdemo-prefab-graph-smoke-r001.log`。
- 原始错误：Unity 在 `EffectDemoPrefabGraphCompiler.ConfigureParticleSystem` 设置 `main.loop` 时抛出 `NullReferenceException: Do not create your own module instances, get them from a ParticleSystem instance`，进程退出码为 `1`；结果文件为 `status=error`、`source_prefab_read=false`，目标 Prefab 未写入。
- 根因：R001 在节点构建完成后才通过 `GetComponent<ParticleSystem>() ?? AddComponent<ParticleSystem>()` 动态附加粒子组件；此隔离 Unity 批处理路径下模块句柄没有在首次 `main` 配置前稳定绑定。
- 修复：R002 改为在创建带 `UnityEngine.ParticleSystem` 的节点时使用 `new GameObject(name, typeof(ParticleSystem))` 直接构造原生组件，配置阶段只获取已存在的 `ParticleSystem` 与其自动创建的 `ParticleSystemRenderer`；节点激活延后至所有模块配置完成后。
- 复验：待执行同一无 parent PrefabGraph 的 R002，并检查 Unity 退出码、结构化结果、Prefab、三个生成材质和运行截图。
- 预防：ParticleSystem 模块只能从已绑定原生组件获取；生成器不得在首次模块写入前隐式补组件，也不得把 Unity 命令失败归因为 Graph 或模型训练失败。
- 状态：mitigated。

## ERR-UNITY-056

- 日期：2026-09-02
- 任务：`vfx-2df.34.10` 源 PrefabGraph 重编译 R003。
- 工程：权威工程 `UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始命令：`powershell -ExecutionPolicy Bypass -File workspace/tools/effectdemo_compile_prefab_graph.ps1 -Graph workspace/data/vfx_generation/generated/prefab_graph_source_export_r003/graphs/trains_fx_129_fx_nuge_zidan_01.json -OutputPrefab Assets/VFXGenerated/PrefabGraph/SourceReconstructionR003/trains_fx_129_fx_nuge_zidan_01/Fx_nuge_zidan_01.prefab -Result workspace/data/vfx_generation/generated/prefab_graph_source_export_r003/recompile_results/trains_fx_129_fx_nuge_zidan_01.json -ProjectPath workspace/unity-render-staging/EffectDemoPromptHumanR001 -NoUpm -LogFile workspace/progress/effectdemo-prefab-graph-source-recompile-r003-trains_fx_129_fx_nuge_zidan_01.log`。
- 原始错误：`FileNotFoundException: Particle material could not be loaded: Resources/unity_builtin_extra`；Unity 退出码 `1`，其余 9 个源 Graph 已编译通过。
- 根因：Unity 内置材质在源 Prefab API 导出时由 `AssetDatabase.GetAssetPath` 表示为 `Resources/unity_builtin_extra`，它不是当前项目中可以用 `AssetDatabase.LoadAssetAtPath<Material>` 重新加载的普通 `.mat` 资产。
- 修复：保留内置路径在源 Graph 的 asset binding provenance 中；编译器新增 `IsBuiltinAssetPath`，只将项目内 `.mat` 交给 `AssetDatabase`，内置路径没有可加载项目材质时走生成材质模板分支，不静默猜测具体来源材质。
- 复验：待单独重跑该候选，检查编译结果、实际 Shader/材质、Unity 项目验证和后续 API 回读。
- 预防：源 AssetDatabase 路径必须区分项目资产、内置资源和运行时对象；内置资源不可当作项目路径传给 `LoadAssetAtPath`，也不能被相似文件名替换。
- 状态：mitigated。

### R006 后续验证

- 现象：R006 生成的材质已实际绑定 `VFXGenerated/SoftParticle` Shader GUID 和三份程序化 Texture2D，编译、Prefab 保存和 9 帧抓取均成功，但九帧 PNG 都是背景，所有文件大小均为 `5627` bytes。
- 根因：首版自定义 pass 同时限制 `RenderPipeline=UniversalPipeline` 且使用 `SRPDefaultUnlit`，在当前 `-noUpm` 隔离渲染路径中虽可导入却没有进入有效绘制；它还依赖 ParticleSystem 顶点色，不能作为首个可见性 smoke 的必要条件。
- 修复：R007 移除 pipeline 限制，使用 `UniversalForward` pass，并先只用可验证的材质 `_Color` 乘 `_MainTex` alpha；顶点色支持另列为后续 Shader 能力，不把它和可见性验证耦合。
- 复验：待检查 R007 的九帧有效性、非背景面积和峰值图像。

### R007 后续验证

- 现象：移除 pipeline tag 并换为 `UniversalForward` 后，R007 的 9 帧仍全部为背景，`visible_ratio.max=0`、`temporal_delta.mean=0`；编译日志没有 Shader 或 C# 错误。
- 根因：当前 `-noUpm` 隔离路径能导入并引用新 Shader 资产，但不足以证明新建 Shader pass 在此渲染路径可用；继续只改 pass 标签没有新的可归因信息。
- 修复：默认生成路径不再自动选择自定义 Shader，改为克隆 Unity 新建 `ParticleSystemRenderer` 的默认已配置粒子材质，再替换颜色和程序化贴图。`generated_soft` 仍是显式实验 profile，留待正常 UPM/编辑器路径单独验证。
- 复验：待运行 R008，检查 clone 后材质的 Shader 名称、透明状态和连续帧指标。

## ERR-UNITY-057

- 日期：2026-09-02
- 任务：`vfx-2df.36` Prefab Play Mode 捕获 v2 五类回归。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始命令：`workspace/tools/effectdemo_render_source.ps1 -Requests workspace/data/vfx_generation/generated/runtime_capture_v2_regression_r001/render_requests.json -ProjectPath workspace/unity-render-staging/EffectDemoPromptHumanR001 -PlayModeRuntime`。
- 原始错误：Unity 退出码 `1`；Package Manager 报 `Failed to resolve packages: The "path" argument must be of type string. Received undefined. No packages loaded.`。
- 影响：五类回归未进入脚本编译和 Play Mode，不能产生任何捕获结论。
- 根因：该历史隔离副本的本地 UPM 路径状态不完整；捕获回归只依赖已经缓存的包和项目资产，不应重新解析该副本的包来源。
- 修复：同一隔离工程执行时显式使用 `-NoUpm`；权威工程仍保留正常 UPM，不修改 `Packages/manifest.json` 规避问题。
- 复验：R002/R003 均使用 `-NoUpm` 启动成功；R003 五类 Prefab 完成脚本编译、Play Mode 和报告输出，Unity 日志无 C#、Shader 或运行异常。
- 预防：历史隔离执行工程默认使用已验证的 `-NoUpm` 路径；UPM 解析错误不得通过修改权威工程包清单掩盖。
- 状态：resolved。

## ERR-UNITY-058

- 日期：2026-09-02
- 任务：`vfx-2df.36` Prefab Play Mode 捕获 v2 调度修复。
- 工程：权威工程 `UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`。
- 原始命令：捕获 R002 前的 R001 五类回归；请求为 `runtime_capture_v2_regression_r001/render_requests.json`。
- 原始现象：0.3 秒 boomerang 的请求时间为 `0.00~0.30s`，逐帧实际墙钟到达 `0.71s`，11 张 PNG 全部为背景；旧批次同名 boomerang 的所谓有效 PNG 也实际全黑。0.15 秒瞬发样本在 R002 中最大请求/实际时间漂移达到约 `0.201s`。
- 根因：每一帧先 `WaitForSecondsRealtime`，之后又通过协程等待下一次 LateUpdate；同步 `Camera.Render + ReadPixels + EncodeToPNG + File.WriteAllBytes` 的阻塞时间还会进入下一帧 delta，短生命周期被跨过。PNG 非空只证明写入成功，不证明时间点正确。
- 修复：捕获调度改为目标绝对 Unity simulation time；`LateUpdate` 在第一个达到目标的模拟帧直接抓取，不再执行双重等待。正式抓帧和镜头评估使用 `Time.captureDeltaTime=plan.Interval` 固定模拟步长，同时分别记录 simulation elapsed、wall-clock elapsed、Unity frame/time。
- 复验：R003 中 1 秒 ground/moving/script 样本最大模拟漂移接近 `0`；0.15 秒 instant 样本最大漂移约 `0.01875s`，不超过一个采样步长，9/9 帧有效且可见；五类报告 `instant_simulation_time_stable=true`。
- 预防：短特效训练证据必须校验请求时间与模拟时间漂移；墙钟只作性能证据，不得作为 Unity 模拟进度。同步 PNG 编码不能改变后续特效时间轴。
- 状态：resolved。

## ERR-UNITY-059

- 日期：2026-09-02
- 任务：`vfx-2df.36` 捕获调度字段重命名。
- 工程：权威工程 `UnityDemo/EffectDemo`；Unity `2022.3.16f1c1`。
- 原始错误：`EffectDemoRuntimeCaptureController.cs(1050,9)/(1062,61): error CS0103: The name 'pendingLateCaptureNotBeforeRealtime' does not exist in the current context`。
- 影响：用户打开的 EffectDemo 2022 工程在字段重命名中间态无法编译，Play Mode 捕获暂不可用。
- 根因：字段已改为 simulation-time 语义，但 `ExecuteAfterLateUpdate` 和 `LateUpdate` 两处仍引用旧的 realtime 名称。
- 修复：统一改为 `pendingLateCaptureNotBeforeSimulationTime`，参数改为 `notBeforeSimulationTime`，比较基准改为 `Time.timeAsDouble`；全文检索旧符号为 0。
- 复验：主工程 Editor.log 显示 `Tundra build success` 并重新导入捕获控制器；隔离工程 R003 再次编译和 Play Mode 通过，相关 Python 测试通过。
- 预防：跨方法字段重命名后必须先全文 `rg` 旧名称，再等待权威 Unity Editor 完成脚本重载；中间编译错误也必须记录，不以最终成功覆盖。
- 状态：resolved。

## ERR-WEB-001

- 日期：2026-09-02
- 任务：`vfx-2df.37.4` Prefab 中文主动复核接入 Unity WebGL。
- 工程与构建：权威工程 `UnityDemo/EffectDemo`；既有 WebGL 构建 `workspace/Builds/WebGL/VfxTrainingPlayer2022PrefabReviewR005AuditR3`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始操作：在 `http://127.0.0.1:8796/` 的 `prefab_active_review_r001` 中，将 `Fx_rayline_body.prefab` 从 Capture v2 截图模式切换到 `http://127.0.0.1:8778/?embed=1&...&catalogId=bd9fa0b2a9121634ca2ca23264b9d098` WebGL 模式。
- 原始错误：浏览器控制台报告 `warning: 2 FS.syncfs operations in flight at once, probably just doing extra work`；同时报告 9 次既有 `The referenced script on this Behaviour (Game Object '<null>') is missing!` 警告。
- 影响：Unity WebGL 仍完成 100% 加载，显示 2 个 ParticleSystem、2 个 Renderer，目标 Prefab 可见并可重播；错误没有写入人工反馈，也不影响同条样本的 9 帧 Capture v2 证据。但该 WebGL 构建不能视为 console-clean，且不适合直接扩大为上千 Prefab 的无条件训练入口。
- 根因：Missing Script 已由 `ERR-UNITY-051` 确认为导入源的上下文缺失。`FS.syncfs` 并发来自既有 WebGL Player 启动期间的文件系统同步，当前只完成单次浏览器复现，尚未定位到 Unity PlayerPrefs、模板脚本或重复初始化中的具体调用方。
- 当前处理：主动复核页默认使用 Capture v2 连续帧；WebGL 仅作为用户可切换的辅助动态视图。系统保留控制台错误，不把 WebGL 可见或该错误转换成人工质量标签。
- 复验：桌面 1280x720 页面中 WebGL iframe 为 618x510，目标画面非空；Capture v2 模式图片为 640x360，播放会推进帧；11 个中文动作完整显示，反馈存储仍为 0 条。架构页无控制台错误。
- 后续：由后续 Beads 扩大 Capture v2 覆盖时，同时复现并定位 `FS.syncfs` 并发调用，按 Prefab 脚本依赖区分“可恢复上下文”和“必须技术排除”的样本。
- 预防：WebGL 验证必须同时检查画面、运行统计和控制台；启动成功或 Prefab 可见都不能覆盖运行时 error。WebGL 不稳定时保留 Capture v2 连续帧作为人工评价主证据。
- 状态：observed，待后续任务定位。

## ERR-UNITY-060

- 日期：2026-09-02
- 任务：`vfx-2df.38.2` EffectDemo 全量 Shader 能力审计。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoFullAssetsR001`；Unity `2022.3.16f1c1`；运行方式 `-noUpm`。
- 原始命令：`Unity.exe -noUpm -batchmode -quit -projectPath .../EffectDemoFullAssetsR001 -executeMethod EffectDemoShaderCapabilityAudit.RunFromCommandLine -shaderCapabilityReport .../effectdemo_shader_capability_audit_r001.json`。
- 原始错误：`EffectDemoShaderCapabilityAudit.cs(157/158): error CS1061: 'Shader' does not contain a definition for 'GetTag'`；`(162/163): error CS0103: ShaderCompilerMessageSeverity does not exist in the current context`。Unity 退出码 `1`，报告未生成。
- 根因：把 `Material.GetTag` 能力误用于 `Shader`，并假定 Shader message severity 枚举位于无需额外命名空间的 API；两者均不符合 Unity 2022.3 当前编译契约。
- 修复：Unity 端不再猜 Shader tag，管线标签改由注册表解析 ShaderLab/HLSL 源码；message severity 使用 `severity.ToString()` 与 `Error/Warning` 比较。staging 的 `currentRenderPipeline` 在 `-noUpm` 下明确写为 `not_loaded_no_upm`，不误报 Built-in。
- 复验：R002/R003 Shader 审计均以退出码 `0` 完成；R003 记录 55 个 Unity 可见 Shader、1846 个 Texture2D、1 个真实 Shader compiler error。主工程 `projects verify` 为 0 errors / 0 warnings。
- 预防：Unity Editor API 必须在目标 2022.3 编译验证；运行管线未加载时写 unknown/not_loaded，不能从空对象推断 Built-in。
- 状态：resolved。

## ERR-VFXDATA-009

- 日期：2026-09-02
- 任务：`vfx-2df.38.2` Texture/Shader/Material 统一能力注册表。
- 原始现象：`asset_registry_r001` 已将 `VFX/YOYO Shader URP` 标为 `blocked_compile_error`，但引用它的 34 个 Material 仍被标为 `usable`。
- 根因：材质组装器只验证 `shader_asset_id` 是否存在，没有验证对应 Shader 的 `binding_status`；“已索引”被错误等同于“可绑定”。
- 影响：如果直接交给 MaterialPlan，34 个材质可能绕过 Shader 编译门禁，生成计划会在 Unity 编译或运行阶段失败。
- 修复：Material candidate 必须引用 `binding_status=project_bindable` 的 Shader；InternalError、compiler error、unsupported 和 missing file 均统一进入 `blocked_shader`。新增编译错误 Shader 与材质的回归测试。
- 复验：`asset_registry_r002/r003` 中 YOYO 的 34 个材质全部为 `blocked_shader`；最终 2138 个材质为 1225 usable、913 blocked，`invalid_materials_marked_usable=0`，全部注册表 Schema/去重/文件门禁为 0。
- 预防：所有跨表引用必须验证目标记录的资格状态，不能只验证 ID 存在；reference-only 与 indexed 都不是 bindable。
- 状态：resolved。

## ERR-VFXDATA-010

- 日期：2026-09-03
- 任务：`vfx-2df.38.7` Capture v2 视觉完整性与用途复核队列。
- 工程：权威工程 `UnityDemo/EffectDemo`；隔离执行工程 `workspace/unity-render-staging/EffectDemoFullAssetsR001`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始现象：`prefab_active_review_full_r008` 将 `Assets/SrRubfish_VFX_03/Prefabs/FX_PF_Fire_GroundBursts_01.prefab` 等材质/Shader 失败画面展示给用户；截图为大块 Unity 纯洋红，仍被当作普通可评价特效。历史五层数据也会把这类截图当颜色/视觉特征，而不是技术失败。
- 影响：用户需要浪费时间判断本应自动排除的样本；错误洋红可能污染颜色标签、视觉自监督和正向生成候选。它不能作为紫色特效或审美负例。
- 弯路：初版仅按 `R>=250,G<=8,B>=250`、至少 64 像素且占全图至少 0.1% 判定，能抓到 13 条，但把正常 `RocketMuzzlePink` 的饱和粉色高亮误判为材质失败。仅提高全图面积阈值会漏掉远景中的小型错误材质面。
- 根因：Unity 错误材质通常由纯洋红主导整个可见 Renderer；正常粉色特效可以有少量饱和洋红，但同时存在大范围光晕、白色核心和其他前景颜色。只检查绝对颜色，未检查洋红在可见前景中的占比。
- 修复：Python 和 Unity Runtime 同时要求纯洋红达到最小像素/全图面积，并占可见前景至少 50%；五层组装、Capture 报告和复核构建统一将命中项路由到 `technical_exclusion/material_render_error`。新增真实坏帧与正常粉色帧回归；复核构建新增 `--carry-feedback-root`，只迁移 Prefab、Capture 和复核模式完全一致的反馈。
- 原始复验命令：`python -m workspace.tools.vfx_generation.capture_visual_integrity --capture-root .../full_prefab_capture_r002 --capture-root .../full_prefab_capture_r003 --output-root .../capture_visual_integrity_r002 --audit-id capture_visual_integrity_r002`；`effectdemo_render_source.ps1 -Requests .../material_error_smoke_r001/render_requests.json -ProjectPath .../EffectDemoFullAssetsR001 -NoUpm -PlayModeRuntime`；同法运行 `pink_effect_smoke_r001` 正常粉色反例。
- 复验：128 个历史捕获中 116 pass、12 个错误洋红 technical exclusion；`GroundBursts` Unity 实测 31/31 有效帧、27 帧材质失败、`visual_evidence_status=material_render_error`、图像训练资格为 false；`RocketMuzzlePink` 17/17 有效帧、0 材质失败、图像训练资格为 true。`prefab_active_review_full_r009` 为 32 条、错误洋红 0、图片加载失败 0、控制台错误 0，并保留 2 条完全兼容反馈。
- 预防：新增 Capture 必须先过视觉完整性门禁再进入五层数据和人工队列；纯洋红只能产生技术排除，不得产生审美或颜色监督；阈值修改必须同时跑真实错误样本和真实粉色/紫色反例。
- 状态：resolved。

## ERR-UNITY-061

- 日期：2026-09-03
- 任务：PrefabGraph 全量结构模型首批候选 Unity 2022 批量编译。
- 工程：权威工程 `UnityDemo/EffectDemo`；Unity `2022.3.16f1c1`；执行方式 `-noUpm -batchmode -nographics`。
- 原始命令：`workspace/tools/effectdemo_compile_prefab_graph_batch.ps1 -Request workspace/data/vfx_generation/generated/prefab_graph_full_model_r001/compile_request.json -ProjectPath UnityDemo/EffectDemo -NoUpm -LogFile workspace/progress/prefab_graph_full_model_r001_compile.log`。
- 原始错误：Unity 退出码 `1073741845`；日志为 `It looks like another Unity instance is running with this project open. Multiple Unity instances cannot open the same project.`。
- 影响：5 个生成候选尚未在该次启动中编译；不能把 Unity 进程崩溃误记为 Graph、材质或 Shader 技术失败。
- 根因：权威 EffectDemo 2022 工程已有 Unity Editor 实例打开，批处理再次打开同一工程触发 Unity 单实例保护。
- 修复：不关闭或抢占用户当前 Unity 实例，改用已有隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001` 进行候选编译和后续运行捕获；编译请求仍使用绝对 Graph/Result 路径和独立 Assets 输出路径。
- 复验：待在隔离工程完成 5 条编译、Prefab 回读和 Play Mode 捕获后更新；本次日志已保留为并发启动失败证据。
- 预防：权威工程有打开实例时，Unity 2022 批处理必须切换到隔离工程；启动前检查项目锁/实例，不能直接重启权威工程。
- 状态：mitigated。

## ERR-UNITY-063

- 日期：2026-09-03
- 任务：Prompt 资产感知生成 `prompt_asset_aware_full_r002` Unity 2022 批量编译。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；注册表 `asset_registry_r003`。
- 原始命令：`workspace/tools/effectdemo_compile_prefab_graph_batch.ps1 -Request .../prompt_asset_aware_full_r002/compile_request.json -ProjectPath .../EffectDemoPromptHumanR001 -NoUpm`。
- 原始错误：8 条候选均出现 `Particle material template could not be loaded`，涉及 `Assets/Hovl Studio/...` 与 `Assets/QFX/...` 材质。
- 影响：注册表中虽标为 `project_bindable` 的资产无法在当前隔离执行工程加载；本批不得进入运行捕获或训练集。
- 根因：资产注册表只证明权威 EffectDemo 内资产可绑定，staging 副本没有这些 Material/Texture/Shader 文件及其 GUID/include 依赖闭包。
- 修复：新增 `stage_material_plan_assets.py`，从最终选中的 MaterialPlan 递归收集 Material/Texture/Shader、GUID 引用和本地 include，连同 `.meta` 同步到 staging；46 个依赖完成 SHA-256 完整性校验。
- 复验：`prompt_asset_aware_full_r003` 同类候选 8/8 Unity 编译通过，24 个贴图绑定均回读匹配；不再使用固定材质回退。
- 预防：任何隔离工程运行前必须执行 MaterialPlan 依赖闭包同步，不能把 registry `project_bindable` 当成 staging 已就绪。
- 状态：resolved。

## ERR-UNITY-064

- 日期：2026-09-03
- 任务：Prompt 资产感知生成 `prompt_asset_aware_full_r002` 依赖同步后的重试编译。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；Unity 2022.3.16f1c1。
- 原始现象：依赖闭包同步后，6/8 候选先通过；2 条失败，一条为 `Refusing to overwrite generated material`（首次部分失败残留），另一条为 `Material ... does not expose planned texture property _NoiseTex`（SphericalDistortion 实际属性不支持）。
- 影响：不能把部分批次结果当作完整资产感知成功，且不能通过删除残留或静默改属性掩盖计划错误。
- 根因：重试沿用已写入的输出目录；MaterialPlan 属性选择只看 Material 审计字段，没有验证选中 Shader 的属性交集。
- 修复：新批次改用隔离输出目录；`material_plan.py` 的属性候选改为 Material 绑定字段与 Shader `property_names` 的交集，无交集时阻断计划；保留原失败目录作为证据。
- 复验：`prompt_asset_aware_full_r003` 8/8 编译通过，覆盖 `Common/ColorDefault`、`ERB/Particles/Blend_CenterGlow`、`QFX/IFX/Cutout/CutoutAB`、`UI/CustomUIDefault`，贴图/Prefab 回读与 Play Mode 均通过。
- 预防：批次重试必须使用新输出版本；AssetPlan 选槽必须同时验证 Material、Shader 和 Unity 实际 `HasProperty` 能力，不能仅依赖审计表字段。
- 状态：resolved。

## ERR-UNITY-062

- 日期：2026-09-03
- 任务：PrefabGraph 全量结构模型候选 Unity API 回读。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；候选 `pfg_7d2a4993852a295e60fa`。
- 原始命令：`workspace/tools/effectdemo_readback_prefab_graph.ps1 -Graph .../asset_upgrade/graphs/pfg_7d2a4993852a295e60fa.json -Prefab Assets/Generated/PrefabGraphFullModelR001/pfg_7d2a4993852a295e60fa.prefab -OutputGraph .../readback/pfg_7d2a4993852a295e60fa.json -NoUpm`。
- 原始现象：Unity 编译结果为 `pass`，但回读为 `mismatch`，差异为 `nodes[pfg_7d2a4993852a295e60fa[0]] unexpected hierarchy path`；保存的 Prefab 根对象名为 `pfg_7d2a4993852a295e60fa`，输入 Graph 根路径为 `GeneratedRoot[0]`。
- 影响：该批次不能作为 Unity API 回读通过的候选；不能把命名规范化误判为材质、贴图或 Shader 失败。
- 根因：`PrefabUtility.SaveAsPrefabAsset` 在当前 Unity 2022 路径下按 `.prefab` 文件名规范化根 GameObject 名称，而生成候选输出文件名使用了 Graph ID，没有保持 Graph 根节点名。
- 修复：后续批量请求按候选隔离目录输出 `GeneratedRoot.prefab`，让 Unity 保存后的根层级与 Graph 的 `GeneratedRoot[0]` 对齐；旧 flat 输出保留为失败证据，不进入交付候选。
- 复验：待使用 `compile_request_r002` 重编译并对全部候选执行 Unity API 回读；同时检查材质/贴图读回和层级差异均为 0。
- 预防：生成 Prefab 的请求构造必须从 Graph 根节点名派生文件名，候选 ID 只能用于目录名；回读必须在运行捕获前完成。
- 状态：mitigated。
## ERR-VFXDATA-020

- 日期：2026-09-04
- 任务：`vfx-2df.42.1` 教程 ProcedureSpec 到 EffectDemo 2022 的首次通用执行。
- 工程：隔离执行工程 `workspace/unity-render-staging/EffectDemoPromptHumanR001`；Unity `2022.3.16f1c1`；URP `14.0.9`。
- 原始命令：`effectdemo_compile_prefab_graph_batch.ps1 -Request .../tutorial_fireworks_effectdemo2022_r001/compile_request.json -ProjectPath .../EffectDemoPromptHumanR001 -NoUpm`，随后执行 Prefab API 回读和 `effectdemo_render_source.ps1 -Requests .../render_requests_focus.json -PlayModeRuntime`。
- 原始现象：Unity 编译和 API 回读通过，33/33 帧生成且无材质洋红；自动全景截图为 `near_blank`，峰值可见面积仅 `0.000703`。强制 front / orthographic `2.5` 后峰值面积提升到 `0.007749`，但仍为 `incomplete_context`，上升段只显示中心小粒子，不符合烟花运动。
- 影响：该样本不得升级为 EffectDemo 2022 已验证 ProcedureSpec，`controller_sft=false`、`positive_generation_supervision=false`。
- 根因：`EXP-2026-004` 摘要保存了五层寿命周期和数值，但没有保存每层的 Transform、运动方向、完整 Shape 配置和镜头意图；通用转换器只能按摘要生成原点爆发，无法恢复教程路径。
- 已采取：保留编译、回读、全景与聚焦捕获证据；将 ProcedureSpec 加入 `source_summary_does_not_preserve_motion_direction_or_transform_mapping` 限制；不通过放大粒子或降低可见门槛伪造成功。
- 后续修复：优先从真实完整制作教程提取对象方向、Transform、Shape、Renderer 和镜头证据；ProcedureSpec 未包含这些字段时，目标工程复现必须保持 blocked。
- 状态：open。
