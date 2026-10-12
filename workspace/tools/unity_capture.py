"""Evidence manifest helpers for Unity runtime captures."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _frame_record(frame: dict, root: Path) -> dict:
    path = Path(frame["path"])
    if not path.is_absolute():
        path = (root / path).resolve()
    try:
        relative = path.relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = path.name
    if not path.exists():
        return {
            "requested_time_seconds": frame["requested_time_seconds"],
            "path": relative,
            "valid": False,
            "error": "missing capture file",
        }
    size = path.stat().st_size
    if size <= 0:
        return {
            "requested_time_seconds": frame["requested_time_seconds"],
            "path": relative,
            "valid": False,
            "error": "capture file is empty",
        }
    return {
        "requested_time_seconds": frame["requested_time_seconds"],
        "capture_time_seconds": frame.get("capture_time_seconds"),
        "path": relative,
        "file_size": size,
        "valid": True,
        "error": None,
    }


def build_manifest(
    root: Path,
    *,
    scene: str,
    effect: str,
    camera: str,
    resolution: tuple[int, int],
    editor_status: str,
    play_requested: bool,
    frames: Iterable[dict],
) -> dict:
    root = root.resolve()
    records = [_frame_record(frame, root) for frame in frames]
    return {
        "schema": "unity-capture-manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "capture_root": root.as_posix(),
        "scene": scene,
        "effect": effect,
        "camera": camera,
        "resolution": list(resolution),
        "editor_status": editor_status,
        "play_requested": play_requested,
        "frames": records,
        "valid_frame_count": sum(1 for record in records if record["valid"]),
        "invalid_frame_count": sum(1 for record in records if not record["valid"]),
    }


def write_manifest(
    output: Path,
    *,
    root: Path | None = None,
    scene: str,
    effect: str,
    camera: str,
    resolution: tuple[int, int],
    editor_status: str,
    play_requested: bool,
    frames: Iterable[dict],
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_manifest(
        root or output.parent,
        scene=scene,
        effect=effect,
        camera=camera,
        resolution=resolution,
        editor_status=editor_status,
        play_requested=play_requested,
        frames=frames,
    )
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Unity capture files and write a manifest.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--frames", type=Path, required=True, help="JSON list of requested_time_seconds/path records")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--effect", required=True)
    parser.add_argument("--camera", default="Main Camera")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--editor-status", default="unknown")
    parser.add_argument("--play-requested", action="store_true")
    args = parser.parse_args(argv)
    frames = json.loads(args.frames.read_text(encoding="utf-8"))
    path = write_manifest(
        args.output,
        root=args.root,
        scene=args.scene,
        effect=args.effect,
        camera=args.camera,
        resolution=(args.width, args.height),
        editor_status=args.editor_status,
        play_requested=args.play_requested,
        frames=frames,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
