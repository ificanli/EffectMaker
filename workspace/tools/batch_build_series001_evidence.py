# -*- coding: utf-8 -*-
"""低优先级批量推进后续集的第一集式视觉证据底座。"""
import os, subprocess, sys
from pathlib import Path

PYTHON = r"C:\Users\luxinyu\AppData\Local\Python\bin\python.exe"
BASE = Path(r"E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-SERIES-001")

# 已完成 ep003；其余已有基础 frames 的视频按序补充第一集结构。
episodes = []
for video in sorted((BASE / "videos").glob("*.mp4")):
    if not (len(video.name) >= 4 and video.name[:3].isdigit() and video.name[3] == "_"):
        continue
    ep = int(video.name[:3])
    if ep in (1, 2, 3):
        continue
    root = BASE / f"ep{ep:03d}"
    marker = root / "objective_metrics.csv"
    if not marker.exists():
        episodes.append(ep)

for pos, ep in enumerate(episodes, 1):
    print(f"[{pos}/{len(episodes)}] START ep{ep:03d}", flush=True)
    completed = subprocess.run([PYTHON, r"E:\Unity特效人工智能学习\workspace\tools\build_episode_evidence.py", str(ep)])
    if completed.returncode:
        print(f"[{pos}/{len(episodes)}] ERROR ep{ep:03d} exit={completed.returncode}", flush=True)
    else:
        print(f"[{pos}/{len(episodes)}] DONE ep{ep:03d}", flush=True)
print("ALL EVIDENCE COMPLETE", flush=True)
