# -*- coding: utf-8 -*-
"""Continue Orange blade lecture processing from 01:30 to the end.
Each window is isolated as a WAV before Whisper to avoid rescanning the MP4.
"""
import subprocess, time
from pathlib import Path
from faster_whisper import WhisperModel

ROOT = Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
FFMPEG = Path(r'C:\Users\luxinyu\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build-shared\bin\ffmpeg.exe')
AUDIO = ROOT / 'audio' / 'BV1mjvxBgESJ_16k_mono.wav'
TRANSCRIPTS = ROOT / 'transcripts'
SEGMENTS = ROOT / 'audio' / 'segments'
SEGMENTS.mkdir(parents=True, exist_ok=True)
TRANSCRIPTS.mkdir(parents=True, exist_ok=True)


def fmt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

model = WhisperModel('base', device='cpu', compute_type='int8')
# Process the remaining lecture in bounded windows; completed windows are skipped.
for start in range(5400, 7682, 600):
    end = min(start + 600, 7682)
    label = f'{start//60:02d}-{end//60:02d}'
    wav = SEGMENTS / f'BV1mjvxBgESJ_{label}.wav'
    out = TRANSCRIPTS / f'BV1mjvxBgESJ_{label}_audio_base.srt'
    if out.exists() and out.stat().st_size > 0:
        print('SKIP', label, flush=True)
        continue
    subprocess.run([str(FFMPEG), '-y', '-ss', str(start), '-t', str(end-start), '-i', str(AUDIO), '-c:a', 'pcm_s16le', str(wav)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    segments, info = model.transcribe(str(wav), language='zh', vad_filter=True, beam_size=5)
    with out.open('w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            f.write(f'{i}\n{fmt(seg.start + start)} --> {fmt(seg.end + start)}\n{seg.text.strip()}\n\n')
            if i % 50 == 0:
                f.flush()
    print('DONE', label, 'bytes', out.stat().st_size, 'elapsed', round(time.time()-t0), flush=True)
print('ALL_REMAINING_WINDOWS_DONE', flush=True)
