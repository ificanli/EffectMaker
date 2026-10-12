"""Reference evidence helpers for teaching-reproduction comparisons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import cv2
from PIL import Image, ImageDraw, ImageFont


def _sample_times(start: float, end: float, step: float) -> list[float]:
    if start < 0 or end < start or step <= 0:
        raise ValueError("invalid time range or step")
    count = int(round((end - start) / step))
    return [round(start + index * step, 6) for index in range(count + 1)]


def extract_dense_frames(
    video: Path,
    output_dir: Path,
    start: float,
    end: float,
    step: float = 0.1,
    width: int = 640,
) -> list[Path]:
    times = _sample_times(start, end, step)
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    paths: list[Path] = []
    try:
        for index, second in enumerate(times):
            if fps:
                capture.set(cv2.CAP_PROP_POS_FRAMES, round(second * fps))
            else:
                capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"cannot decode frame at {second:.3f}s")
            height = max(1, round(frame.shape[0] * width / frame.shape[1]))
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            path = output_dir / f"ref_{index:04d}_{second:08.3f}s.jpg"
            if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92]):
                raise RuntimeError(f"cannot write frame: {path}")
            paths.append(path)
    finally:
        capture.release()
    return paths


def build_contact_sheet(frame_paths: Iterable[Path], output: Path, columns: int = 4) -> Path:
    paths = list(frame_paths)
    if not paths:
        raise ValueError("frame_paths must not be empty")
    images = [Image.open(path).convert("RGB") for path in paths]
    cell_width = max(image.width for image in images)
    cell_height = max(image.height for image in images) + 28
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (cell_width * columns, cell_height * rows), "#202020")
    draw = ImageDraw.Draw(sheet)
    for index, (path, image) in enumerate(zip(paths, images)):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        sheet.paste(image, (x, y + 28))
        draw.text((x + 4, y + 5), path.stem, fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="JPEG", quality=92)
    return output


def build_timeline(
    source_id: str,
    case_id: str,
    video: Path,
    start: float,
    end: float,
    step: float,
    frame_paths: list[Path],
    output: Path,
) -> Path:
    times = _sample_times(start, end, step)
    if len(frame_paths) != len(times):
        raise ValueError("frame count does not match timeline sample count")
    payload = {
        "schema": "teaching-reference-timeline.v1",
        "source_id": source_id,
        "case_id": case_id,
        "video": str(video),
        "start_seconds": start,
        "end_seconds": end,
        "sample_interval_seconds": step,
        "frames": [
            {
                "id": f"ref_{index:04d}",
                "source_time_seconds": second,
                "image": str(path.relative_to(output.parent)).replace("\\", "/"),
                "phase": "unreviewed",
                "observations": {},
            }
            for index, (second, path) in enumerate(zip(times, frame_paths))
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
