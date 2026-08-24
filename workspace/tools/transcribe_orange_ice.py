# -*- coding: utf-8 -*-
import subprocess, sys, time
from pathlib import Path
from faster_whisper import WhisperModel

ROOT = Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
FFMPEG = Path(r'C:\Users\luxinyu\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build-shared\bin\ffmpeg.exe')
video = ROOT / 'videos' / sys.argv[1]
slug = video.stem.split('_', 1)[0]
duration = int(float(sys.argv[2]))
label = sys.argv[3]
audio_dir = ROOT / 'audio'; trans_dir = ROOT / 'transcripts'; seg_dir = ROOT / 'audio_segments'
for d in (audio_dir, trans_dir, seg_dir): d.mkdir(parents=True, exist_ok=True)
audio = audio_dir / f'{slug}_16k_mono.wav'
if not audio.exists():
    subprocess.run([str(FFMPEG), '-y', '-i', str(video), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(audio)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fmt(t):
    h=int(t//3600); m=int(t%3600//60); s=int(t%60); ms=int((t-int(t))*1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
model=WhisperModel('base', device='cpu', compute_type='int8')
t0=time.time()
for start in range(0, duration, 600):
    end=min(start+600, duration)
    name=f'{slug}_{start//60:02d}-{end//60:02d}_{label}.srt'
    out=trans_dir/name
    if out.exists() and out.stat().st_size > 0:
        print('SKIP', start, end, flush=True); continue
    wav=seg_dir/f'{slug}_{start:05d}-{end:05d}.wav'
    subprocess.run([str(FFMPEG), '-y', '-ss', str(start), '-t', str(end-start), '-i', str(audio), '-c:a', 'pcm_s16le', str(wav)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    segments, _ = model.transcribe(str(wav), language='zh', vad_filter=True, beam_size=5)
    with out.open('w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            f.write(f'{i}\n{fmt(seg.start+start)} --> {fmt(seg.end+start)}\n{seg.text.strip()}\n\n')
            if i % 50 == 0: f.flush()
    print('DONE', start, end, out.stat().st_size, 'elapsed', int(time.time()-t0), flush=True)
print('ALL_ICE_TRANSCRIPTS_DONE', slug, flush=True)
