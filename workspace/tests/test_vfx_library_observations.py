from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_library_index.observations import (
    append_observation,
    validate_observation,
)


class ObservationTests(unittest.TestCase):
    def test_observation_requires_queue_bound_evidence(self) -> None:
        queue = {"items": [{"relative_path": "fire.gif", "sha256": "abc"}]}
        payload = {"relative_path": "other.gif", "sha256": "abc", "label": "middle"}
        with self.assertRaises(ValueError):
            validate_observation(payload, queue)

    def test_append_observation_preserves_reference_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = {"items": [{"relative_path": "fire.gif", "sha256": "abc"}]}
            payload = {"relative_path": "fire.gif", "sha256": "abc", "label": "middle", "theme_status": "pending", "confidence": "low"}
            result = append_observation(Path(directory) / "observations.jsonl", payload, queue)
            self.assertTrue(result["reference_only"])

    def test_observation_rejects_score_fields(self) -> None:
        queue = {"items": [{"relative_path": "fire.gif", "sha256": "abc"}]}
        with self.assertRaises(ValueError):
            validate_observation({"relative_path": "fire.gif", "sha256": "abc", "label": "middle", "quality_score": 1}, queue)


if __name__ == "__main__":
    unittest.main()
