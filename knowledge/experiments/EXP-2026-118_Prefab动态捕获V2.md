# EXP-2026-118：Prefab 动态捕获 V2

## 问题

旧 Play Mode 捕获虽优于编辑器 `ParticleSystem.Simulate`，但仍在同一 Prefab 实例上执行 Bounds 预跑和正式截图。`ResetAndPlay` 只重置 ParticleSystem、Animator、Animation 和 PlayableDirector，不能恢复任意 MonoBehaviour、协程、动态材质、MaterialPropertyBlock、Trail/LineRenderer 或静态状态。相机仅在正面/俯视间猜测，窗口又被截断为 3 秒；非空 PNG 仍可能是全黑、错角度或错时间。

## V2 机制

1. Bootstrap 只保存 Prefab 资产引用，不在进入 Play Mode 前实例化可复用对象。
2. Bounds 探测、三机位评估和正式截图分别从 Prefab 新建实例，前两者使用后销毁。
3. front、side、top 在五个代表时间点低分辨率真实渲染，按可见面积、边缘触碰和中心偏移选择。
4. 捕获相机标记 `MainCamera`；标准上下文提供 EventSystem、地面 Collider、目标和角色锚点；ScreenSpaceOverlay Canvas 转为捕获 Camera。
5. 粒子关闭 auto random seed，按 candidate + hierarchy path 写入稳定 seed。
6. 时长上限恢复为 8 秒，最大间隔 0.1 秒；正式截图和镜头评估使用 `Time.captureDeltaTime`，PNG 编码墙钟开销不再推进后续模拟时间。
7. 每帧记录 requested/simulation/wall-clock 时间、Unity frame/time、camera view、可见面积、裁切率和中心偏移。
8. Capture manifest 分离 technical、image-sequence 和 full-visual 三种资格；未知 Shader global 或无法枚举 MPB 时 full-visual 必须为 false。

## 回归样本

| 类别 | 样本 | 结果 |
|---|---|---|
| instant | `Fx_rayline_body` | 0.15 秒、9/9 帧，约 0.01875 秒间隔，最大模拟漂移约一个短步长 |
| moving | 确定性移动探针 | 1 秒、11/11 帧，移动主体可见，模拟漂移接近 0 |
| ground | `Fx_Tip_Common_Circle` | 11/11 帧，环形范围可见，无裁切 |
| ui | `FX_ui_jiyinsuo` | 8 秒上限、81/81 帧，UI 六边形可见，MainCamera/EventSystem 上下文有效 |
| script-material | MaterialStateProbe | 11/11 帧，33 个材质/keyword/MPB delta，动态状态为 true |

最终报告：`workspace/data/vfx_generation/generated/runtime_capture_v2_regression_r003/regression_report.json`，所有质量门禁为 true，状态 `pass`。代表帧已人工打开核对，不只检查文件和像素统计。

## 训练边界

- 五类图像序列均可作为带上下文的技术图像证据。
- Shader global 尚未插桩，因此本批 `full_visual_training_eligible=false`；不能声称完整还原了全部脚本材质状态。
- 自定义脚本的未来触发时间仍不可从组件自动推断；存在 custom script 时 manifest 写 `custom_script_duration_unbounded`，最长 8 秒之外的事件仍需专门上下文配置。
- `run_pipeline` 已接入 v2 硬门禁；上下文不完整、实例隔离失败或 image-sequence 不合格会直接拒绝进入图像训练。
