# Unity 制作工程进度

- 结构总览：见 [工程结构总览](../../docs/00-总纲/工程结构总览.md)

## Unity 6 制作工程

- 路径：`E:/UnityVFX/EffectDemo6.0`
- Unity：`6000.5.9f1`
- 渲染管线：URP `17.5.0`
- Pipeline：`com.unity.pipeline 0.5.0-exp.1`
- CLI 项目检查：通过，`errors=0`、`warnings=0`
- Editor：Pipeline Server `7800` 已验证可达。

## Unity 2022 制作工程

- 路径：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo`
- Unity：`2022.3.16f1c1`
- 渲染管线：URP `14.0.9`
- Pipeline：嵌入适配快照 `com.unity.pipeline 0.5.0-exp.1`
- Pipeline Server：`7801`，已验证命令发现和 `create_cli_smoke_effect` 执行。
- 项目检查：`unity projects verify` 通过，`errors=0`、`warnings=0`
- 任务用途：`vfx-2df.16` 及其后续生成式 VFX 训练任务使用该工程承接 `E:/Trains/Unity` 特效资产的本地导入、依赖解析、材质时间线、训练样本反推和 WebGL 动态人工复核。
- 边界：该工程只用于本次源文件摄入/训练搬运任务，不替代 `E:/UnityVFX/EffectDemo6.0` 主制作工程；导入资产默认本地训练参考，不默认提交或公开分发。
- 当前本地导入包：`Assets/VFXSourceIngest/Trains/Trains_FX_All_001/`，来源为 `E:/Trains/Unity`；共 259 个目标 Prefab（含依赖 Prefab），已按 GUID 依赖闭包补齐 Material、Texture、Mesh、Shader 和本地 shader include，源运行时脚本依赖保持记录但未批量导入。
- WebGL 训练复核：播放器源码位于 `Assets/Art/VFX/WebPrefabPlayer/` 和 `Assets/WebGLTemplates/VfxPrefabPlayer/`；使用 Unity `2022.3.16f1c1` 中国版同 revision WebGL Support 构建。稳定输出为 `workspace/Builds/WebGL/VfxTrainingPlayer2022`，当前本地验证地址为 `http://127.0.0.1:8772/`。
- 材质时间线复核：3 个 `play_mode_runtime` 候选的 linked build 位于 `workspace/Builds/WebGL/VfxTrainingPlayer2022MaterialR001`，当前地址为 `http://127.0.0.1:8773/`；人工 feedback 尚未填写。

## Unity 6 源工程

- 路径：`E:/Unity特效人工智能学习/UnityDemo/EffectDemo6.0`
- 作为 Unity 6 制作轨道的源工程保留；不要与 Unity 2022 工程混用资源、Library 或运行状态。

## 验证沙箱

- 路径：`E:/Unity特效人工智能学习/workspace/unity-verification`
- Unity：`2021.3.29f1`
- 仅用于最小验证、批处理测试和环境诊断。
- 该工程独立于主工程，失败或重建不会影响主制作工程。

## 已完成

- 场景搭建基线：Unity 6 源工程已有 CLI/Pipeline 创建、保存和 Play Mode 证据；迁移到对应制作轨道时必须重新验证。
- 后处理配置：Unity 6 源工程已有 Profile 读取和运行证据；Unity 2022 轨道需按版本差异单独记录。

## 双版本使用规则

1. Unity 2022 特效发送到端口 `7801`，Unity 6 特效发送到端口 `7800`。
2. 每个任务先确认 `unity status` 的项目路径和 Editor 版本，再发现命令。
3. 每个实验记录 Editor 版本、URP 版本、Pipeline 端口和验证日志。
4. 所有错误先记录到 `workspace/progress/ERROR_LOG.md`，再修复和验证。
