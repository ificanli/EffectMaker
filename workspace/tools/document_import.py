"""Document conversion into the knowledge inbox."""

from __future__ import annotations

import shutil
from pathlib import Path

_PLAIN_COPY_SUFFIXES = {".md", ".markdown", ".txt", ".csv", ".json", ".xml"}


def import_document(source: Path, knowledge_root: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    output_dir = knowledge_root / "inbox"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.md"
    if source.suffix.lower() in {".md", ".markdown"}:
        shutil.copyfile(source, output)
        return output
    if source.suffix.lower() in {".txt", ".csv", ".json", ".xml"}:
        output.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return output
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise RuntimeError("MarkItDown 未安装，请运行: python -m pip install -r requirements-media.txt") from exc
    converted = MarkItDown().convert(str(source))
    output.write_text(converted.text_content, encoding="utf-8")
    return output
