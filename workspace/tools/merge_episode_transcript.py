"""Merge fixed-window SRT parts and create a timestamped flat text file."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

PART_RE = re.compile(r"^(\d+)-(\d+)\.srt$")
BLOCK_RE = re.compile(r"^\s*\d+\s*\n(?P<time>\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3})\s*\n(?P<text>.*?)(?:\n\s*)?$", re.S)


def read_blocks(path: Path) -> list[tuple[str, str]]:
    blocks = []
    for raw in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig")):
        match = BLOCK_RE.match(raw)
        if match:
            text = " ".join(line.strip() for line in match["text"].splitlines() if line.strip())
            if text:
                blocks.append((match["time"], text))
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge episode SRT parts")
    parser.add_argument("episode", type=int)
    parser.add_argument("--source-root", type=Path, default=Path("knowledge/sources/SRC-2026-SERIES-001"))
    args = parser.parse_args()
    root = args.source_root.resolve()
    transcripts = root / "transcripts"
    parts = transcripts / f"parts_ep{args.episode:03d}"
    files = []
    for path in parts.glob("*.srt"):
        match = PART_RE.match(path.name)
        if match:
            files.append((int(match.group(1)), path))
    files.sort()
    if not files:
        raise FileNotFoundError(parts)
    blocks = []
    for _, path in files:
        blocks.extend(read_blocks(path))
    prefix = f"{args.episode:03d}_"
    videos = sorted((root / "videos").glob(prefix + "*.mp4"))
    if len(videos) != 1:
        raise RuntimeError(f"Expected one episode video, found {len(videos)}")
    stem = videos[0].stem
    formal = transcripts / f"{stem}_transcript_base.srt"
    formal.write_text("\n\n".join(f"{i}\n{time}\n{text}" for i, (time, text) in enumerate(blocks, 1)) + "\n\n", encoding="utf-8")
    flat = transcripts / f"ep{args.episode:03d}_text_flat.txt"
    lines = []
    for time, text in blocks:
        stamp = time.split(" --> ", 1)[0][:8]
        lines.append(f"[{stamp}] {text}")
    flat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"parts={len(files)} entries={len(blocks)}")
    print(formal)
    print(flat)


if __name__ == "__main__":
    main()
