from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path("workspace/data/vfx_generation/schemas/aesthetic_record.schema.json")


def _base_record(kind: str, payload: dict, *, visibility: str = "visible") -> dict:
    return {
        "schema_version": "vfx_aesthetic_record.v1",
        "record_id": f"record-{kind}",
        "record_kind": kind,
        "provenance": {
            "source_kind": "human_feedback",
            "source_path": "workspace/data/reviews/feedback.jsonl",
            "source_record_id": "source-001",
            "source_sha256": None,
            "run_id": "run-001",
            "run_manifest_path": "workspace/data/runs/run_manifest.json",
            "spec_path": "workspace/data/spec.json",
            "timecodes": ["00:00-00:10"],
            "frame_paths": ["workspace/data/runs/frame_000.png"],
            "parent_record_ids": [],
        },
        "scope": {
            "effect_family": "fire",
            "style_family": "cartoon",
            "style_keywords": ["高饱和"],
            "prompt_id": "prompt-001",
            "candidate_ids": ["candidate-001"],
            "scene_context": ["battle"],
        },
        "evidence": {
            "visibility_status": visibility,
            "evidence_status": "verified",
            "technical_status": "pass",
            "independent_visual_evidence": True,
            "continuous_frame_evidence": True,
            "visual_review_channel": "native_image",
            "evidence_notes": "真实连续帧已确认。",
        },
        "payload": payload,
        "training_eligibility": {
            "aesthetic_judge": False,
            "preference_training": False,
            "controller_sft": False,
            "positive_generation_supervision": False,
            "excluded_reasons": [],
        },
    }


class AestheticRecordSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)

    def assert_valid(self, record: dict) -> None:
        errors = sorted(self.validator.iter_errors(record), key=lambda error: list(error.path))
        self.assertFalse(errors, errors[0].message if errors else "unexpected schema error")

    def test_reference_record_is_evidence_not_training_label(self) -> None:
        record = _base_record(
            "reference",
            {"reference_role": "style_reference", "description": "高饱和卡通火焰参考。", "human_confirmed": False},
        )
        self.assert_valid(record)
        self.assertFalse(record["training_eligibility"]["aesthetic_judge"])

    def test_observation_record_keeps_rule_as_unconfirmed_candidate(self) -> None:
        record = _base_record(
            "observation",
            {
                "observation": "主体轮廓在峰值前已经建立。",
                "rule_candidate": "主体先成立，命中层后出现。",
                "axes": ["core_readability", "rhythm"],
                "polarity": "positive_example",
                "confidence": "medium",
                "requires_unity_validation": True,
            },
        )
        self.assert_valid(record)

    def test_human_label_contains_quality_style_and_layer_contract(self) -> None:
        record = _base_record(
            "human_label",
            {
                "reviewer": "human",
                "reviewed_at": "2026-09-01T12:00:00Z",
                "decision": "accept_reference",
                "quality_score": 4,
                "scores": {"core_readability": 4, "layer_separation": 3, "rhythm": 4, "material": 3, "composition": 4},
                "style_match_decision": "match",
                "layer_roles": {"core": "清楚", "support": "有效", "hit": "有效", "residual": "一般"},
                "reusable_layers": ["主体", "命中"],
                "issues": ["材质普通"],
                "summary": "可作为参考",
                "notes": "峰值集中，主体可读。",
                "confirmation_mode": "human_corrected_ai_draft",
            },
        )
        self.assert_valid(record)

    def test_technical_exclusion_can_record_non_visual_failure(self) -> None:
        record = _base_record(
            "technical_exclusion",
            {"exclusion_category": "context", "exclusion_code": "runtime_context_required", "reason": "独立镜头无法呈现主体。"},
            visibility="not_visible",
        )
        record["evidence"]["independent_visual_evidence"] = False
        record["evidence"]["continuous_frame_evidence"] = False
        record["training_eligibility"]["excluded_reasons"] = ["no_independent_visual_evidence"]
        self.assert_valid(record)

    def test_preference_training_requires_visible_continuous_evidence(self) -> None:
        record = _base_record(
            "preference_pair",
            {
                "candidate_a": "run-001/candidate-a",
                "candidate_b": "run-001/candidate-b",
                "preference": "a",
                "comparable": True,
                "reason_codes": ["core_readability", "rhythm"],
                "human_note": "A的主体更清楚，峰值更集中。",
            },
        )
        record["scope"]["candidate_ids"] = ["run-001/candidate-a", "run-001/candidate-b"]
        record["training_eligibility"]["preference_training"] = True
        self.assert_valid(record)

    def test_judge_eligibility_rejects_not_visible_human_label(self) -> None:
        record = _base_record(
            "human_label",
            {
                "reviewer": "human",
                "reviewed_at": "2026-09-01T12:00:00Z",
                "decision": "not_visible",
                "quality_score": 1,
                "scores": {"core_readability": 0, "layer_separation": 0, "rhythm": 0, "material": 0, "composition": 0},
                "style_match_decision": "unlabeled",
                "layer_roles": {"core": "没有", "support": "没有", "hit": "没有", "residual": "没有"},
                "reusable_layers": [],
                "issues": ["无法判断"],
                "summary": "无法判断",
                "notes": "没有独立画面。",
                "confirmation_mode": "human_accepted_ai_draft",
            },
            visibility="not_visible",
        )
        record["evidence"]["independent_visual_evidence"] = False
        record["evidence"]["continuous_frame_evidence"] = False
        record["training_eligibility"]["aesthetic_judge"] = True
        with self.assertRaises(AssertionError):
            self.assert_valid(record)

    def test_preference_training_rejects_tie_or_non_comparable_record(self) -> None:
        record = _base_record(
            "preference_pair",
            {
                "candidate_a": "run-001/candidate-a",
                "candidate_b": "run-001/candidate-b",
                "preference": "tie",
                "comparable": False,
                "reason_codes": ["similar_quality"],
                "human_note": "两者无法区分。",
            },
        )
        record["scope"]["candidate_ids"] = ["run-001/candidate-a", "run-001/candidate-b"]
        record["training_eligibility"]["preference_training"] = True
        with self.assertRaises(AssertionError):
            self.assert_valid(record)


if __name__ == "__main__":
    unittest.main()
