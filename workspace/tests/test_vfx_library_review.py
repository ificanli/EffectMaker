from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.tools.vfx_library_index.review import (
    build_ffmpeg_command,
    canonicalize_media,
    paginate,
    run_review,
)
from workspace.tools.vfx_library_index.queue import build_review_queue
from workspace.tools.vfx_library_index.triage import analyze_visual_package
from workspace.tools.vfx_library_index.visual_package import (
    build_visual_package,
    select_seed_records,
)


class VfxLibraryReviewTests(unittest.TestCase):
    def test_build_ffmpeg_command_uses_timestamp_and_single_video_frame(self) -> None:
        command = build_ffmpeg_command(
            Path("E:/library/fire.mp4"),
            Path("out/fire_start.png"),
            1.25,
        )
        self.assertIn("-ss", command)
        self.assertIn("1.25", command)
        self.assertIn("-frames:v", command)
        self.assertIn("1", command)
        self.assertEqual(command[-1], "out/fire_start.png")

    def test_run_review_reports_blocked_when_ffmpeg_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.jsonl"
            evidence = root / "evidence_manifest.jsonl"
            output = root / "review"
            manifest.write_text(
                json.dumps({
                    "media_id": "m1",
                    "relative_path": "fire.mp4",
                    "media_type": "video",
                    "sha256": "abc",
                }) + "\n",
                encoding="utf-8",
            )
            evidence.write_text(
                json.dumps({"relative_path": "fire.mp4", "label": "start", "second": 0.0}) + "\n",
                encoding="utf-8",
            )
            with patch("workspace.tools.vfx_library_index.review.which", return_value=None):
                report = run_review(root, manifest, evidence, output)
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["evidence_count"], 1)
            self.assertTrue((output / "review_report.json").exists())

    def test_run_review_counts_successful_evidence_with_injected_runner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.jsonl"
            evidence = root / "evidence_manifest.jsonl"
            output = root / "review"
            manifest.write_text(
                json.dumps({
                    "media_id": "m1",
                    "relative_path": "fire.mp4",
                    "media_type": "video",
                    "sha256": "abc",
                }) + "\n",
                encoding="utf-8",
            )
            evidence.write_text(
                "\n".join([
                    json.dumps({"relative_path": "fire.mp4", "label": "start", "second": 0.0}),
                    json.dumps({"relative_path": "fire.mp4", "label": "middle", "second": 0.5}),
                ]) + "\n",
                encoding="utf-8",
            )

            def runner(command: list[str]) -> int:
                Path(command[-1]).write_bytes(b"png")
                return 0

            with patch("workspace.tools.vfx_library_index.review.which", return_value="ffmpeg"):
                report = run_review(root, manifest, evidence, output, runner=runner)
            self.assertEqual(report["status"], "ready")
            self.assertEqual(report["successful_evidence_count"], 2)
            self.assertEqual(len(list((output / "frames").glob("*.png"))), 2)

    def test_select_seed_records_deduplicates_by_sha_and_limits_theme_samples(self) -> None:
        records = [
            {"relative_path": "a.gif", "sha256": "same", "media_type": "gif"},
            {"relative_path": "a(1).gif", "sha256": "same", "media_type": "gif"},
            {"relative_path": "b.gif", "sha256": "other", "media_type": "gif"},
            {"relative_path": "c.gif", "sha256": "third", "media_type": "gif"},
        ]
        assignments = [
            {"relative_path": "a.gif", "sha256": "same", "theme": "fire"},
            {"relative_path": "a(1).gif", "sha256": "same", "theme": "fire"},
            {"relative_path": "b.gif", "sha256": "other", "theme": "fire"},
            {"relative_path": "c.gif", "sha256": "third", "theme": "water"},
        ]
        selected = select_seed_records(records, assignments, themes=("fire",), per_theme=2)
        self.assertEqual([item["relative_path"] for item in selected], ["a.gif", "b.gif"])

    def test_visual_package_uses_five_timepoints_and_declares_reference_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.jsonl"
            assignments = root / "assignments.jsonl"
            output = root / "package"
            record = {
                "media_id": "m1",
                "relative_path": "fire.gif",
                "sha256": "abc",
                "media_type": "gif",
                "duration_seconds": 4.0,
            }
            manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
            assignments.write_text(json.dumps({"relative_path": "fire.gif", "sha256": "abc", "theme": "fire"}) + "\n", encoding="utf-8")
            report = build_visual_package(
                root,
                manifest,
                assignments,
                output,
                themes=("fire",),
                per_theme=1,
            )
            self.assertEqual(report["sample_count"], 1)
            self.assertEqual(report["evidence_point_count"], 5)
            self.assertTrue(report["reference_only"])
            self.assertIn("not an aesthetic quality standard", report["disclaimer"])
            self.assertTrue((output / "visual_package.json").exists())
    def test_triage_report_is_objective_and_counts_unavailable_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "visual_package.json"
            review = root / "review_report.json"
            output = root / "triage"
            package.write_text(json.dumps({
                "samples": [{
                    "relative_path": "fire.gif",
                    "sha256": "abc",
                    "theme_candidate": "fire",
                    "evidence": [
                        {"relative_path": "fire.gif", "label": "start"},
                    ],
                }],
            }), encoding="utf-8")
            review.write_text(json.dumps({
                "results": [{
                    "relative_path": "fire.gif",
                    "label": "start",
                    "status": "failed",
                }],
            }), encoding="utf-8")
            report = analyze_visual_package(package, review, output)
            self.assertEqual(report["status"], "triage-only")
            self.assertTrue(report["reference_only"])
            self.assertIn("quality", report["disclaimer"])
            self.assertEqual(report["unavailable_or_failed_frame_count"], 1)
            self.assertNotIn("score", json.dumps(report))
    def test_review_queue_prioritizes_missing_frames_without_quality_ranking(self) -> None:
        triage = {
            "samples": [
                {"relative_path": "fire.gif", "sha256": "f", "theme_candidate": "fire", "frame_count": 5, "luma_range": 12.0},
                {"relative_path": "water.gif", "sha256": "w", "theme_candidate": "water", "frame_count": 3, "luma_range": 1.0},
            ],
        }
        review = {
            "results": [
                {"relative_path": "fire.gif", "label": "end", "status": "failed"},
                {"relative_path": "water.gif", "label": "start", "status": "ok"},
            ],
        }
        queue = build_review_queue(triage, review)
        self.assertEqual(queue["status"], "review-queue")
        self.assertTrue(queue["reference_only"])
        self.assertEqual(queue["items"][0]["relative_path"], "fire.gif")
        self.assertNotIn("quality_score", json.dumps(queue))

if __name__ == "__main__":
    unittest.main()
