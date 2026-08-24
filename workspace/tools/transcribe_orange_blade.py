# -*- coding: utf-8 -*-
import time
from pathlib import Path
from faster_whisper import WhisperModel

root = Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
video = root / 'videos' / 'BV1mjvxBgESJ_刀光特效制作的底层逻辑（公开课）.mp4'
out = root / 'transcripts' / 'BV1mjvxBgESJ_transcript_base.srt'
out.parent.mkdir(parents=True, exist_ok=True)

def fmt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

t0 = time.time()
model = WhisperModel('base', device='cpu', compute_type='int8')
segments, info = model.transcribe(str(video), language='zh', vad_filter=True, beam_size=5, clip_timestamps='0,600')
print(f'language={info.language} prob={info.language_probability:.3f}', flush=True)
with out.open('w', encoding='utf-8') as f:
    for i, seg in enumerate(segments, 1):
        f.write(f'{i}\n{fmt(seg.start)} --> {fmt(seg.end)}\n{seg.text.strip()}\n\n')
        if i % 50 == 0:
            f.flush()
            print(f'seg={i} at={fmt(seg.start)} elapsed={time.time()-t0:.0f}s', flush=True)
print(f'DONE elapsed={time.time()-t0:.0f}s -> {out}')
