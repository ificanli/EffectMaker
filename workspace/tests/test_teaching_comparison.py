import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools import teaching_comparison


class TeachingComparisonTests(unittest.TestCase):
    def test_build_timeline_writes_dense_frame_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            timeline_path = teaching_comparison.build_timeline(
                source_id="SRC-TEST",
                case_id="slash-demo",
                video=Path("lesson.mp4"),
                start=12.0,
                end=12.3,
                step=0.1,
                frame_paths=[output / "frame_0000.jpg", output / "frame_0001.jpg", output / "frame_0002.jpg", output / "frame_0003.jpg"],
                output=output / "timeline.json",
            )
            payload = json.loads(timeline_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["source_id"], "SRC-TEST")
        self.assertEqual(payload["case_id"], "slash-demo")
        self.assertEqual(payload["sample_interval_seconds"], 0.1)
        self.assertEqual([row["source_time_seconds"] for row in payload["frames"]], [12.0, 12.1, 12.2, 12.3])
        self.assertEqual(payload["frames"][0]["image"], "frame_0000.jpg")

    def test_build_timeline_rejects_mismatched_frame_count(self):
        with self.assertRaises(ValueError):
            teaching_comparison.build_timeline(
                source_id="SRC-TEST",
                case_id="slash-demo",
                video=Path("lesson.mp4"),
                start=1.0,
                end=1.2,
                step=0.1,
                frame_paths=[Path("frame_0000.jpg")],
                output=Path("timeline.json"),
            )


if __name__ == "__main__":
    unittest.main()
