from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_library_index.review_server import (
    build_server_manifest,
    load_review_queue,
)


class ReviewServerTests(unittest.TestCase):
    def test_load_review_queue_rejects_non_reference_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.json"
            path.write_text(json.dumps({"status": "review-queue", "reference_only": False}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_review_queue(path)

    def test_build_server_manifest_exposes_frame_urls_without_quality_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = {"status": "review-queue", "reference_only": True, "items": [{
                "relative_path": "fire.gif", "sha256": "abc", "theme_candidate": "fire"
            }]}
            manifest = build_server_manifest(queue, root)
            payload = json.dumps(manifest)
            self.assertIn("fire.gif", payload)
            self.assertNotIn("quality_score", payload)
            self.assertNotIn("aesthetic_score", payload)

    def test_build_server_manifest_uses_review_report_output_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "actual_start.png").write_bytes(b"png")
            queue = {"status": "review-queue", "reference_only": True, "items": [{
                "relative_path": "fire.gif", "sha256": "abc", "theme_candidate": "fire"
            }]}
            review = {"results": [{
                "relative_path": "fire.gif", "label": "start", "status": "ok", "output": "frames/actual_start.png"
            }]}
            manifest = build_server_manifest(queue, root, review)
            self.assertTrue(manifest["samples"][0]["frames"][0]["available"])
            self.assertEqual(manifest["samples"][0]["frames"][0]["url"], "/frames/actual_start.png")


if __name__ == "__main__":
    unittest.main()
