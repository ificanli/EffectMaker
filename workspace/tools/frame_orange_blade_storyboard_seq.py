from pathlib import Path
import cv2, json, time
root=Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
video=root/'videos'/'BV1mjvxBgESJ_刀光特效制作的底层逻辑（公开课）.mp4'
out=root/'frames'/'BV1mjvxBgESJ'/'storyboard'; out.mkdir(parents=True,exist_ok=True)
cap=cv2.VideoCapture(str(video)); fps=cap.get(cv2.CAP_PROP_FPS); total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); step=int(fps*300)
for i in range(total):
    ok,frame=cap.read()
    if not ok: break
    if i % step == 0:
        t=i/fps; small=cv2.resize(frame,(640,360),interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out/f'{int(t//3600):02d}-{int(t%3600//60):02d}-{int(t%60):02d}.jpg'),small,[cv2.IMWRITE_JPEG_QUALITY,88])
cap.release(); print('decoded',i+1,'saved',len(list(out.glob('*.jpg'))))
