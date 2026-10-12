import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.tools.vfx_library_index.scanner import normalize_download_name, scan_library


class ScannerTests(unittest.TestCase):
    def test_normalize_download_name_strips_terminal_download_suffix(self):
        self.assertEqual(normalize_download_name("Ray(1).gif"), "Ray.gif")
        self.assertEqual(normalize_download_name("clip (2).mp4"), "clip.mp4")
        self.assertEqual(normalize_download_name("take 2.mp4"), "take 2.mp4")

    def test_scan_writes_records_duplicate_reports_and_summary(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_dir:
            root = Path(source_dir)
            (root / "Ray.gif").write_bytes(b"same")
            (root / "Ray(1).gif").write_bytes(b"same")
            (root / "broken.mp4").write_bytes(b"video")
            (root / "notes.txt").write_text("skip", encoding="utf-8")

            probe = {"duration_seconds": 1.25, "video": {"width": 320, "height": 180, "fps": 24.0}, "format": "gif"}
            with patch("workspace.tools.vfx_library_index.scanner.probe", return_value=probe):
                summary = scan_library(root, Path(output_dir), "SRC-2026-VFXLIB-001")

            self.assertEqual(summary.supported_media_count, 3)
            self.assertEqual(summary.skipped_count, 1)
            self.assertEqual(summary.content_duplicate_group_count, 1)
            self.assertEqual(summary.normalized_name_duplicate_group_count, 1)
            records = [json.loads(line) for line in (Path(output_dir) / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["relative_path"] for record in records], ["Ray(1).gif", "Ray.gif", "broken.mp4"])
            self.assertTrue(all(record["source_id"] == "SRC-2026-VFXLIB-001" for record in records))
            self.assertEqual(records[0]["duration_seconds"], 1.25)
            duplicates = json.loads((Path(output_dir) / "duplicates.json").read_text(encoding="utf-8"))
            self.assertEqual(len(duplicates["content_hash_groups"]), 1)
            self.assertEqual(len(duplicates["normalized_name_groups"]), 1)

    def test_scan_skips_probe_when_requested(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_dir:
            root = Path(source_dir)
            (root / "a.gif").write_bytes(b"a")
            with patch("workspace.tools.vfx_library_index.scanner.probe") as mocked_probe:
                scan_library(root, Path(output_dir), "SRC-2026-VFXLIB-001", probe_media=False)
            mocked_probe.assert_not_called()
            record = json.loads((Path(output_dir) / "manifest.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(record["media_probe_status"], "skipped")

    def test_scan_is_idempotent_for_unchanged_files(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as output_dir:
            root = Path(source_dir)
            (root / "a.gif").write_bytes(b"a")
            with patch("workspace.tools.vfx_library_index.scanner.probe", return_value={}):
                first = scan_library(root, Path(output_dir), "SRC-2026-VFXLIB-001")
                first_manifest = (Path(output_dir) / "manifest.jsonl").read_text(encoding="utf-8")
                second = scan_library(root, Path(output_dir), "SRC-2026-VFXLIB-001")
                second_manifest = (Path(output_dir) / "manifest.jsonl").read_text(encoding="utf-8")
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first_manifest, second_manifest)


if __name__ == "__main__":
    unittest.main()
