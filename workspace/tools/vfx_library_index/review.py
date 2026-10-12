from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from shutil import which
from typing import Callable

from .clustering import classify_title

Runner = Callable[[list[str]], int]


def build_ffmpeg_command(source: Path, destination: Path, second: float | None) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if second is not None:
        command.extend(["-ss", str(second)])
    command.extend(["-i", source.as_posix(), "-frames:v", "1", "-threads", "1", "-c:v", "png", destination.as_posix()])
    return command


def build_last_frame_command(source: Path, destination: Path) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-0.1",
        "-i", source.as_posix(), "-frames:v", "1", "-threads", "1", "-c:v", "png", destination.as_posix(),
    ]


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_stem(relative_path: str, label: str, second: float | None) -> str:
    digest = hashlib.sha1(f"{relative_path}|{label}|{second}".encode("utf-8")).hexdigest()[:12]
    return f"{digest}_{label}.png"


def _safe_media_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _default_runner(command: list[str]) -> int:
    completed = subprocess.run(command, check=False, stdin=subprocess.DEVNULL)
    return completed.returncode


def paginate(items: list[dict], page_size: int) -> list[list[dict]]:
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    return [items[index:index + page_size] for index in range(0, len(items), page_size)]


def build_media_details(records: dict[str, dict], results: list[dict], output: Path | None = None) -> list[dict]:
    grouped: dict[str, dict] = {}
    for result in results:
        relative_path = result["relative_path"]
        record = records.get(relative_path, {})
        key = str(record.get("media_id") or record.get("sha256") or relative_path)
        item = grouped.setdefault(key, {
            "media_id": record.get("media_id") or key,
            "relative_path": relative_path,
            "aliases": [],
            "sha256": record.get("sha256"),
            "media_type": record.get("media_type"),
            "timepoints": [],
        })
        if relative_path != item["relative_path"] and relative_path not in item["aliases"]:
            item["aliases"].append(relative_path)
        item["timepoints"].append({
            key: value for key, value in result.items()
            if key not in {"relative_path"}
        } | {"relative_path": relative_path})
    details = list(grouped.values())
    for item in details:
        classification = classify_title(item["relative_path"])
        item.update({
            "candidate_theme": classification["theme"],
            "matched_terms": classification["matched_terms"],
            "evidence_level": classification["evidence_level"],
            "theme_basis": "filename-keyword-candidate",
        })
        item["aliases"].sort()
        item["timepoints"].sort(key=lambda point: (point.get("second") is None, point.get("second") or 0, point.get("label", "")))
    details.sort(key=lambda item: item["relative_path"])
    return details


def canonicalize_media(details: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for detail in details:
        key = str(detail.get("media_id") or detail.get("sha256") or detail["relative_path"])
        existing = grouped.get(key)
        if existing is None:
            existing = {**detail, "aliases": list(detail.get("aliases", [])), "timepoints": list(detail.get("timepoints", []))}
            grouped[key] = existing
        else:
            paths = [detail["relative_path"], *detail.get("aliases", [])]
            existing["aliases"] = sorted(set(existing.get("aliases", [])) | set(paths) - {existing["relative_path"]})
            existing["timepoints"].extend(detail.get("timepoints", []))
    result = []
    for item in grouped.values():
        paths = sorted({item["relative_path"], *item.get("aliases", [])})
        item["relative_path"] = paths[0]
        item["aliases"] = paths[1:]
        item["timepoints"].sort(key=lambda point: (point.get("relative_path", ""), point.get("second") is None, point.get("second") or 0, point.get("label", "")))
        classification = classify_title(item["relative_path"])
        item.update({
            "candidate_theme": classification["theme"],
            "matched_terms": classification["matched_terms"],
            "evidence_level": classification["evidence_level"],
            "theme_basis": "filename-keyword-candidate",
        })
        result.append(item)
    return sorted(result, key=lambda item: item["relative_path"])


def _write_contact_sheet(frame_paths: list[Path], destination: Path) -> bool:
    if not frame_paths:
        return False
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    images = []
    try:
        for path in frame_paths:
            try:
                with Image.open(path) as image:
                    copy = image.convert("RGB")
                    copy.thumbnail((240, 180), Image.Resampling.LANCZOS)
                    images.append((path, copy.copy()))
            except (OSError, ValueError):
                continue
        if not images:
            return False
        columns = min(4, len(images))
        rows = (len(images) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * 240, rows * 200), "#202020")
        draw = ImageDraw.Draw(sheet)
        for index, (path, image) in enumerate(images):
            x = (index % columns) * 240
            y = (index // columns) * 200
            sheet.paste(image, (x, y))
            draw.text((x + 4, y + 182), path.stem, fill="white")
        destination.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(destination, format="JPEG", quality=90)
        sheet.close()
        return True
    except (OSError, ValueError):
        return False
    finally:
        for _, image in images:
            image.close()


def _write_media_sheet(items: list[dict], destination: Path, output_root: Path) -> bool:
    frame_paths = []
    for item in items:
        for point in item.get("timepoints", []):
            if point.get("status") == "ok" and point.get("output"):
                frame_paths.append(output_root / point["output"])
    return _write_contact_sheet(frame_paths, destination)


def _page_records(items: list[dict], directory: Path, output_root: Path, page_size: int, theme: str | None = None) -> list[dict]:
    pages = []
    for number, page_items in enumerate(paginate(items, page_size), start=1):
        page_path = directory / f"page-{number:03d}.jpg"
        _write_media_sheet(page_items, page_path, output_root)
        page = {
            "page": number,
            "item_count": len(page_items),
            "relative_paths": [item["relative_path"] for item in page_items],
            "media_ids": [item.get("media_id") for item in page_items],
            "output": str(page_path.relative_to(output_root).as_posix()),
        }
        if theme is not None:
            page["candidate_theme"] = theme
        pages.append(page)
    return pages


def _write_index(path: Path, pages: list[dict], *, kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"kind": kind, "pages": pages}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_review(
    source_root: Path,
    manifest_path: Path,
    evidence_path: Path,
    output: Path,
    *,
    runner: Runner | None = None,
    page_size: int = 64,
) -> dict:
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    records = {item["relative_path"]: item for item in _load_jsonl(manifest_path)}
    evidence = _load_jsonl(evidence_path)
    ffmpeg = shutil.which("ffmpeg")
    report: dict = {
        "status": "blocked" if ffmpeg is None else "ready",
        "source_root": str(source_root),
        "manifest": str(manifest_path),
        "evidence_manifest": str(evidence_path),
        "ffmpeg": ffmpeg,
        "evidence_count": len(evidence),
        "successful_evidence_count": 0,
        "failed_evidence_count": 0,
        "results": [],
        "media_details": [],
        "overview_pages": [],
        "theme_pages": [],
        "limitations": [
            "Automated extraction proves file/timepoint availability only; it does not infer visual themes.",
            "Candidate themes are filename-keyword classifications, not visual facts.",
            "External provenance and redistribution rights remain unknown unless separately verified.",
        ],
    }
    if ffmpeg is None:
        report["errors"] = ["ffmpeg executable was not found on PATH"]
        (output / "review_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report

    active_runner = runner or _default_runner
    frame_paths: list[Path] = []
    for point in evidence:
        relative_path = point["relative_path"]
        record = records.get(relative_path)
        result = {**point, "status": "failed"}
        if record is None:
            result["error"] = "relative_path not present in manifest"
        else:
            source = source_root / relative_path
            destination = frames_dir / _safe_stem(relative_path, point["label"], point.get("second"))
            if destination.exists() and destination.stat().st_size > 0:
                result["status"] = "ok"
                result["output"] = str(destination.relative_to(output).as_posix())
                frame_paths.append(destination)
                report["results"].append(result)
                continue
            command = build_ffmpeg_command(source, destination, point.get("second"))
            result["command"] = command
            try:
                return_code = active_runner(command)
                result["return_code"] = return_code
                if return_code == 0 and destination.exists() and destination.stat().st_size > 0:
                    result["status"] = "ok"
                    result["output"] = str(destination.relative_to(output).as_posix())
                    frame_paths.append(destination)
                elif point.get("label") == "end":
                    fallback = build_last_frame_command(source, destination)
                    fallback_code = active_runner(fallback)
                    result["fallback_command"] = fallback
                    result["fallback_return_code"] = fallback_code
                    if fallback_code == 0 and destination.exists() and destination.stat().st_size > 0:
                        result["status"] = "ok"
                        result["output"] = str(destination.relative_to(output).as_posix())
                        result["fallback"] = "last-decodable-frame"
                        frame_paths.append(destination)
                    else:
                        result["error"] = "ffmpeg returned a failure or produced no output"
                else:
                    result["error"] = "ffmpeg returned a failure or produced no output"
            except OSError as error:
                result["error"] = str(error)
        report["results"].append(result)

    report["successful_evidence_count"] = sum(item["status"] == "ok" for item in report["results"])
    report["failed_evidence_count"] = len(report["results"]) - report["successful_evidence_count"]
    if report["successful_evidence_count"] == 0:
        report["status"] = "blocked"
    elif report["failed_evidence_count"]:
        report["status"] = "partial"

    details = canonicalize_media(build_media_details(records, report["results"], output))
    media_dir = output / "media"
    for item in details:
        detail_path = media_dir / f"{_safe_media_id(str(item.get('media_id') or item['relative_path']))}.jpg"
        if _write_media_sheet([item], detail_path, output):
            item["detail_output"] = str(detail_path.relative_to(output).as_posix())
    report["media_details"] = details

    overview_dir = output / "overview"
    report["overview_pages"] = _page_records(details, overview_dir, output, page_size)
    _write_index(overview_dir / "index.json", report["overview_pages"], kind="media-overview")

    themes_dir = output / "themes"
    theme_groups: dict[str, list[dict]] = defaultdict(list)
    for item in details:
        theme_groups[item["candidate_theme"]].append(item)
    for theme in sorted(theme_groups):
        report["theme_pages"].extend(_page_records(theme_groups[theme], themes_dir / theme, output, page_size, theme))
    _write_index(themes_dir / "index.json", report["theme_pages"], kind="candidate-theme-overview")

    report["contact_sheet"] = "contact_sheet.jpg" if _write_contact_sheet(frame_paths[:256], output / "contact_sheet.jpg") else None
    (output / "review_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
