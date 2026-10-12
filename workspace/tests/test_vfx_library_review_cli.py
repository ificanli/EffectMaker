from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.tools.vfx_library_index import review_cli


class ReviewCliTests(unittest.TestCase):
    def test_parser_defaults_page_size_to_64(self) -> None:
        parser = review_cli.build_parser()
        args = parser.parse_args([
            "--source-root", "source",
            "--manifest", "manifest.jsonl",
            "--evidence-manifest", "evidence.jsonl",
            "--output", "review",
        ])
        self.assertEqual(args.page_size, 64)

    def test_main_passes_page_size_and_returns_partial_success(self) -> None:
        captured: dict = {}

        def fake_run(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return {"status": "partial", "overview_pages": []}

        with patch.object(review_cli, "run_review", side_effect=fake_run):
            result = review_cli.main([
                "--source-root", "source",
                "--manifest", "manifest.jsonl",
                "--evidence-manifest", "evidence.jsonl",
                "--output", "review",
                "--page-size", "3",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(captured["kwargs"]["page_size"], 3)

    def test_main_rejects_non_positive_page_size(self) -> None:
        with self.assertRaises(SystemExit):
            review_cli.main([
                "--source-root", "source",
                "--manifest", "manifest.jsonl",
                "--evidence-manifest", "evidence.jsonl",
                "--output", "review",
                "--page-size", "0",
            ])


if __name__ == "__main__":
    unittest.main()
