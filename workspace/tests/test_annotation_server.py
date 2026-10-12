import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools import annotation_server


class AnnotationServerTests(unittest.TestCase):
    def test_load_annotations_defaults_to_timeline_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "timeline.json").write_text(json.dumps({"frames": [{"id": "ref_0000", "source_time_seconds": 0.0, "image": "frames/a.jpg", "phase": "unreviewed", "observations": {}}]}), encoding="utf-8")
            data = annotation_server.load_annotations(root)

        self.assertEqual(data["schema"], "teaching-annotation.v1")
        self.assertEqual(data["frames"][0]["status"], "unreviewed")
        self.assertEqual(data["frames"][0]["image"], "frames/a.jpg")

    def test_save_annotations_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"schema": "teaching-annotation.v1", "frames": [{"id": "ref_0000", "status": "human_confirmed"}]}
            path = annotation_server.save_annotations(root, payload)
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved["frames"][0]["status"], "human_confirmed")


if __name__ == "__main__":
    unittest.main()
