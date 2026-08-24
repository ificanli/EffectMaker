"""Shared FFmpeg helpers for the video evidence workflow."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class MediaTools:
    ffmpeg: Path
    ffprobe: Path


_WINDOWS_FFMPEG_CANDIDATES = (
    Path(r"C:\Program Files\ShareX\ffmpeg.exe"),
    Path(r"C:\Program Files\ShareX\ffprobe.exe"),
)
_WINGET_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"


def _find_winget_binary(name: str) -> Path | None:
    if not _WINGET_ROOT.is_dir():
        return None
    matches = sorted(_WINGET_ROOT.glob(f"Gyan.FFmpeg.Shared_*\\**\\{name}.exe"))
    return matches[0] if matches else None


def _resolve_binary(env_name: str, name: str, candidates: Sequence[Path]) -> Path:
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured)
    located = shutil.which(name)
    if located:
        return Path(located)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    winget = _find_winget_binary(name)
    if winget:
        return winget
    return Path(name)


def resolve_tools() -> MediaTools:
    """Resolve binaries without requiring them to exist until execution time."""
    return MediaTools(
        ffmpeg=_resolve_binary("VFX_FFMPEG", "ffmpeg", (_WINDOWS_FFMPEG_CANDIDATES[0],)),
        ffprobe=_resolve_binary("VFX_FFPROBE", "ffprobe", (_WINDOWS_FFMPEG_CANDIDATES[1],)),
    )


def build_probe_command(video: Path, ffprobe: Path | str = "ffprobe") -> list[str]:
    return [
        str(ffprobe),
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(video),
    ]


def validate_interval(start: float, end: float) -> None:
    if start < 0 or end <= start:
        raise ValueError("end must be greater than start, and start must be non-negative")


def _fps(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def normalize_metadata(payload: dict[str, Any], video: Path, output: Path | None = None) -> dict[str, Any]:
    fmt = payload.get("format") or {}
    streams = payload.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = fmt.get("duration")
    result: dict[str, Any] = {
        "source": str(video),
        "format": fmt.get("format_name"),
        "duration_seconds": float(duration) if duration not in (None, "N/A") else None,
        "video_stream": video_stream.get("index"),
        "audio_stream": audio_stream.get("index"),
        "video": {
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": _fps(video_stream.get("r_frame_rate")),
            "codec": video_stream.get("codec_name"),
        },
        "audio": {
            "codec": audio_stream.get("codec_name"),
            "sample_rate": int(audio_stream["sample_rate"]) if audio_stream.get("sample_rate", "").isdigit() else None,
            "channels": audio_stream.get("channels"),
        },
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _read_probe_payload(video: Path, tools: MediaTools) -> dict[str, Any]:
    completed = subprocess.run(build_probe_command(video, tools.ffprobe), check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def probe(video: Path, tools: MediaTools | None = None, output: Path | None = None) -> dict[str, Any]:
    tools = tools or resolve_tools()
    result = normalize_metadata(_read_probe_payload(video, tools), video, output)
    return result


def extract_frame(video: Path, second: float, output: Path, tools: MediaTools | None = None, width: int = 640) -> None:
    if second < 0:
        raise ValueError("second must be non-negative")
    tools = tools or resolve_tools()
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(tools.ffmpeg), "-loglevel", "error", "-ss", f"{second:.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-1", "-y", str(output)],
        check=True,
    )


def extract_audio(video: Path, output: Path, tools: MediaTools | None = None, sample_rate: int = 16000) -> None:
    tools = tools or resolve_tools()
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(tools.ffmpeg), "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(output)], check=True)


def cut_audio(source: Path, start: float, end: float, output: Path, tools: MediaTools | None = None) -> None:
    validate_interval(start, end)
    tools = tools or resolve_tools()
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(tools.ffmpeg), "-y", "-ss", f"{start:.3f}", "-t", f"{end-start:.3f}", "-i", str(source), "-c:a", "pcm_s16le", str(output)], check=True)


def cut_video(video: Path, start: float, end: float, output: Path, tools: MediaTools | None = None) -> None:
    validate_interval(start, end)
    tools = tools or resolve_tools()
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(tools.ffmpeg), "-y", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{end-start:.3f}", "-c", "copy", str(output)], check=True)
