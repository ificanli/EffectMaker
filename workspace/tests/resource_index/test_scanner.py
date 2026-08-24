import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from workspace.tools.resource_index.models import ScanConfig
from workspace.tools.resource_index.scanner import scan_resources


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "resource"
        self.output = self.root / "workspace" / "data" / "resource_index"
        (self.source / "fire").mkdir(parents=True)
        Image.new("RGB", (8, 4), "red").save(self.source / "fire" / "spark.png")
        (self.source / "fire" / "duplicate.png").write_bytes(
            (self.source / "fire" / "spark.png").read_bytes()
        )
        (self.source / "mesh.fbx").write_bytes(b"model placeholder")
        (self.source / "notes.txt").write_text("source notes", encoding="utf-8")
        (self.source / "unsupported.bin").write_bytes(b"unsupported")
        (self.source / "broken.png").write_bytes(b"not an image")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _snapshot(self):
        return {
            path.relative_to(self.source).as_posix(): path.read_bytes()
            for path in sorted(self.source.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }

    def test_scan_is_incremental_read_only_and_writes_summary(self):
        before = self._snapshot()
        first = scan_resources(ScanConfig(root=self.source, output_dir=self.output))
        self.assertEqual(first["scanned"], 6)
        self.assertEqual(first["added"], 6)
        self.assertEqual(first["modified"], 0)
        self.assertEqual(first["unchanged"], 0)
        self.assertEqual(first["removed"], 0)
        self.assertGreaterEqual(first["errors"], 1)
        self.assertGreaterEqual(first["thumbnails_created"], 1)
        self.assertEqual(before, self._snapshot())
        self.assertTrue((self.output / "assets.sqlite3").is_file())
        self.assertTrue((self.output / "assets.jsonl").is_file())
        summary = json.loads((self.output / "scan_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["scanned"], 6)

        second = scan_resources(ScanConfig(root=self.source, output_dir=self.output))
        self.assertEqual(second["scanned"], 6)
        self.assertEqual(second["added"], 0)
        self.assertEqual(second["modified"], 0)
        self.assertEqual(second["unchanged"], 6)
        self.assertEqual(second["errors"], 0)

        (self.source / "new.png").write_bytes(b"new image bytes")
        (self.source / "notes.txt").write_text("changed notes", encoding="utf-8")
        (self.source / "mesh.fbx").unlink()
        third = scan_resources(ScanConfig(root=self.source, output_dir=self.output))
        self.assertEqual(third["added"], 1)
        self.assertEqual(third["modified"], 1)
        self.assertEqual(third["removed"], 1)
        self.assertEqual(third["unchanged"], 4)
        rows = {
            item["relative_path"]: item
            for item in map(
                json.loads,
                (self.output / "assets.jsonl").read_text(encoding="utf-8").splitlines(),
            )
        }
        self.assertEqual(rows["mesh.fbx"]["status"], "missing")
        self.assertTrue(
            all(row["status"] == "present" for path, row in rows.items() if path != "mesh.fbx")
        )

    def test_stat_failure_records_error_and_scan_continues_without_restat(self):
        failing_path = self.source / "notes.txt"
        original_stat = Path.stat
        stat_calls = 0

        def fail_notes_stat(path, *args, **kwargs):
            nonlocal stat_calls
            if path == failing_path:
                stat_calls += 1
                raise PermissionError("simulated stat denial")
            return original_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", autospec=True, side_effect=fail_notes_stat):
            result = scan_resources(ScanConfig(root=self.source, output_dir=self.output))

        self.assertEqual(stat_calls, 1)
        self.assertEqual(result["scanned"], 6)
        self.assertGreaterEqual(result["errors"], 2)
        rows = {
            item["relative_path"]: item
            for item in map(
                json.loads,
                (self.output / "assets.jsonl").read_text(encoding="utf-8").splitlines(),
            )
        }
        self.assertIn("PermissionError: simulated stat denial", rows["notes.txt"]["error"])
        self.assertIsNotNone(rows["fire/spark.png"]["sha256"])

    def test_ids_are_hashes_of_normalized_relative_paths_and_symlinks_are_skipped(self):
        try:
            (self.source / "linked.png").symlink_to(self.source / "fire" / "spark.png")
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlink creation unavailable: {error}")
        result = scan_resources(ScanConfig(root=self.source, output_dir=self.output))
        rows = [json.loads(line) for line in (self.output / "assets.jsonl").read_text(encoding="utf-8").splitlines()]
        row = next(item for item in rows if item["relative_path"] == "fire/spark.png")
        self.assertEqual(row["asset_id"], hashlib.sha256(b"fire/spark.png").hexdigest())
        self.assertNotIn("linked.png", {item["relative_path"] for item in rows})
        self.assertEqual(result["scanned"], 6)

    def test_rejects_output_inside_source(self):
        with self.assertRaises(ValueError):
            scan_resources(ScanConfig(root=self.source, output_dir=self.source / "generated"))


if __name__ == "__main__":
    unittest.main()
