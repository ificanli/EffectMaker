from __future__ import annotations


DISCLAIMER = (
    "Review order is an evidence-triage aid only; it does not rank quality, taste, "
    "originality, or aesthetic value. The materials are references, not standards."
)


def build_review_queue(triage: dict, review: dict) -> dict:
    failed_keys = {
        (item.get("relative_path"), item.get("label"))
        for item in review.get("results", [])
        if item.get("status") != "ok"
    }
    items = []
    for sample in triage.get("samples", []):
        path = sample["relative_path"]
        sample_failures = sum(1 for key in failed_keys if key[0] == path)
        missing_frames = max(0, 5 - int(sample.get("frame_count") or 0))
        priority = (sample_failures * 100) + (missing_frames * 10) + (1 if (sample.get("luma_range") or 0) > 40 else 0)
        items.append({
            "relative_path": path,
            "sha256": sample.get("sha256"),
            "theme_candidate": sample.get("theme_candidate"),
            "reason": [
                *( ["failed-or-missing-evidence"] if sample_failures or missing_frames else [] ),
                *( ["large-luma-change-signal"] if (sample.get("luma_range") or 0) > 40 else [] ),
                *( ["theme-coverage-entry"] if not sample_failures and not missing_frames else [] ),
            ],
            "triage_priority": priority,
            "observation_status": "unreviewed",
        })
    items.sort(key=lambda item: (-item["triage_priority"], item["theme_candidate"], item["relative_path"]))
    themes = sorted({item["theme_candidate"] for item in items})
    return {
        "status": "review-queue",
        "reference_only": True,
        "disclaimer": DISCLAIMER,
        "theme_count": len(themes),
        "sample_count": len(items),
        "themes": themes,
        "items": items,
        "limitations": [
            "Priority reflects evidence completeness and review needs only.",
            "Filename themes remain candidates until visual review.",
            "No item is labeled good, bad, preferred, or authoritative.",
        ],
    }
