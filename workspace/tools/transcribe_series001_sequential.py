# -*- coding: utf-8 -*-
"""复刻第一集工作流的转写阶段：单进程、20 CPU 线程、断点续跑。"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from faster_whisper import WhisperModel

BASE = r"E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-SERIES-001"
VID_DIR = os.path.join(BASE, "videos")
OUT_DIR = os.path.join(BASE, "transcripts")

def fmt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def flatten(srt, out):
    with open(srt, encoding="utf-8") as f:
        blocks = f.read().strip().split("\n\n")
    with open(out, "w", encoding="utf-8") as f:
        minute_bucket = -1
        for b in blocks:
            lines = b.split("\n")
            if len(lines) < 3:
                continue
            ts = lines[1].split(" --> ")[0][:8]
            bucket = (int(ts[:2]) * 60 + int(ts[3:5])) // 2
            if bucket != minute_bucket:
                minute_bucket = bucket
                f.write(f"\n[{ts}] ")
            f.write(" ".join(lines[2:]))

def main():
    model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=20, num_workers=1)
    files = sorted(f for f in os.listdir(VID_DIR) if f.endswith(".mp4") and not f.startswith(("001_", "002_")))
    for index, fname in enumerate(files, 1):
        ep, bv = fname[:3], fname.split("_")[1]
        srt = os.path.join(OUT_DIR, f"{ep}_{bv}_transcript_base.srt")
        flat = os.path.join(OUT_DIR, f"ep{ep}_text_flat.txt")
        if os.path.exists(srt) and os.path.getsize(srt) > 1024:
            if not os.path.exists(flat): flatten(srt, flat)
            print(f"[{index}/{len(files)}] ep{ep} skip", flush=True)
            continue
        tmp = srt + ".tmp"
        if os.path.exists(tmp): os.remove(tmp)
        t0 = time.time()
        print(f"[{index}/{len(files)}] START ep{ep} {fname}", flush=True)
        segments, info = model.transcribe(os.path.join(VID_DIR, fname), language="zh", vad_filter=True, beam_size=5)
        count = 0
        with open(tmp, "w", encoding="utf-8") as f:
            for count, segment in enumerate(segments, 1):
                f.write(f"{count}\n{fmt(segment.start)} --> {fmt(segment.end)}\n{segment.text.strip()}\n\n")
                if count % 100 == 0:
                    f.flush()
        os.replace(tmp, srt)
        flatten(srt, flat)
        print(f"[{index}/{len(files)}] DONE ep{ep}: {count} segments, {time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__": main()
