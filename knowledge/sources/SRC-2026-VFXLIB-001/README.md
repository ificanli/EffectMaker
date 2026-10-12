# SRC-2026-VFXLIB-001 扫描说明

本阶段扫描已完成，状态为 `experimental`。共发现 20,350 个输入文件，其中 2,934 个为支持的 GIF/视频媒体，总大小 29,428,894,935 字节；内容哈希重复组 1,461，规范化名称重复组 1,169，探测错误 0。输入目录扫描前后快照一致。
扫描器是只读的，按相对路径稳定排序，使用内容 SHA-256 识别强重复，并将末尾 `(数字)` 下载副本作为名称提示。探测失败会保留条目并记录错误，不会中断整批。

自动代表帧复核已完成：8,798 个证据点中 8,707 个成功生成 PNG，91 个末尾证据点在原始解码和 `-sseof -0.1` 回退后仍失败；失败项和 FFmpeg 命令保存在 `workspace/data/resource_index/vfx_library/review/review_report.json`。兼容联系表为 `workspace/data/resource_index/vfx_library/review/contact_sheet.jpg`，代表帧位于 `workspace/data/resource_index/vfx_library/review/frames/`。分页视觉索引已生成：1,463 个 canonical 媒体、23 张媒体总览页、31 张文件名主题候选页，入口分别为 `workspace/data/resource_index/vfx_library/review/overview/index.json` 和 `workspace/data/resource_index/vfx_library/review/themes/index.json`；单媒体多时间点详情位于 `workspace/data/resource_index/vfx_library/review/media/`。主题分页只用于候选筛选，仍不证明画面主题、制作步骤或授权状态。该自动流程只证明文件和时间点可抽取，不自动推断视觉规律。
