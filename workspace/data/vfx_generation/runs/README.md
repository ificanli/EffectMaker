# Runs

每次候选生成称为一个 run。命名建议：

```text
runs/slash_arc_pref_001_r001/
```

推荐结构：

```text
runs/<run_id>/
  run_manifest.json
  auto_eval.jsonl
  feedback.jsonl
  contact_sheets/
    page-001.jpg
    page-002.jpg
  candidates/
    <candidate_id>/
      spec.json
      capture_manifest.json
      captures/
```

大量渲染图片、Unity 导出和临时模型默认不提交。它们可以放在 run 目录下，但会被本目录 `.gitignore` 忽略。

`run_manifest.json` 至少记录：

- run_id
- parent Beads id
- prompt file
- generator version
- candidate count
- render time points
- Unity project path
- scene and camera
- verify and Console status
- contact sheet page paths
- candidate status counts
- frame summary

## 单轮执行顺序

每个 run 按同一顺序执行，避免候选生成、截图、反馈彼此脱节：

```text
1. freeze prompt and search bounds
2. generate candidate specs
3. render fixed time points in Unity
4. run hard-filter auto evaluation
5. build contact sheet from surviving candidates
6. record human feedback and pairwise preferences
7. write next-round mutation hints
```

推荐的自动化入口是 `python -m workspace.tools.vfx_generation.run_pipeline`。

`auto_eval.jsonl` 每行对应一个候选，至少包含：

- `run_id`、`candidate_id`、`seed`
- `status`: `pass` / `reject` / `warn`
- `hard_reject_reasons`
- `metrics`: 可见面积、亮度范围、过曝比例、帧间变化、截图缺失数、Unity error 数
- `rank_hint`: 给 contact sheet 排序用的粗分

自动评价只负责缩小人工审阅范围。最终是否进入下一轮，以 `feedback.jsonl` 为准。

## 捕获模式与时间采样

训练证据必须区分两种捕获模式：

- `editor_particle_simulation`：Editor 中调用 `ParticleSystem.Simulate` 的快速预筛，只验证基础粒子、材质和大致可见性，不能作为最终正向训练证据。
- `play_mode_runtime`：真实进入 Play Mode，让 Player Loop、Animator、Animation、Timeline、脚本生命周期和事件正常推进，可进入人工审核。

最终训练 run 使用 `adaptive_runtime`：每个 Prefab 独立计算粒子 `startDelay + duration + startLifetime`、Animator/Animation clip 和 PlayableDirector 时长；循环效果截一个周期，非循环效果覆盖残留寿命。默认目标为 10 个区间，间隔限制为 `0.02s~0.25s`。例如 1 秒效果生成 `0.0, 0.1, ..., 1.0` 共 11 帧。

完整细帧全部写入候选 capture manifest。联系表最多均匀抽取 6 个关键帧展示，不能用联系表帧数反推实际采样密度。
