# Public repository upload rules

This repository contains the reproducible parts of a Unity VFX and AI-assisted learning workspace:

- `UnityDemo/`: Unity project source and project settings that are suitable for version control.
- `workspace/`: media utilities, indexing code, tests, and verification notes.
- `knowledge/`: source records, links, transcripts, visual review notes, cards, and experiments.
- `docs/`: operating procedures and project documentation.

## Entry points

- `docs/00-总纲/工程结构总览.md`: canonical repository boundaries and placement rules.
- `UnityDemo/README.md`: project selection and version split between the active Unity 6 project and the legacy compatibility project.
- `workspace/README.md`: workspace map for tools, data, progress, tests, and the verification sandbox.
- `workspace/progress/UNITY_PROJECT_INDEX.md`: current project routing.
- `knowledge/index.md`: source and knowledge traceability.
- `docs/30-操作指南/生成式VFX训练标准.md`: Prefab/视频/教程/评价课程到特征矩阵、排序权重和下一轮 VFXSpec 的训练标准。
- `docs/00-总纲/VFX审美资料训练方案.md`: 审美点评、参考视频、Unity连续帧和人工反馈如何训练 VFX Judge、偏好排序器并接入 Controller。
- `docs/30-操作指南/VFX Controller训练基线.md`: MiniMind 参考边界、千级 Prefab 语料索引、Controller 数据导出和训练门禁。
- `docs/30-操作指南/Unity-WebGL-Prefab特效播放器.md`: 在浏览器中真实运行 `UnityDemo/EffectDemo` 2022 Trains Prefab 的动态训练播放器、构建和验证入口。

For the local FBX/OBJ geometry metadata and Blender preview prototype, see [`docs/30-操作指南/FBX几何索引与预览原型使用指南.md`](docs/30-操作指南/FBX几何索引与预览原型使用指南.md).

## Media and asset boundary

Video and audio files are intentionally not committed. The local workspace may contain downloaded copies under `knowledge/sources/**/videos/` and derived audio under `audio/` or `audio_segments/`; these paths are ignored by Git. Source records retain the original public reference, usually a Bilibili space or BV page, so the material can be located without redistributing the downloaded file.

The repository also excludes local Unity caches, generated editor indexes, model/RAG caches, archives, and raw files under `resource/`. Raw assets are not assumed to be redistributable merely because they exist locally; add them only after their license and redistribution permission have been verified.

## Reproducing local media evidence

Install the media dependencies from `requirements-media.txt`, then use the shared commands documented in `docs/30-操作指南/统一媒体工具.md`. Downloaded media stays local and should not be added with `git add -f`.

## Repository status

This is a learning workspace rather than a packaged game release. Unity Editor version, render pipeline, evidence status, and licensing limitations are recorded in the project documentation and source records.
