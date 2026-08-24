from pathlib import Path
import cv2, sys
root=Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
video=root/'videos'/sys.argv[1]
slug=video.stem.split('_',1)[0]
duration=int(float(sys.argv[2])); out=root/'frames'/slug; out.mkdir(parents=True,exist_ok=True)
cap=cv2.VideoCapture(str(video)); fps=cap.get(cv2.CAP_PROP_FPS) or 30
next_sample=0.0; i=0
while True:
    ok, frame=cap.read()
    if not ok: break
    t=i/fps
    if t+0.001 >= next_sample:
        small=cv2.resize(frame,(640,360),interpolation=cv2.INTER_AREA)
        good,data=cv2.imencode('.jpg',small,[cv2.IMWRITE_JPEG_QUALITY,90])
        if good: (out/f'{int(t//60):02d}-{int(t%60):02d}.jpg').write_bytes(data.tobytes())
        next_sample += 30.0
    i += 1
cap.release(); print('frames',len(list(out.glob('*.jpg'))),'decoded',i)
