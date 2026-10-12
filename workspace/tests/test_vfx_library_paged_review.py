from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.tools.vfx_library_index.review import (
    build_media_details,
    canonicalize_media,
    paginate,
    run_review,
)


class PagedReviewTests(unittest.TestCase):
    def test_paginate_rejects_non_positive_size_and_preserves_order(self) -> None:
        with self.assertRaises(ValueError):
            paginate([{"id": 1}], 0)
        self.assertEqual(paginate([{"id": 1}, {"id": 2}, {"id": 3}], 2), [[{"id": 1}, {"id": 2}], [{"id": 3}]])

    def test_canonicalize_media_merges_aliases_by_media_id(self) -> None:
        details = [
            {"media_id": "m1", "relative_path": "z/fire.gif", "sha256": "same", "timepoints": []},
            {"media_id": "m1", "relative_path": "a/fire.gif", "sha256": "same", "timepoints": []},
        ]
        result = canonicalize_media(details)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["relative_path"], "a/fire.gif")
        self.assertEqual(result[0]["aliases"], ["z/fire.gif"])

    def test_run_review_writes_media_and_theme_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.jsonl"
            evidence = root / "evidence.jsonl"
            output = root / "review"
            records = [
                {"media_id": "m1", "relative_path": "fire.gif", "media_type": "gif", "sha256": "same"},
                {"media_id": "m2", "relative_path": "unknown.gif", "media_type": "gif", "sha256": "other"},
            ]
            points = [
                {"relative_path": "fire.gif", "label": "start", "second": 0.0},
                {"relative_path": "fire.gif", "label": "middle", "second": 0.5},
                {"relative_path": "unknown.gif", "label": "start", "second": 0.0},
            ]
            manifest.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
            evidence.write_text("\n".join(json.dumps(item) for item in points) + "\n", encoding="utf-8")

            def runner(command: list[str]) -> int:
                try:
                    from PIL import Image
                    destination = Path(command[-1])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(destination, format="PNG")
                except ImportError:
                    Path(command[-1]).write_bytes(b"png")
                return 0

            with patch("workspace.tools.vfx_library_index.review.which", return_value="ffmpeg"):
                report = run_review(root, manifest, evidence, output, runner=runner, page_size=1)

            self.assertEqual(report["successful_evidence_count"], 3)
            self.assertEqual(len(report["media_details"]), 2)
            self.assertEqual(len(report["overview_pages"]), 2)
            self.assertTrue(any(page.get("candidate_theme") == "fire" for page in report["theme_pages"]))
            self.assertTrue(any(page.get("candidate_theme") == "unclassified" for page in report["theme_pages"]))
            self.assertTrue((output / "overview" / "index.json").exists())
            self.assertTrue((output / "themes" / "index.json").exists())
            self.assertTrue(all((output / page["output"]).stat().st_size > 0 for page in report["overview_pages"]))
            self.assertTrue(all(item.get("detail_output") for item in report["media_details"]))


if __name__ == "__main__":
    unittest.main()
