from pathlib import Path
import cv2,sys
root=Path(r'E:\Unity特效人工智能学习\knowledge\sources\SRC-2026-UP389578709')
video=root/'videos'/'BV1mjvxBgESJ_刀光特效制作的底层逻辑（公开课）.mp4'
start,end=map(int,sys.argv[1:3]); out=root/'frames'/'BV1mjvxBgESJ'/f'{start//60:02d}-{end//60:02d}'; out.mkdir(parents=True,exist_ok=True)
cap=cv2.VideoCapture(str(video)); fps=cap.get(cv2.CAP_PROP_FPS); cap.set(cv2.CAP_PROP_POS_FRAMES,start*int(fps)); i=start*int(fps); stop=end*int(fps); step=30*int(fps)
while i<=stop:
 ok,frame=cap.read()
 if not ok: break
 if (i-start*int(fps))%step==0:
  t=i/fps; small=cv2.resize(frame,(640,360),interpolation=cv2.INTER_AREA); good,data=cv2.imencode('.jpg',small,[cv2.IMWRITE_JPEG_QUALITY,90])
  if good: (out/f'{int(t//60):02d}-{int(t%60):02d}.jpg').write_bytes(data.tobytes())
 i+=1
cap.release(); print('frames',len(list(out.glob('*.jpg'))),'decoded',i)
