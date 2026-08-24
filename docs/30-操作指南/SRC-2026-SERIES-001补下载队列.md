# 缺失视频补下载队列（SRC-2026-SERIES-001）

> 2026-08-23 主线程整理。下载完成后需校验、重新命名为 `NNN_BV..._标题.mp4`，再解除对应 bd 任务的 blocked 状态。

| 集数 | BV | 标题 | URL | 状态 |
|---:|---|---|---|---|
| 34 | BV1zm421j7Zi | 20240415点评-新课老课一起来 | https://www.bilibili.com/video/BV1zm421j7Zi | blocked |
| 42 | BV1FF411Q7VT | 20230915点评-东西有点多 | https://www.bilibili.com/video/BV1FF411Q7VT | blocked |
| 43 | BV1tu4y1q7kX | 20230816点评 | https://www.bilibili.com/video/BV1tu4y1q7kX | blocked |
| 48 | BV1ja4y1M753 | 20230331点评-666 | https://www.bilibili.com/video/BV1ja4y1M753 | blocked |
| 49 | BV1oo4y1i7TJ | 20230315点评-知识福利大爆发 嗓子都哑了 | https://www.bilibili.com/video/BV1oo4y1i7TJ | blocked |
| 55 | BV1484y1W7JT | 221230点评-元旦快乐 | https://www.bilibili.com/video/BV1484y1W7JT | blocked |
| 57 | BV19V4y1V7Nx | 20221020点评-攒了一个国庆 | https://www.bilibili.com/video/BV19V4y1V7Nx | blocked |
| 61 | BV1iY4y1g7Fg | 20220615点评上 | https://www.bilibili.com/video/BV1iY4y1g7Fg | blocked |

## 补下载命令模板

```bash
python -m yt_dlp --format "30064+30280/bestvideo+bestaudio/best" \
  --merge-output-format mp4 --continue \
  --output "knowledge/sources/SRC-2026-SERIES-001/videos/NNN_%(id)s_%(title)s.%(ext)s" \
  "URL"
```

下载后用 `cv2.VideoCapture` 校验可读、时长、帧率，并在对应 bd 任务评论记录实际文件名。
