from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.feedback import (
    FeedbackValidationError,
    append_feedback,
    make_feedback_record,
    summarize_feedback_file,
    validate_feedback_file,
    validate_feedback_record,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class VfxFeedbackTests(unittest.TestCase):
    def _make_run(self, root: Path) -> Path:
        run_root = root / "run"
        _write_json(run_root / "run_manifest.json", {"run_id": "run-001"})
        for candidate_id in ("candidate-a", "candidate-b"):
            _write_json(
                run_root / "candidates" / candidate_id / "spec.json",
                {
                    "schema_version": "vfxspec.v1",
                    "generation": {"candidate_id": candidate_id},
                },
            )
        return run_root

    def test_make_append_and_validate_pairwise_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = self._make_run(Path(tmp))
            record = make_feedback_record(
                run_root,
                candidate_id="candidate-a",
                reviewer="human",
                decision="partial",
                summary="保留主体方向，继续收窄尖端",
                rank=1,
                common_scores={"readability": 4, "timing": 3},
                specialized_scores={"sharpness": 4},
                accepted_parts=["attack direction"],
                rejected_parts=["tip width"],
                reject_reasons=["尖端仍偏钝"],
                next_mutation=["increase taper"],
                mutation_allowed=True,
                pairwise={
                    "compared_candidate_id": "candidate-b",
                    "preference": "candidate",
                    "reason": "方向更明确",
                },
            )
            destination = append_feedback(run_root, record)
            result = validate_feedback_file(run_root)

            self.assertTrue(destination.exists())
            self.assertTrue(result["valid"])
            self.assertEqual(result["record_count"], 1)
            stored = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(stored["candidate_id"], "candidate-a")
            self.assertEqual(stored["trace"]["spec_path"], "candidates/candidate-a/spec.json")
            self.assertIsNone(stored["trace"]["seed"])

    def test_feedback_accepts_structured_style_assessment(self) -> None:
        profile = {
            "schema_version": "vfx_style_profile.v1",
            "family": "stylized",
            "keywords": ["high saturation"],
            "axes": {
                "realism": 0.2,
                "graphic_stylization": 0.8,
                "texture_detail": 0.4,
                "color_saturation": 0.9,
                "edge_definition": 0.7,
                "glow_exaggeration": 0.8,
                "motion_exaggeration": 0.6,
            },
            "scene_context": ["battle"],
            "source": "prompt",
            "confidence": 1.0,
        }
        observed = {**profile, "source": "render_human_review", "confidence": 0.8}
        with tempfile.TemporaryDirectory() as tmp:
            run_root = self._make_run(Path(tmp))
            record = make_feedback_record(
                run_root,
                candidate_id="candidate-a",
                reviewer="human",
                decision="partial",
                summary="风格接近但发光过强",
                target_style_profile=profile,
                observed_style_profile=observed,
                style_match_decision="partial",
                style_mismatch_dimensions=["glow_exaggeration"],
            )

        self.assertEqual(record["target_style_profile"]["family"], "stylized")
        self.assertEqual(record["style_match_decision"], "partial")

    def test_feedback_summary_aggregates_rank_and_pairwise_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = self._make_run(Path(tmp))
            first = make_feedback_record(
                run_root,
                candidate_id="candidate-a",
                reviewer="human",
                decision="accept_direction",
                summary="a",
                rank=1,
                pairwise={
                    "compared_candidate_id": "candidate-b",
                    "preference": "candidate",
                    "reason": "a wins",
                },
            )
            second = make_feedback_record(
                run_root,
                candidate_id="candidate-b",
                reviewer="human",
                decision="reject",
                summary="b",
                rank=2,
            )
            append_feedback(run_root, first)
            append_feedback(run_root, second)

            result = summarize_feedback_file(run_root)

            self.assertTrue(result["valid"])
            self.assertEqual(result["ranked_candidates"][0]["candidate_id"], "candidate-a")
            self.assertEqual(result["pairwise"]["candidate-a"]["wins"], 1)
            self.assertEqual(result["pairwise"]["candidate-b"]["losses"], 1)

    def test_unknown_candidate_and_invalid_score_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = self._make_run(Path(tmp))
            with self.assertRaises(FeedbackValidationError):
                make_feedback_record(
                    run_root,
                    candidate_id="missing",
                    reviewer="human",
                    decision="reject",
                    summary="不存在的候选",
                )
            record = {
                "schema_version": "human_feedback.v1",
                "run_id": "run-001",
                "candidate_id": "candidate-a",
                "reviewer": "human",
                "decision": "reject",
                "feedback": {"summary": "bad"},
                "specialized_scores": {"sharpness": 8},
            }
            errors = validate_feedback_record(record, expected_run_id="run-001", candidate_ids={"candidate-a"})
            self.assertTrue(any("0 to 5" in error for error in errors))

    def test_incomplete_trace_is_rejected(self) -> None:
        record = {
            "schema_version": "human_feedback.v1",
            "run_id": "run-001",
            "candidate_id": "candidate-a",
            "reviewer": "human",
            "decision": "partial",
            "feedback": {"summary": "trace test"},
            "trace": {},
        }

        errors = validate_feedback_record(record, expected_run_id="run-001", candidate_ids={"candidate-a"})

        self.assertTrue(any("missing trace.spec_path" in error for error in errors))

    def test_feedback_path_cannot_escape_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = self._make_run(Path(tmp))
            record = make_feedback_record(
                run_root,
                candidate_id="candidate-a",
                reviewer="human",
                decision="reject",
                summary="test",
            )
            with self.assertRaises(FeedbackValidationError):
                append_feedback(run_root, record, Path("..") / "outside.jsonl")

    def test_cli_create_and_validate(self) -> None:
        from workspace.tools.vfx_generation.feedback import main

        with tempfile.TemporaryDirectory() as tmp:
            run_root = self._make_run(Path(tmp))
            output = run_root / "draft.json"
            exit_code = main(
                [
                    "create",
                    "--run-root",
                    str(run_root),
                    "--candidate-id",
                    "candidate-a",
                    "--reviewer",
                    "human",
                    "--decision",
                    "reject",
                    "--summary",
                    "CLI record",
                    "--specialized-score",
                    "sharpness=2",
                    "--output",
                    str(output.relative_to(run_root)),
                    "--append",
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            self.assertTrue(validate_feedback_file(run_root)["valid"])


if __name__ == "__main__":
    unittest.main()
