"""CLI for scene boundary detection and document import."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import document_import, scene_detect


def main() -> None:
    parser = argparse.ArgumentParser(description="视频场景与资料导入工具")
    sub = parser.add_subparsers(dest="command", required=True)

    scenes = sub.add_parser("scenes", help="检测镜头边界")
    scenes.add_argument("video", type=Path)
    scenes.add_argument("output_dir", type=Path)
    scenes.add_argument("--threshold", type=float, default=27.0)

    document = sub.add_parser("import-document", help="将文档转换到 knowledge/inbox")
    document.add_argument("source", type=Path)
    document.add_argument("--knowledge-root", type=Path, default=Path("knowledge"))

    args = parser.parse_args()
    if args.command == "scenes":
        outputs = scene_detect.detect_scenes(args.video, args.output_dir, threshold=args.threshold)
        for path in outputs.values():
            print(path)
    else:
        print(document_import.import_document(args.source, args.knowledge_root))


if __name__ == "__main__":
    main()
