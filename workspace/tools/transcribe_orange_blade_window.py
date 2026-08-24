# -*- coding: utf-8 -*-
import sys, time
from pathlib import Path
from faster_whisper import WhisperModel
root=Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
audio=root/'audio'/'BV1mjvxBgESJ_16k_mono.wav'
start=int(sys.argv[1]); end=int(sys.argv[2]); label=f'{start//60:02d}-{end//60:02d}'
out=root/'transcripts'/f'BV1mjvxBgESJ_{label}_audio_base.srt'; out.parent.mkdir(parents=True,exist_ok=True)
def fmt(t):
 h=int(t//3600); m=int(t%3600//60); s=int(t%60); ms=int((t-int(t))*1000); return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
t0=time.time(); model=WhisperModel('base',device='cpu',compute_type='int8')
segments,info=model.transcribe(str(audio),language='zh',vad_filter=True,beam_size=5,clip_timestamps=f'{start},{end}')
with out.open('w',encoding='utf-8') as f:
 for i,seg in enumerate(segments,1):
  # clip timestamps are relative to source timeline in faster-whisper output
  f.write(f'{i}\n{fmt(seg.start)} --> {fmt(seg.end)}\n{seg.text.strip()}\n\n')
  if i%50==0: f.flush(); print(f'seg={i} at={fmt(seg.start)} elapsed={time.time()-t0:.0f}s',flush=True)
print(f'DONE {out} elapsed={time.time()-t0:.0f}s',flush=True)
