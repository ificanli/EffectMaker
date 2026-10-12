import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.tools.model_index.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_build_all_defaults_to_separate_full_output(self):
        args = build_parser().parse_args(["build-all"])
        self.assertEqual(args.output, Path("workspace/data/model_index/full"))
        self.assertIsNone(args.limit)
        self.assertGreater(args.timeout, 0)

    def test_build_all_forwards_options(self):
        with patch("workspace.tools.model_index.cli.build_all", return_value={}) as build:
            self.assertEqual(main(["build-all", "--root", "r", "--output", "o", "--limit", "2",
                                   "--timeout", "9", "--resume", "--json"]), 0)
        build.assert_called_once_with(Path("r"), Path("o"), None, "blender", True, 9, limit=2)

    def test_query_prints_filtered_jsonl(self):
        with tempfile.TemporaryDirectory() as temp:
            metadata = Path(temp) / "metadata.jsonl"
            metadata.write_text('{"asset_id":"a","format":"obj","tags":["prop"],"vertex_count":3,"triangle_count":1}\n', encoding="utf-8")
            with patch("builtins.print") as output:
                self.assertEqual(main(["query", "--metadata", str(metadata), "--type", "obj",
                                       "--tag", "prop", "--min-vertices", "2"]), 0)
        self.assertIn('"asset_id": "a"', output.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
