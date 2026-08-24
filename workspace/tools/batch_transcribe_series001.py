# -*- coding: utf-8 -*-
"""批量转写 SRC-2026-SERIES-001 全系列：4进程并行，跳过已完成，输出 SRT + flat text"""
import sys, io, os, re, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from concurrent.futures import ProcessPoolExecutor, as_completed

BASE = r"E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-SERIES-001"
VID_DIR = os.path.join(BASE, "videos")
OUT_DIR = os.path.join(BASE, "transcripts")

def fmt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def flatten(srt_path, flat_path):
    with open(srt_path, encoding='utf-8') as f:
        blocks = f.read().strip().split('\n\n')
    out = []
    for b in blocks:
        lines = b.split('\n')
        if len(lines) >= 3:
            t = lines[1].split(' --> ')[0][:8]
            out.append((t, ' '.join(lines[2:])))
    with open(flat_path, 'w', encoding='utf-8') as f:
        cur = -1
        for t, txt in out:
            m = int(t[:2])*60 + int(t[3:5])
            if m // 2 != cur:
                cur = m // 2
                f.write(f"\n[{t}] ")
            f.write(txt)

def transcribe_one(fname):
    from faster_whisper import WhisperModel
    ep = fname[:3]
    bv = fname.split('_')[1]
    srt = os.path.join(OUT_DIR, f"{ep}_{bv}_transcript_base.srt")
    flat = os.path.join(OUT_DIR, f"ep{ep}_text_flat.txt")
    if os.path.exists(srt) and os.path.getsize(srt) > 1000:
        if not os.path.exists(flat):
            flatten(srt, flat)
        return (ep, 'skip', 0)
    t0 = time.time()
    tmp = srt + '.tmp'
    model = WhisperModel('base', device='cpu', compute_type='int8', cpu_threads=4)
    segments, info = model.transcribe(os.path.join(VID_DIR, fname), language='zh', vad_filter=True, beam_size=5)
    with open(tmp, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n{fmt(seg.start)} --> {fmt(seg.end)}\n{seg.text.strip()}\n\n")
    os.replace(tmp, srt)
    flatten(srt, flat)
    return (ep, 'done', time.time() - t0)

if __name__ == '__main__':
    files = sorted(f for f in os.listdir(VID_DIR) if f.endswith('.mp4'))
    # 跳过 001(已有卡片)/002(已完成)；60/51/54 是几分钟的短视频放最后
    files = [f for f in files if not f.startswith(('001_', '002_'))]
    tiny = [f for f in files if f.startswith(('051_', '054_', '060_'))]
    files = [f for f in files if f not in tiny] + tiny
    print(f"queue: {len(files)} files", flush=True)
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(transcribe_one, f): f for f in files}
        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                ep, status, dt = fut.result()
                print(f"[{done}/{len(files)}] ep{ep} {status} {dt:.0f}s", flush=True)
            except Exception as e:
                print(f"[{done}/{len(files)}] {futs[fut]} ERROR {e}", flush=True)
    print("ALL DONE", flush=True)
