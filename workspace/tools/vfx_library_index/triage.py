from __future__ import annotations

import json
from pathlib import Path

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    Image = None
    ImageStat = None


DISCLAIMER = (
    "Objective frame statistics are triage signals only; they do not rate quality, "
    "taste, originality, or suitability as an aesthetic standard."
)


def _frame_stats(path: Path) -> dict:
    if Image is None:
        return {"status": "blocked", "error": "Pillow is not installed", "path": path.as_posix()}
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            rgb = rgba.convert("RGB")
            pixels = list(rgba.getdata())
            alpha_values = [pixel[3] for pixel in pixels]
            mean_rgb = ImageStat.Stat(rgb).mean
            return {
                "status": "ok",
                "path": path.as_posix(),
                "width": rgba.width,
                "height": rgba.height,
                "alpha_zero_ratio": round(alpha_values.count(0) / len(alpha_values), 6),
                "nontransparent_ratio": round(sum(value > 0 for value in alpha_values) / len(alpha_values), 6),
                "mean_rgb": [round(value, 3) for value in mean_rgb],
                "mean_luma": round(sum(mean_rgb) / 3, 3),
            }
    except Exception as error:
        return {"status": "failed", "path": path.as_posix(), "error": str(error)}


def analyze_visual_package(package_path: Path, review_path: Path, output: Path) -> dict:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review_by_key = {(item["relative_path"], item["label"]): item for item in review.get("results", [])}
    samples = []
    available_count = 0
    failed_count = 0
    for sample in package.get("samples", []):
        frames = []
        for point in sample["evidence"]:
            item = review_by_key.get((point["relative_path"], point["label"]))
            if not item or item.get("status") != "ok":
                frames.append({**point, "frame_status": "unavailable"})
                failed_count += 1
                continue
            frame = _frame_stats(review_path.parent / item["output"])
            if frame.get("status") == "ok":
                available_count += 1
            else:
                failed_count += 1
            frames.append({**point, "frame": frame, "frame_status": frame.get("status")})
        available = [item for item in frames if item.get("frame_status") == "ok"]
        lumas = [item["frame"]["mean_luma"] for item in available]
        samples.append({
            "relative_path": sample["relative_path"],
            "sha256": sample.get("sha256"),
            "theme_candidate": sample["theme_candidate"],
            "frame_count": len(available),
            "mean_luma_min": min(lumas) if lumas else None,
            "mean_luma_max": max(lumas) if lumas else None,
            "luma_range": round(max(lumas) - min(lumas), 3) if lumas else None,
            "frames": frames,
        })
    report = {
        "status": "triage-only",
        "reference_only": True,
        "disclaimer": DISCLAIMER,
        "sample_count": len(samples),
        "available_frame_count": available_count,
        "unavailable_or_failed_frame_count": failed_count,
        "samples": samples,
        "limitations": [
            "Statistics describe encoded frames, not perceived quality or design value.",
            "Theme candidates remain filename-derived until continuous visual review.",
            "No aesthetic ranking or implementation inference is produced.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "triage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
