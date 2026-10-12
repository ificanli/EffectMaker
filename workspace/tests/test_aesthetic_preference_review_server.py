from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.aesthetic_preference_review_batch import build_preference_review_batch
from workspace.tools.vfx_generation.aesthetic_preference_review_server import PreferenceReviewError, finalize_preferences, save_preference


class AestheticPreferenceReviewServerTests(unittest.TestCase):
    def _variant(self, root: Path, index: int) -> Path:
        run = root / f"run-{index}"
        candidate = run / "candidate"
        frames = candidate / "frames"
        frames.mkdir(parents=True)
        frame_rows = []
        for frame_index in range(2):
            frame = frames / f"frame-{frame_index}.png"
            frame.write_bytes(b"frame")
            frame_rows.append({"path": frame.name, "valid": True, "requested_time_seconds": frame_index / 10.0})
        result = candidate / "execution_result.json"
        result.write_text(json.dumps({"spec_path": str(run / "spec.json"), "prefab_path": "Assets/FX/fire.prefab", "valid_frame_count": 2, "frames": frame_rows}), encoding="utf-8")
        proposal = run / "proposal_manifest.json"
        proposal.write_text(json.dumps({
            "run_id": run.name,
            "proposal_id": f"proposal-{index}",
            "prompt_condition": {"prompt_id": "prompt-1", "text": "卡通火焰", "style_family": "cartoon", "effect_families": ["fire"]},
            "source_prefab": {"prefab_path": "Assets/FX/fire.prefab", "effect_family_hint": "fire"},
        }, ensure_ascii=False), encoding="utf-8")
        (run / "spec.json").write_text(json.dumps({"schema_version": "material_trajectory_spec.v1"}), encoding="utf-8")
        manifest = run / "variant_manifest.json"
        manifest.write_text(json.dumps({"proposal_manifest": str(proposal), "proposal_id": f"proposal-{index}", "execution_result_path": str(result), "technical_status": "pass"}), encoding="utf-8")
        return manifest

    def _batch(self, root: Path) -> Path:
        manifests = [self._variant(root, index) for index in range(4)]
        return build_preference_review_batch(manifests, root / "review", "server-review")["batch"]

    def test_save_preference_accepts_chosen_option_and_persists_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch_path = self._batch(root)
            batch_root = batch_path.parent
            pair_id = json.loads(batch_path.read_text(encoding="utf-8"))["pairs"][0]["pair_id"]
            saved = save_preference(batch_root, {"pair_id": pair_id, "preference": "a", "reason_codes": ["core_readability"], "human_note": "A的主体更清楚。"})
            store = json.loads((batch_root / "feedback_store.json").read_text(encoding="utf-8"))

        self.assertEqual(saved["preference"], "a")
        self.assertEqual(store["records"][pair_id]["human_note"], "A的主体更清楚。")

    def test_finalize_rejects_incomplete_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch_path = self._batch(root)
            pair_id = json.loads(batch_path.read_text(encoding="utf-8"))["pairs"][0]["pair_id"]
            save_preference(batch_path.parent, {"pair_id": pair_id, "preference": "tie", "reason_codes": [], "human_note": ""})
            with self.assertRaisesRegex(PreferenceReviewError, "incomplete"):
                finalize_preferences(batch_path.parent)

    def test_finalize_writes_canonical_records_and_excludes_ties(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch_path = self._batch(root)
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            for index, pair in enumerate(batch["pairs"]):
                save_preference(batch_path.parent, {
                    "pair_id": pair["pair_id"],
                    "preference": "a" if index == 0 else "tie",
                    "reason_codes": ["core_readability"] if index == 0 else [],
                    "human_note": "A更清楚。" if index == 0 else "差不多。",
                })
            outputs = finalize_preferences(batch_path.parent)
            records = [json.loads(line) for line in outputs["records"].read_text(encoding="utf-8").splitlines()]
            summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
            schema = json.loads(Path("workspace/data/vfx_generation/schemas/aesthetic_record.schema.json").read_text(encoding="utf-8"))

        for record in records:
            Draft202012Validator(schema).validate(record)
        self.assertEqual(len(records), 6)
        self.assertEqual(summary["trainable_preference_count"], 1)
        self.assertEqual(summary["excluded_tie_or_not_comparable_count"], 5)
        self.assertEqual(records[0]["training_eligibility"]["preference_training"], True)


if __name__ == "__main__":
    unittest.main()
