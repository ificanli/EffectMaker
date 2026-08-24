from pathlib import Path
import cv2, json, time

root = Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
video = root / 'videos' / 'BV1mjvxBgESJ_刀光特效制作的底层逻辑（公开课）.mp4'
out = root / 'frames' / 'BV1mjvxBgESJ' / 'storyboard'
out.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(str(video))
fps = cap.get(cv2.CAP_PROP_FPS)
frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
duration = frames / fps if fps else 0
meta = {'video': str(video), 'fps': fps, 'frame_count': frames, 'duration_seconds': duration, 'sample_interval_seconds': 300, 'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S')}
(root / 'frames' / 'BV1mjvxBgESJ' / 'media_meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
t = 0
while t <= duration:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if ok:
        frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out / f'{int(t//3600):02d}-{int(t%3600//60):02d}-{int(t%60):02d}.jpg'), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
    t += 300
cap.release()
print(json.dumps(meta, ensure_ascii=False))
print('frames', len(list(out.glob('*.jpg'))))
