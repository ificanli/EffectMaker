"""Create a resumable status manifest for one video episode."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PART_RE = re.compile(r"^(?P<start>\d+)-(?P<end>\d+)\.srt$")


def find_episode_video(videos_dir: Path, episode: int) -> Path:
    prefix = f"{episode:03d}_"
    matches = sorted(p for p in videos_dir.glob(prefix + "*.mp4") if p.is_file())
    if not matches:
        raise FileNotFoundError(f"No video found for episode {episode:03d} in {videos_dir}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple videos found for episode {episode:03d}: {matches}")
    return matches[0]


def video_metadata(video: Path) -> dict[str, Any]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for checkpoint scanning") from exc
    capture = cv2.VideoCapture(str(video))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        capture.release()
    duration = frame_count / fps if fps > 0 else None
    return {
        "path": str(video),
        "bytes": video.stat().st_size,
        "fps": fps or None,
        "frames": frame_count or None,
        "width": width or None,
        "height": height or None,
        "duration_seconds": round(duration, 3) if duration is not None else None,
    }


def scan_parts(parts_dir: Path, duration: float | None, part_seconds: int) -> dict[str, Any]:
    files: dict[tuple[int, int], dict[str, Any]] = {}
    if parts_dir.is_dir():
        for path in sorted(parts_dir.glob("*.srt")):
            match = PART_RE.match(path.name)
            if not match:
                continue
            start, end = int(match["start"]), int(match["end"])
            size = path.stat().st_size
            files[(start, end)] = {
                "start": start,
                "end": end,
                "path": str(path),
                "bytes": size,
                "status": "complete" if size > 0 else "empty",
            }

    expected: list[tuple[int, int]] = []
    if duration is not None and duration > 0:
        start = 0
        while start < duration:
            # Segment filenames follow the transcriber’s fixed-window convention;
            # the final window may extend past the actual video end.
            end = start + part_seconds
            expected.append((start, end))
            start = end

    segments = []
    for start, end in expected:
        segments.append(files.get((start, end), {
            "start": start,
            "end": end,
            "path": str(parts_dir / f"{start:05d}-{end:05d}.srt"),
            "bytes": 0,
            "status": "missing",
        }))
    extras = [row for key, row in files.items() if key not in set(expected)]
    return {
        "directory": str(parts_dir),
        "part_seconds": part_seconds,
        "expected_count": len(expected),
        "complete_count": sum(row["status"] == "complete" for row in segments),
        "empty_count": sum(row["status"] == "empty" for row in segments),
        "missing_count": sum(row["status"] == "missing" for row in segments),
        "segments": segments,
        "unexpected_segments": extras,
    }


def artifact_status(source_root: Path, episode: int) -> dict[str, Any]:
    prefix = f"{episode:03d}_"
    transcripts = source_root / "transcripts"
    episode_dir = source_root / f"ep{episode:03d}"
    formal = sorted(transcripts.glob(prefix + "*_transcript_base.srt"))
    flat = transcripts / f"ep{episode:03d}_text_flat.txt"
    reports = {name: (episode_dir / name).is_file() for name in (
        "visual_review_front.md", "visual_review_middle.md", "visual_review_back.md"
    )}
    return {
        "formal_transcript": [str(p) for p in formal],
        "flat_text": {"path": str(flat), "exists": flat.is_file(), "bytes": flat.stat().st_size if flat.is_file() else 0},
        "evidence": {
            "directory": str(episode_dir),
            "exists": episode_dir.is_dir(),
            "objective_metrics": (episode_dir / "objective_metrics.csv").is_file(),
            "contact_sheet": (episode_dir / "visual" / "contact-sheet.jpg").is_file(),
            "reports": reports,
        },
    }


def build_manifest(source_root: Path, episode: int, part_seconds: int) -> dict[str, Any]:
    video = find_episode_video(source_root / "videos", episode)
    metadata = video_metadata(video)
    parts_dir = source_root / "transcripts" / f"parts_ep{episode:03d}"
    return {
        "schema": 1,
        "episode": episode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "video": metadata,
        "transcription": scan_parts(parts_dir, metadata["duration_seconds"], part_seconds),
        "artifacts": artifact_status(source_root, episode),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan one episode and write a resumable manifest")
    parser.add_argument("episode", type=int)
    parser.add_argument("--source-root", type=Path, default=Path("knowledge/sources/SRC-2026-SERIES-001"))
    parser.add_argument("--part-seconds", type=int, default=600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.episode < 1 or args.part_seconds < 1:
        parser.error("episode and part-seconds must be positive")
    source_root = args.source_root.resolve()
    manifest = build_manifest(source_root, args.episode, args.part_seconds)
    output = args.output or (source_root / f"ep{args.episode:03d}" / "episode_manifest.json")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tx = manifest["transcription"]
    print(f"episode={args.episode:03d} duration={manifest['video']['duration_seconds']}s")
    print(f"segments complete={tx['complete_count']} empty={tx['empty_count']} missing={tx['missing_count']} total={tx['expected_count']}")
    print(output)


if __name__ == "__main__":
    main()
