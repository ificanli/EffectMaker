import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from workspace.tools.resource_index.metadata import (
    extract_metadata,
    read_image_metadata,
    sha256_file,
)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_image(self, name, mode):
        path = self.root / name
        image = Image.new(mode, (3, 2))
        image.save(path, format="PNG")
        image.close()
        return path

    def test_sha256_streams_and_matches_standard_digest(self):
        path = self.root / "payload.bin"
        content = b"vfx-data" * 257
        path.write_bytes(content)

        self.assertEqual(sha256_file(path, chunk_size=7), hashlib.sha256(content).hexdigest())

    def test_identical_content_files_have_identical_hashes(self):
        first = self.root / "first.bin"
        second = self.root / "second.bin"
        first.write_bytes(b"same bytes")
        second.write_bytes(b"same bytes")

        self.assertEqual(sha256_file(first), sha256_file(second))

    def test_reads_rgb_image_metadata(self):
        path = self._write_image("rgb.png", "RGB")

        self.assertEqual(
            read_image_metadata(path),
            {
                "width": 3,
                "height": 2,
                "mode": "RGB",
                "channels": 3,
                "frame_count": 1,
                "error": None,
            },
        )

    def test_reads_rgba_image_metadata(self):
        path = self._write_image("rgba.png", "RGBA")

        metadata = read_image_metadata(path)
        self.assertEqual(metadata["mode"], "RGBA")
        self.assertEqual(metadata["channels"], 4)
        self.assertEqual(metadata["frame_count"], 1)

    def test_corrupt_image_returns_error_record(self):
        path = self.root / "corrupt.png"
        path.write_bytes(b"not a png")

        metadata = read_image_metadata(path)
        self.assertIsNone(metadata["width"])
        self.assertIsNone(metadata["height"])
        self.assertIsNone(metadata["mode"])
        self.assertIsNone(metadata["channels"])
        self.assertIsNone(metadata["frame_count"])
        self.assertTrue(metadata["error"])

    def test_non_image_asset_has_empty_image_fields(self):
        path = self.root / "shader.shader"
        path.write_text("Shader {}", encoding="utf-8")

        self.assertEqual(
            extract_metadata(path, "shader"),
            {
                "sha256": sha256_file(path),
                "width": None,
                "height": None,
                "mode": None,
                "channels": None,
                "frame_count": None,
                "error": None,
            },
        )

    def test_extract_metadata_hashes_image_and_keeps_decode_error(self):
        path = self.root / "broken.png"
        path.write_bytes(b"broken")

        metadata = extract_metadata(path, "texture")
        self.assertEqual(metadata["sha256"], sha256_file(path))
        self.assertTrue(metadata["error"])


if __name__ == "__main__":
    unittest.main()
