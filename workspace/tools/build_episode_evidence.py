# -*- coding: utf-8 -*-
"""按第一集结构为单集建立视觉证据：时间帧、联系表、三段密集帧、客观指标、案例目录。"""
import argparse, csv, json, os, subprocess
from pathlib import Path
import cv2
from PIL import Image, ImageDraw

try:
    from media import probe as probe_media
except ImportError:
    from workspace.tools.media import probe as probe_media

FFMPEG = r"C:\Program Files\ShareX\ffmpeg.exe"
BASE = Path(r"E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-SERIES-001")

def extract(video, sec, output):
    subprocess.run([FFMPEG, "-loglevel", "error", "-ss", f"{sec:.3f}", "-i", str(video),
                    "-frames:v", "1", "-vf", "scale=640:-1", "-y", str(output)], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep", type=int)
    args = ap.parse_args()
    prefix = f"{args.ep:03d}_"
    videos = list((BASE / "videos").glob(prefix + "*.mp4"))
    if not videos:
        raise SystemExit(f"未找到 ep{args.ep:03d} 视频")
    video = videos[0]
    root = BASE / f"ep{args.ep:03d}"
    visual = root / "visual"
    visual_check = root / "visual_check"
    root.mkdir(exist_ok=True); visual.mkdir(exist_ok=True); visual_check.mkdir(exist_ok=True)
    metadata = probe_media(video)
    (root / "media_meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    dur = frames / fps
    cap.release()
    # 第一集同样的约12个全片锚点
    stamps = [dur * i / 12 for i in range(12)]
    paths = []
    for sec in stamps:
        name = f"{int(sec//3600):02d}-{int(sec%3600//60):02d}-{int(sec%60):02d}.jpg"
        out = visual / name
        if not out.exists(): extract(video, sec, out)
        paths.append((sec, out))
    # 联系表，含时间标签
    thumbs = []
    for sec, p in paths:
        im = Image.open(p).convert("RGB"); im.thumbnail((320, 180))
        canvas = Image.new("RGB", (320, 205), "black"); canvas.paste(im, ((320-im.width)//2, 0))
        ImageDraw.Draw(canvas).text((8, 184), f"{sec//60:02.0f}:{sec%60:02.0f}", fill="white")
        thumbs.append(canvas)
    sheet = Image.new("RGB", (960, ((len(thumbs)+2)//3)*205), "black")
    for i, im in enumerate(thumbs): sheet.paste(im, ((i%3)*320, (i//3)*205))
    sheet.save(visual / "contact-sheet.jpg", "JPEG", quality=92)
    # 3段密集联系图：每段固定 24 张（背景分析工具所需）
    for seg in range(3):
        start = dur * seg / 3; length = dur / 3
        out = visual / f"contact_{seg+1}.jpg"
        if not out.exists():
            interval = length / 24
            subprocess.run([FFMPEG, "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{length:.3f}",
                            "-vf", f"fps=1/{interval:.3f},scale=640:-1,tile=4x6", "-frames:v", "1", "-y", str(out)], check=True)
    # 客观指标：每10秒一帧
    metrics = root / "objective_metrics.csv"
    if not metrics.exists():
        cap = cv2.VideoCapture(str(video))
        with metrics.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f); writer.writerow(["time_sec","mean_brightness","max_brightness","bright_ratio","mean_saturation","edge_density","contrast","bright_center_x","bright_center_y"])
            for sec in range(0, int(dur), 10):
                cap.set(cv2.CAP_PROP_POS_MSEC, sec*1000)
                ok, frame = cap.read()
                if not ok: continue
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV); gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                bright = gray > 220; y, x = bright.nonzero()
                edges = cv2.Canny(gray, 80, 160)
                writer.writerow([sec, round(float(gray.mean()),2), int(gray.max()), round(float(bright.mean()),5), round(float(hsv[:,:,1].mean()),2), round(float((edges>0).mean()),5), round(float(gray.std()),2), round(float(x.mean()/gray.shape[1]),4) if len(x) else "", round(float(y.mean()/gray.shape[0]),4) if len(y) else ""])
        cap.release()
    # 预建目录：转写后按案例名称改名/补关键帧
    for d in ("01_opening", "02_case_a", "03_case_b", "04_case_c", "05_case_d", "06_case_e", "07_case_f", "08_ending"):
        (visual_check / d).mkdir(exist_ok=True)
    (root / "clips").mkdir(exist_ok=True)
    (root / "README.md").write_text(f"# EP{args.ep:03d} 视觉证据\n\n- 视频：`{video.name}`\n- 时长：{dur/60:.2f} 分钟\n- `visual/`：12 个全片锚点、联系表、3 个三段密集联系图\n- `visual_check/`：逐案例证据目录（待按转写补充关键帧和片段）\n- `objective_metrics.csv`：每 10 秒客观画面指标\n", encoding="utf-8")
    print(f"ep{args.ep:03d} evidence ready: {root}")
if __name__ == "__main__": main()
