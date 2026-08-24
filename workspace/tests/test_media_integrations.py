import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from workspace.tools import document_import, media, scene_detect


class SceneDetectTests(unittest.TestCase):
    def test_normalize_scene_rows_has_traceable_boundaries(self):
        rows = scene_detect.normalize_scene_rows(
            [(0, 48), (48, 120)], fps=24.0, detector="content"
        )

        self.assertEqual(rows[0]["start_frame"], 0)
        self.assertEqual(rows[0]["start_seconds"], 0.0)
        self.assertEqual(rows[0]["end_seconds"], 2.0)
        self.assertEqual(rows[1]["detector"], "content")

    def test_write_scene_outputs_creates_json_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = scene_detect.write_scene_outputs(
                [{"start_frame": 0, "end_frame": 10, "start_seconds": 0.0, "end_seconds": 1.0, "detector": "content"}],
                Path(tmp) / "scenes",
            )
            self.assertTrue(outputs["json"].exists())
            self.assertTrue(outputs["csv"].exists())
            self.assertEqual(json.loads(outputs["json"].read_text())[0]["end_frame"], 10)

    def test_detect_scenes_finds_boundary_in_two_part_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "cuts.mp4"
            subprocess.run([
                str(media.resolve_tools().ffmpeg), "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=3",
                "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=3",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)
            ], check=True)
            outputs = scene_detect.detect_scenes(video, root / "scenes", threshold=10)
            rows = json.loads(outputs["json"].read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(rows), 2)
            self.assertAlmostEqual(rows[1]["start_seconds"], 3.0, places=1)


class DocumentImportTests(unittest.TestCase):
    def test_import_markdown_writes_to_inbox_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "lesson.md"
            source.write_text("# Lesson\n\nBody", encoding="utf-8")
            output = document_import.import_document(source, Path(tmp) / "knowledge")

            self.assertEqual(output.parent.name, "inbox")
            self.assertEqual(output.name, "lesson.md")
            self.assertIn("Body", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
