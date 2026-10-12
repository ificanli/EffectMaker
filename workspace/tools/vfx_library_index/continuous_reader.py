from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable


Runner = Callable[[list[str]], int]
DEFAULT_LABELS = ("start", "quarter", "middle", "three-quarter", "end")


def build_frame_plan(
    duration_seconds: float | None,
    labels: tuple[str, ...] = DEFAULT_LABELS,
) -> list[tuple[str, float | None]]:
    if not labels:
        return []
    if duration_seconds is None or duration_seconds <= 0:
        return [(label, None) for label in labels]
    positions = {
        "start": 0.0,
        "quarter": duration_seconds * 0.25,
        "middle": duration_seconds * 0.5,
        "three-quarter": duration_seconds * 0.75,
        "end": max(0.0, duration_seconds - min(0.05, duration_seconds / 10)),
    }
    return [(label, round(positions.get(label, duration_seconds / 2), 3)) for label in labels]


def _build_command(source: Path, destination: Path, second: float | None, label: str) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if label == "end" and second is not None:
        command.extend(["-sseof", "-0.1"])
    elif second is not None:
        command.extend(["-ss", str(second)])
    command.extend([
        "-i", source.as_posix(), "-frames:v", "1", "-threads", "1", "-c:v", "png",
        destination.as_posix(),
    ])
    return command


def _default_runner(command: list[str]) -> int:
    return subprocess.run(command, check=False, stdin=subprocess.DEVNULL).returncode


def extract_evidence_frames(
    source_root: Path,
    sample: dict,
    output: Path,
    *,
    runner: Runner | None = None,
) -> dict:
    source = source_root / sample["relative_path"]
    output.mkdir(parents=True, exist_ok=True)
    run = runner or _default_runner
    frames = []
    failed_count = 0
    for label, second in build_frame_plan(sample.get("duration_seconds")):
        destination = output / f"{sample['sha256'][:12]}_{label}.png"
        command = _build_command(source, destination, second, label)
        status = "reused" if destination.exists() and destination.stat().st_size > 0 else None
        returncode = 0
        error = None
        if status is None:
            try:
                returncode = run(command)
            except OSError as exc:
                returncode = 1
                error = str(exc)
            if returncode == 0 and destination.exists() and destination.stat().st_size > 0:
                status = "ok"
            else:
                status = "failed"
                failed_count += 1
                error = error or "ffmpeg returned no usable output"
        frames.append({
            "label": label,
            "second": second,
            "status": status,
            "command": command,
            "output": destination.as_posix(),
            "returncode": returncode,
            "error": error,
        })
    return {
        "status": "complete" if failed_count == 0 else "partial",
        "reference_only": True,
        "relative_path": sample["relative_path"],
        "sha256": sample.get("sha256"),
        "frames": frames,
        "failed_count": failed_count,
    }


def write_evidence_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
