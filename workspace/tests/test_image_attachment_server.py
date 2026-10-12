import base64
import tempfile
import unittest
from pathlib import Path

from workspace.tools.image_attachment_server import (
    ImageAttachmentError,
    build_image_content,
)


class ImageAttachmentTests(unittest.TestCase):
    def test_png_returns_mcp_image_content_with_reversible_bytes(self):
        payload = b"\x89PNG\r\n\x1a\nminimal-test-png"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame.png"
            path.write_bytes(payload)

            content = build_image_content(path)

        self.assertEqual(content["type"], "image")
        self.assertEqual(content["mimeType"], "image/png")
        self.assertEqual(base64.b64decode(content["data"]), payload)

    def test_jpeg_mime_type_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame.jpg"
            path.write_bytes(b"jpeg")
            content = build_image_content(path)

        self.assertEqual(content["mimeType"], "image/jpeg")

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ImageAttachmentError):
            build_image_content(Path("missing-frame.png"))

    def test_unsupported_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame.txt"
            path.write_text("not an image", encoding="utf-8")
            with self.assertRaises(ImageAttachmentError):
                build_image_content(path)


if __name__ == "__main__":
    unittest.main()
