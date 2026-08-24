# -*- coding: utf-8 -*-
"""主线程前台可续跑的单段 Whisper 转写，输出独立 SRT 分段。"""
import argparse, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from faster_whisper import WhisperModel

BASE = r"E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-SERIES-001"

def fmt(t):
    h=int(t//3600); m=int(t%3600//60); s=int(t%60); ms=int((t-int(t))*1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

p=argparse.ArgumentParser(); p.add_argument('episode',type=int); p.add_argument('start',type=float); p.add_argument('duration',type=float); a=p.parse_args()
prefix=f"{a.episode:03d}_"
video=next(f for f in os.listdir(os.path.join(BASE,'videos')) if f.startswith(prefix) and f.endswith('.mp4'))
outdir=os.path.join(BASE,'transcripts',f'parts_ep{a.episode:03d}'); os.makedirs(outdir,exist_ok=True)
out=os.path.join(outdir,f'{int(a.start):05d}-{int(a.start+a.duration):05d}.srt')
model=WhisperModel('base',device='cpu',compute_type='int8',cpu_threads=20,num_workers=1)
segments,info=model.transcribe(os.path.join(BASE,'videos',video),language='zh',vad_filter=True,beam_size=5,clip_timestamps=f'{a.start},{a.start+a.duration}')
with open(out,'w',encoding='utf-8') as f:
    for i,s in enumerate(segments,1): f.write(f'{i}\n{fmt(s.start)} --> {fmt(s.end)}\n{s.text.strip()}\n\n')
print(out)
