# -*- coding: utf-8 -*-
"""批量生成视觉证据帧：storyboard + 3张全覆盖总览图，跳过已完成"""
import sys, io, os, subprocess, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FF = r"C:\Program Files\ShareX\ffmpeg.exe"
BASE = r"E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-SERIES-001"
VID_DIR = os.path.join(BASE, "videos")
FRAME_BASE = os.path.join(BASE, "frames")

import cv2

files = sorted(f for f in os.listdir(VID_DIR) if f.endswith('.mp4'))
for fname in files:
    ep = fname[:3]
    out_dir = os.path.join(FRAME_BASE, f"ep{ep}")
    marker = os.path.join(out_dir, "overview_3.jpg")
    if os.path.exists(marker):
        print(f"ep{ep} skip", flush=True)
        continue
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(VID_DIR, fname)
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    dur = n / fps if fps else 0
    if dur < 30:
        print(f"ep{ep} too-short {dur:.0f}s only storyboard", flush=True)
        subprocess.run([FF, "-loglevel", "error", "-i", path,
                        "-vf", f"fps=1/{max(dur/12,1):.2f},scale=320:-1,tile=3x4",
                        "-frames:v", "1", "-y", os.path.join(out_dir, "storyboard.jpg")])
        continue
    # storyboard: 12格覆盖全片
    iv = dur / 12
    subprocess.run([FF, "-loglevel", "error", "-i", path,
                    "-vf", f"fps=1/{iv:.2f},scale=320:-1,tile=3x4",
                    "-frames:v", "1", "-y", os.path.join(out_dir, "storyboard.jpg")])
    # 3张总览：全片三等分，每张4x8=32格
    seg = dur / 3
    for i in range(3):
        start = i * seg
        cell = seg / 32
        subprocess.run([FF, "-loglevel", "error", "-ss", f"{start:.1f}", "-i", path,
                        "-t", f"{seg:.1f}",
                        "-vf", f"fps=1/{cell:.2f},scale=640:-1,tile=4x8",
                        "-frames:v", "1", "-y", os.path.join(out_dir, f"overview_{i+1}.jpg")])
    print(f"ep{ep} done dur={dur/60:.0f}m", flush=True)
print("FRAMES ALL DONE", flush=True)
