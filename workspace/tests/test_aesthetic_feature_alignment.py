from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.aesthetic_feature_alignment import build_feature_alignment


class AestheticFeatureAlignmentTests(unittest.TestCase):
    def _record(self, root: Path, record_id: str, candidate_id: str, render_candidate_id: str | None, frames: list[str], run_id: str = "run-1") -> dict:
        return {
            "record_id": record_id,
            "record_kind": "human_label",
            "scope": {"effect_family": "fire", "style_family": "cartoon", "candidate_ids": [candidate_id]},
            "provenance": {
                "run_id": run_id,
                "render_candidate_id": render_candidate_id,
                "frame_paths": frames,
                "source_path": "workspace/data/reviews/feedback.jsonl",
            },
            "training_eligibility": {"aesthetic_judge": True},
        }

    def _write_jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_existing_feature_matches_runtime_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = self._write_jsonl(root / "records.jsonl", [self._record(root, "record-1", "trains_fx_001", "source_prefab_001", [])])
            features = self._write_jsonl(root / "features.jsonl", [{"run_id": "run-1", "candidate_id": "source_prefab_001", "features": {"image.edge_density.mean": 0.4}}])
            paths = build_feature_alignment(records, [features], root / "alignment", "alias_alignment")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["features"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["aligned_count"], 1)
        self.assertEqual(manifest["existing_feature_match_count"], 1)
        self.assertEqual(rows[0]["candidate_id"], "trains_fx_001")
        self.assertEqual(rows[0]["feature_source"], "existing_run_feature_matrix")

    def test_direct_record_frames_fill_missing_existing_feature(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames = []
            for index in range(2):
                image = np.zeros((32, 32, 3), dtype=np.uint8)
                cv2.rectangle(image, (8, 8), (24, 24), (30, 120, 220), -1)
                path = root / f"frame-{index}.png"
                cv2.imencode(".png", image)[1].tofile(str(path))
                frames.append(str(path))
            records = self._write_jsonl(root / "records.jsonl", [self._record(root, "record-1", "candidate-1", None, frames)])
            paths = build_feature_alignment(records, [], root / "alignment", "direct_alignment")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["features"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["direct_image_feature_count"], 1)
        self.assertEqual(rows[0]["feature_source"], "direct_record_frames")
        self.assertGreater(rows[0]["features"]["image.visible_ratio.mean"], 0.0)

    def test_missing_record_frame_is_explicitly_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = self._write_jsonl(root / "records.jsonl", [self._record(root, "record-1", "candidate-1", None, [str(root / "missing.png")])])
            paths = build_feature_alignment(records, [], root / "alignment", "missing_alignment")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            exclusions = [json.loads(line) for line in paths["exclusions"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["aligned_count"], 0)
        self.assertEqual(manifest["excluded_count"], 1)
        self.assertEqual(exclusions[0]["reason"], "missing_or_unreadable_frame_features")

    def test_real_r005_labels_align_to_prefab_and_composition_features(self) -> None:
        records = Path("workspace/data/vfx_generation/datasets/aesthetic_records_r005/aesthetic_judge_records.jsonl")
        features = Path("workspace/data/vfx_generation/datasets/features/trains_prefab_playmode_r005_audit_r3_short_window_r001/candidate_features.jsonl")
        self.assertTrue(records.is_file(), "real standardized labels are required")
        self.assertTrue(features.is_file(), "real prefab features are required")
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_feature_alignment(records, [features], Path(temporary) / "alignment", "real_r005_alignment")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in paths["features"].read_text(encoding="utf-8").splitlines()]
            schema = json.loads(Path("workspace/data/vfx_generation/schemas/aesthetic_feature_alignment.schema.json").read_text(encoding="utf-8"))

        Draft202012Validator(schema).validate(manifest)
        self.assertEqual(manifest["judge_candidate_count"], 47)
        self.assertEqual(manifest["aligned_count"], 47)
        self.assertEqual(manifest["excluded_count"], 0)
        self.assertEqual(manifest["existing_feature_match_count"], 41)
        self.assertEqual(manifest["direct_image_feature_count"], 6)
        self.assertEqual(len(rows), 47)


if __name__ == "__main__":
    unittest.main()
