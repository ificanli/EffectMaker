import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_web_player_server import (
    DEFAULT_BUILD_ROOT,
    VfxWebRequestHandler,
    build_parser,
    resolve_build_root,
)


class VfxWebPlayerServerTests(unittest.TestCase):
    def test_resolve_build_root_requires_unity_index(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with self.assertRaises(FileNotFoundError):
                resolve_build_root(root)
            (root / "index.html").write_text("ok", encoding="utf-8")
            self.assertEqual(root.resolve(), resolve_build_root(root))

    def test_server_uses_webassembly_mime_type(self):
        self.assertEqual(
            "application/wasm", VfxWebRequestHandler.extensions_map[".wasm"]
        )

    def test_cli_defaults_to_loopback(self):
        args = build_parser().parse_args([])
        self.assertEqual("127.0.0.1", args.host)
        self.assertEqual(8770, args.port)
        self.assertIn("VfxTrainingPlayer2022", DEFAULT_BUILD_ROOT.as_posix())


if __name__ == "__main__":
    unittest.main()
