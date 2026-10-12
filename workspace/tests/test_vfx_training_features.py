from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from workspace.tools.vfx_training_features import build_feature_matrix


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class VfxTrainingFeatureTests(unittest.TestCase):
    def test_builds_feature_matrix_from_spec_and_rendered_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_root = root / "run"
            candidates = []
            for index, candidate_id in enumerate(("candidate-a", "candidate-b"), start=1):
                candidate_dir = run_root / "candidates" / candidate_id
                capture_dir = candidate_dir / "captures"
                capture_dir.mkdir(parents=True)
                frames = []
                for frame_index, time_value in enumerate((0.1, 0.5, 0.9)):
                    image = np.zeros((72, 128, 3), dtype=np.uint8)
                    cv2.line(
                        image,
                        (15, 55 - frame_index * 5),
                        (45 + index * 20 + frame_index * 10, 20),
                        (40 * index, 100, 220),
                        3 + index,
                    )
                    frame_name = f"frame_{frame_index}.png"
                    cv2.imwrite(str(capture_dir / frame_name), image)
                    frames.append(
                        {
                            "requested_time_seconds": time_value,
                            "capture_time_seconds": time_value,
                            "path": frame_name,
                            "valid": True,
                            "error": None,
                        }
                    )
                _write_json(
                    candidate_dir / "spec.json",
                    {
                        "schema_version": "vfxspec.v1",
                        "effect_family": "slash",
                        "effect_type": "slash_arc",
                        "generation": {"generator": "test", "generator_version": "1"},
                        "adapter": {
                            "topology": {"arc_topology": "single_sweep", "asymmetry": 0.4 + index * 0.1},
                            "shape": {"arc_length": 4.0 + index, "control_points": [[0, 0, 0], [1, 0, 1]]},
                        },
                        "layers": [{"role": "core_blade", "status": "active", "timing_parameters": {"peak_time": 0.5}}],
                    },
                )
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "spec_path": f"candidates/{candidate_id}/spec.json",
                        "capture_root": f"candidates/{candidate_id}/captures",
                        "frames": frames,
                        "auto_eval": {
                            "status": "pass",
                            "hard_reject_reasons": [],
                            "metrics": {"visible_area_ratio_peak": 0.08 * index, "frame_delta_mean": 0.01},
                        },
                    }
                )
            _write_json(run_root / "run_manifest.json", {"run_id": "test-run", "candidates": candidates})

            paths = build_feature_matrix(run_root, root / "features")

            rows = [json.loads(line) for line in paths["feature_jsonl"].read_text(encoding="utf-8").splitlines()]
            frame = pd.read_csv(paths["feature_csv"])
            schema = json.loads(paths["feature_schema"].read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(frame.shape[0], 2)
            self.assertGreater(schema["feature_count"], 20)
            self.assertIn("image.edge_density.mean", rows[0]["features"])
            self.assertIn("spec.adapter.topology.arc_topology", rows[0]["features"])
            self.assertEqual(schema["label_status"], "unlabeled_feature_matrix")

    def test_reads_frames_from_a_non_ascii_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "中文运行"
            run_root = root / "run"
            capture_dir = run_root / "candidates" / "candidate" / "captures"
            capture_dir.mkdir(parents=True)
            frame_path = capture_dir / "frame.png"
            image = np.zeros((32, 32, 3), dtype=np.uint8)
            cv2.rectangle(image, (8, 8), (24, 24), (20, 80, 180), -1)
            encoded = cv2.imencode(".png", image)[1]
            encoded.tofile(str(frame_path))
            _write_json(run_root / "candidates" / "candidate" / "spec.json", {
                "schema_version": "vfxspec.v1", "effect_family": "fire", "effect_type": "fire",
                "generation": {"generator": "test", "generator_version": "1"},
                "layers": [{"role": "core", "status": "active"}],
            })
            _write_json(run_root / "run_manifest.json", {
                "run_id": "unicode-run",
                "candidates": [{
                    "candidate_id": "candidate", "spec_path": "candidates/candidate/spec.json",
                    "capture_root": "candidates/candidate/captures",
                    "frames": [{"requested_time_seconds": 0.0, "path": "frame.png", "valid": True}],
                }],
            })
            paths = build_feature_matrix(run_root, root / "features")
            rows = [json.loads(line) for line in paths["feature_jsonl"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["features"]["image.visible_ratio.mean"], 0.0)


if __name__ == "__main__":
    unittest.main()
