from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from workspace.tools.vfx_generation.professional_residual_rule_model import CAPTURE_PROTOCOL, FEATURE_NAMES, feature_vector, merge_datasets, prepare_evaluation_capture


class ProfessionalResidualRuleModelTests(unittest.TestCase):
    def test_feature_vector_has_stable_order(self) -> None:
        row = {"image_features": {FEATURE_NAMES[0]: 0.2, FEATURE_NAMES[-1]: 0.8}}
        vector = feature_vector(row)

        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.2)
        self.assertEqual(vector[-1], 0.8)
        self.assertEqual(sum(vector[1:-1]), 0.0)

    def test_feature_contract_excludes_global_image_features(self) -> None:
        self.assertTrue(FEATURE_NAMES)
        self.assertTrue(all(name.startswith("late.") for name in FEATURE_NAMES))

    def test_evaluation_capture_uses_residual_sampling_protocol(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            compile_path = root / "compile.json"
            source_path = root / "generation.json"
            compile_path.write_text(json.dumps({"status": "pass", "output_prefab_path": "Assets/X.prefab"}), encoding="utf-8")
            source_path.write_text(json.dumps({"run_id": "r001", "effect_family": "explosion", "candidates": [{"candidate_id": "x", "compile_result_path": compile_path.as_posix(), "capture_manifest_path": "old.json"}]}), encoding="utf-8")
            paths = prepare_evaluation_capture(source_path, root / "evaluation")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            requests = json.loads(paths["runtime_request"].read_text(encoding="utf-8"))
        self.assertEqual(manifest["capture_protocol"], CAPTURE_PROTOCOL)
        self.assertEqual(requests["width"], 512)
        self.assertEqual(requests["sampling"]["max_interval_seconds"], 0.05)

    def test_merge_reassigns_pair_splits_without_leakage(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            sources = []
            for batch in range(2):
                source = root / f"source_{batch}"
                source.mkdir()
                rows = []
                for pair_index in range(4):
                    pair_id = f"batch_{batch}_pair_{pair_index}"
                    for label in (0, 1):
                        rows.append({"record_id": f"{pair_id}_{label}", "pair_id": pair_id, "split": "train", "label": label})
                (source / "records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                (source / "dataset_manifest.json").write_text(json.dumps({"status": "pass", "dataset_id": f"source_{batch}", "teacher_rule_id": "residual", "target_scope": {"effect_family": "explosion", "judgment_axis": "residual_persistence"}, "feature_names": list(FEATURE_NAMES), "pair_count": 4, "files": {"records": "records.jsonl"}}), encoding="utf-8")
                sources.append(source)
            paths = merge_datasets(sources, root / "merged", "merged")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["records"].read_text(encoding="utf-8").splitlines()]
        self.assertEqual(manifest["pair_count"], 8)
        self.assertEqual(manifest["record_count"], 16)
        self.assertEqual(manifest["pair_split_overlap_count"], 0)
        self.assertEqual({row["split"] for row in rows}, {"train", "validation", "test"})


if __name__ == "__main__":
    unittest.main()
