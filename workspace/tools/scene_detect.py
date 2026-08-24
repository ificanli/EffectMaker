"""Scene boundary detection helpers backed by PySceneDetect."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Sequence


def normalize_scene_rows(
    scenes: Iterable[Sequence[int]], fps: float, detector: str = "content"
) -> list[dict[str, object]]:
    if fps <= 0:
        raise ValueError("fps must be positive")
    rows = []
    for start_frame, end_frame in scenes:
        rows.append(
            {
                "start_frame": int(start_frame),
                "end_frame": int(end_frame),
                "start_seconds": round(float(start_frame) / fps, 6),
                "end_seconds": round(float(end_frame) / fps, 6),
                "detector": detector,
            }
        )
    return rows


def write_scene_outputs(rows: list[dict[str, object]], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "scenes.json"
    csv_path = output_dir / "scenes.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["start_frame", "end_frame", "start_seconds", "end_seconds", "detector"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return {"json": json_path, "csv": csv_path}


def detect_scenes(video: Path, output_dir: Path, detector: str = "content", threshold: float = 27.0) -> dict[str, Path]:
    try:
        from scenedetect import ContentDetector, SceneManager, open_video
    except ImportError as exc:
        raise RuntimeError("PySceneDetect 未安装，请运行: python -m pip install -r requirements-media.txt") from exc

    video_handle = open_video(str(video))
    try:
        manager = SceneManager()
        if detector != "content":
            raise ValueError("当前仅支持 detector=content")
        manager.add_detector(ContentDetector(threshold=threshold))
        manager.detect_scenes(video_handle)
        scene_list = manager.get_scene_list()
        fps = float(video_handle.frame_rate)
        rows = normalize_scene_rows(
            [(start.frame_num, end.frame_num) for start, end in scene_list], fps, detector
        )
        return write_scene_outputs(rows, output_dir)
    finally:
        close = getattr(video_handle, "close", None)
        if close is not None:
            close()
