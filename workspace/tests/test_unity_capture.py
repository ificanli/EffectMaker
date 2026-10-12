import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools import unity_capture


class UnityCaptureTests(unittest.TestCase):
    def test_build_manifest_records_relative_frames_and_validity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "frame_0000_t0000ms.png"
            second = root / "frame_0001_t0050ms.png"
            first.write_bytes(b"png-data")
            second.write_bytes(b"png-data-2")
            output = root / "capture_manifest.json"
            path = unity_capture.write_manifest(
                output,
                scene="SlashComparison",
                effect="OrangeSlash_Final",
                camera="Main Camera",
                resolution=(1280, 720),
                editor_status="playing",
                play_requested=True,
                frames=[
                    {"requested_time_seconds": 0.0, "path": first},
                    {"requested_time_seconds": 0.05, "path": second},
                ],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "unity-capture-manifest.v1")
        self.assertEqual(payload["capture_root"], root.as_posix())
        self.assertEqual(payload["frames"][0]["path"], "frame_0000_t0000ms.png")
        self.assertTrue(payload["frames"][0]["valid"])
        self.assertEqual(payload["frames"][1]["requested_time_seconds"], 0.05)

    def test_missing_frame_is_invalid_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = unity_capture.write_manifest(
                root / "capture_manifest.json",
                scene="SlashComparison",
                effect="OrangeSlash_Final",
                camera="Main Camera",
                resolution=(1280, 720),
                editor_status="playing",
                play_requested=True,
                frames=[{"requested_time_seconds": 0.2, "path": root / "missing.png"}],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(payload["frames"][0]["valid"])
        self.assertIn("missing", payload["frames"][0]["error"])

    def test_explicit_capture_root_validates_frames_outside_manifest_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture_root = root / "captures"
            capture_root.mkdir()
            frame = capture_root / "frame_0000.png"
            frame.write_bytes(b"png-data")
            output = root / "records" / "capture_manifest.json"
            path = unity_capture.write_manifest(
                output,
                root=capture_root,
                scene="BladeReproduction",
                effect="BladeRoot",
                camera="Main Camera",
                resolution=(1280, 720),
                editor_status="ready",
                play_requested=False,
                frames=[{"requested_time_seconds": 0.0, "path": "frame_0000.png"}],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(payload["frames"][0]["valid"])
        self.assertEqual(payload["frames"][0]["path"], "frame_0000.png")


if __name__ == "__main__":
    unittest.main()
