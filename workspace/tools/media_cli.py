"""Command line entry point for shared video media operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from . import media
except ImportError:
    from workspace.tools import media


def main() -> None:
    parser = argparse.ArgumentParser(description="统一视频媒体处理工具")
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="读取并保存媒体元数据")
    probe.add_argument("video", type=Path)
    probe.add_argument("--output", type=Path)

    frame = sub.add_parser("frame", help="抽取单帧")
    frame.add_argument("video", type=Path)
    frame.add_argument("second", type=float)
    frame.add_argument("output", type=Path)

    audio = sub.add_parser("audio", help="提取 16kHz 单声道 WAV")
    audio.add_argument("video", type=Path)
    audio.add_argument("output", type=Path)

    cut_audio = sub.add_parser("cut-audio", help="导出音频时间片段")
    cut_audio.add_argument("source", type=Path)
    cut_audio.add_argument("start", type=float)
    cut_audio.add_argument("end", type=float)
    cut_audio.add_argument("output", type=Path)

    cut_video = sub.add_parser("cut-video", help="导出视频时间片段")
    cut_video.add_argument("video", type=Path)
    cut_video.add_argument("start", type=float)
    cut_video.add_argument("end", type=float)
    cut_video.add_argument("output", type=Path)

    args = parser.parse_args()
    tools = media.resolve_tools()
    if args.command == "probe":
        result = media.probe(args.video, tools, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "frame":
        media.extract_frame(args.video, args.second, args.output, tools)
    elif args.command == "audio":
        media.extract_audio(args.video, args.output, tools)
    elif args.command == "cut-audio":
        media.cut_audio(args.source, args.start, args.end, args.output, tools)
    elif args.command == "cut-video":
        media.cut_video(args.video, args.start, args.end, args.output, tools)


if __name__ == "__main__":
    main()
