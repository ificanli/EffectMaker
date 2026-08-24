import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from workspace.tools.resource_index.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "resource"
        self.output = self.root / "index"
        (self.source / "slash").mkdir(parents=True)
        Image.new("RGB", (20, 10), "red").save(self.source / "slash" / "spark.png")
        (self.source / "slash" / "copy.png").write_bytes(
            (self.source / "slash" / "spark.png").read_bytes()
        )
        (self.source / "mesh.fbx").write_bytes(b"model")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([*args])
        return code, output.getvalue()

    def test_scan_json_reports_summary_and_no_thumbnails_option(self):
        code, text = self.run_cli(
            "scan", "--root", str(self.source), "--output", str(self.output),
            "--json", "--no-thumbnails"
        )
        payload = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(payload["scanned"], 3)
        self.assertEqual(payload["added"], 3)
        self.assertEqual(list((self.output / "thumbnails").glob("**/*")), [])

    def test_stats_json_reads_existing_index(self):
        self.run_cli("scan", "--root", str(self.source), "--output", str(self.output))
        code, text = self.run_cli("stats", "--output", str(self.output), "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text), {"missing": 0, "present": 3, "total": 3})

    def test_query_json_applies_filters_and_limit(self):
        self.run_cli("scan", "--root", str(self.source), "--output", str(self.output))
        code, text = self.run_cli(
            "query", "--output", str(self.output), "--json", "--type", "texture",
            "--tag", "slash", "--min-width", "10", "--min-height", "5", "--limit", "1"
        )
        self.assertEqual(code, 0)
        rows = json.loads(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["relative_path"], "slash/copy.png")

    def test_duplicates_json_lists_hash_group(self):
        self.run_cli("scan", "--root", str(self.source), "--output", str(self.output))
        code, text = self.run_cli(
            "duplicates", "--output", str(self.output), "--json", "--limit", "1"
        )
        self.assertEqual(code, 0)
        self.assertEqual(code, 0)
        groups = json.loads(text)
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["paths"], ["slash/copy.png", "slash/spark.png"])

    def test_force_hash_is_passed_to_scan_configuration(self):
        with patch("workspace.tools.resource_index.cli.scan_resources", return_value={}) as scan:
            self.run_cli(
                "scan", "--root", str(self.source), "--output", str(self.output),
                "--force-hash"
            )
        config = scan.call_args.args[0]
        self.assertTrue(config.force_hash)


if __name__ == "__main__":
    unittest.main()
