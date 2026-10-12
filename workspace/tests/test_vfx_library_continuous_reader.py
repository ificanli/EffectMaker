from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_library_index.continuous_reader import (
    build_frame_plan,
    extract_evidence_frames,
)


class ContinuousReaderTests(unittest.TestCase):
    def test_build_frame_plan_has_five_deterministic_labels(self) -> None:
        plan = build_frame_plan(2.0, ("start", "quarter", "middle", "three-quarter", "end"))
        self.assertEqual([label for label, _ in plan], ["start", "quarter", "middle", "three-quarter", "end"])
        self.assertEqual(plan[0][1], 0.0)
        self.assertEqual(plan[2][1], 1.0)

    def test_extract_evidence_frames_records_failed_frame_without_losing_other_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = {"relative_path": "fire.gif", "sha256": "abc", "duration_seconds": 2.0}
            calls: list[list[str]] = []

            def runner(command: list[str]) -> int:
                calls.append(command)
                if len(calls) < 5:
                    Path(command[-1]).write_bytes(b"png")
                    return 0
                return 1

            result = extract_evidence_frames(root, sample, root / "frames", runner=runner)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(len(result["frames"]), 5)
            self.assertEqual(result["frames"][4]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
