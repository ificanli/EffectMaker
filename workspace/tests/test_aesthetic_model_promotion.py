from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.aesthetic_model_promotion import build_promotion_report


class AestheticModelPromotionTests(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return path

    def _dataset(self, root: Path, *, leakage: bool = False) -> Path:
        judge_rows = []
        for index, (family, style) in enumerate((("fire", "cartoon"), ("explosion", "realistic"), ("fire", "cartoon"), ("explosion", "realistic"))):
            judge_rows.append({"record_id": f"judge-{index}", "candidate_id": f"candidate-{index}", "effect_family": family, "style_family": style, "group_id": f"group-{index}", "features": {"x": index}, "label": {"quality_score": index + 1, "scores": {"core_readability": index, "layer_separation": index, "rhythm": index, "material": index, "composition": index}}})
        preference_rows = [{"record_id": "pair-1", "candidate_a": "candidate-0", "candidate_b": "candidate-1", "preference": "a", "features_a": {"x": 1}, "features_b": {"x": 0}, "split": "train", "group_id": "group-pair", "effect_family": "fire", "style_family": "cartoon", "provenance": {"run_id": "run-pair"}}]
        assignments = [{"record_id": row["record_id"], "group_id": row["group_id"], "split": "train"} for row in judge_rows]
        if leakage:
            assignments.append({"record_id": "leak", "group_id": "group-0", "split": "test"})
        self._write_jsonl(root / "records.jsonl", judge_rows)
        self._write_jsonl(root / "judge.jsonl", judge_rows)
        self._write_jsonl(root / "preference.jsonl", preference_rows)
        self._write_jsonl(root / "assignments.jsonl", assignments)
        manifest = root / "dataset.json"
        manifest.write_text(json.dumps({
            "files": {"records": "records.jsonl", "judge_training": "judge.jsonl", "preference_training": "preference.jsonl", "split_assignments": "assignments.jsonl"},
        }), encoding="utf-8")
        return manifest

    def test_real_dataset_is_blocked_without_models_or_training_rows(self) -> None:
        dataset = Path("workspace/data/vfx_generation/datasets/aesthetic_training_r003/aesthetic_training_dataset_manifest.json")
        self.assertTrue(dataset.is_file(), "real aesthetic training manifest is required")
        with tempfile.TemporaryDirectory() as temporary:
            report_path = build_promotion_report(dataset, Path(temporary) / "promotion.json")
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["promotion"]["decision"], "blocked")
        self.assertIn("no_judge_training_rows", report["promotion"]["reasons"])
        self.assertIn("judge_model_absent", report["promotion"]["reasons"])
        self.assertEqual(report["leakage_audit"]["status"], "pass")

    def test_coverage_is_reported_separately_from_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._dataset(Path(temporary))
            report_path = build_promotion_report(manifest, Path(temporary) / "promotion.json")
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["data_coverage"]["judge_training_count"], 4)
        self.assertEqual(report["data_coverage"]["effect_family_counts"], {"explosion": 2, "fire": 2})
        self.assertEqual(report["data_coverage"]["style_family_counts"], {"cartoon": 2, "realistic": 2})
        self.assertIn("judge_model_absent", report["promotion"]["reasons"])

    def test_split_leakage_blocks_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._dataset(Path(temporary), leakage=True)
            report_path = build_promotion_report(manifest, Path(temporary) / "promotion.json")
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["leakage_audit"]["status"], "fail")
        self.assertEqual(report["leakage_audit"]["multi_split_group_count"], 1)
        self.assertIn("split_leakage_detected", report["promotion"]["reasons"])

    def test_report_matches_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._dataset(Path(temporary))
            report_path = build_promotion_report(manifest, Path(temporary) / "promotion.json")
            report = json.loads(report_path.read_text(encoding="utf-8"))
        schema = json.loads(Path("workspace/data/vfx_generation/schemas/vfx_aesthetic_promotion_report.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)


if __name__ == "__main__":
    unittest.main()
