import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.tools import media


class MediaToolTests(unittest.TestCase):
    def test_resolve_tools_prefers_environment_variables(self):
        with patch.dict(
            os.environ,
            {"VFX_FFMPEG": r"D:\tools\ffmpeg.exe", "VFX_FFPROBE": r"D:\tools\ffprobe.exe"},
            clear=False,
        ):
            tools = media.resolve_tools()

        self.assertEqual(tools.ffmpeg, Path(r"D:\tools\ffmpeg.exe"))
        self.assertEqual(tools.ffprobe, Path(r"D:\tools\ffprobe.exe"))

    def test_build_probe_command_returns_json_metadata_request(self):
        command = media.build_probe_command(Path("clip.mp4"))

        self.assertEqual(command[0], "ffprobe")
        self.assertIn("-show_format", command)
        self.assertIn("-show_streams", command)
        self.assertEqual(command[-1], "clip.mp4")

    def test_validate_interval_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            media.validate_interval(10, 10)
        with self.assertRaises(ValueError):
            media.validate_interval(20, 10)
        with self.assertRaises(ValueError):
            media.validate_interval(-1, 2)

    def test_metadata_json_is_stable_and_includes_video_stream(self):
        payload = {
            "format": {"duration": "12.5", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            "streams": [{"codec_type": "video", "width": 1280, "height": 720, "r_frame_rate": "30/1"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "media_meta.json"
            result = media.normalize_metadata(payload, Path("clip.mp4"), output)
            saved = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["duration_seconds"], 12.5)
        self.assertEqual(result["video"]["width"], 1280)
        self.assertEqual(saved["video"]["fps"], 30.0)


if __name__ == "__main__":
    unittest.main()
