from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_active_learning import _recommended_rate, build_active_learning_batch


class PrefabActiveLearningTests(unittest.TestCase):
    def _record(self, sample_id: str, prefab_path: str, tier: str, *, node_count: int, status: str = "ready") -> dict:
        observations = {}
        evidence = {"capture_manifest_path": None}
        labels = {}
        provenance = {"confidence": None}
        if tier == "technical_corpus":
            observations = {
                "technical": {
                    "node_count": node_count,
                    "particle_system_count": node_count % 3,
                    "renderer_count": node_count % 2,
                    "material_count": node_count % 4,
                    "mesh_count": node_count % 5,
                    "reconstruction_status": "reconstructable",
                },
                "source_hints": {"effect_family_hint": f"family_{node_count}"},
            }
        elif tier == "visual_feature_only":
            observations = {
                "visual": {
                    "duration_seconds": 1.0 + node_count / 10.0,
                    "max_visible_area_ratio": 0.1 + node_count / 100.0,
                    "cropped_frame_count": 0,
                },
                "measured_color": {"semantic_tags": ["蓝色"]},
            }
            evidence["capture_manifest_path"] = f"captures/{sample_id}/capture_manifest.json"
        elif tier == "ai_pseudo_label":
            labels = {"observed_element_tags": ["火焰"]}
            provenance = {"confidence": 0.7}
        return {
            "sample_id": sample_id,
            "tier": tier,
            "status": status,
            "source": {"prefab_path": prefab_path},
            "observations": observations,
            "labels": labels,
            "label_provenance": provenance,
            "evidence": evidence,
            "grouping": {"cluster_id": None},
            "training": {"split": "regression" if tier == "regression_gold" else "train"},
        }

    def _dataset(self, root: Path) -> Path:
        dataset = root / "dataset"
        dataset.mkdir()
        rows = []
        paths = {
            "sample-a-old": "Assets/FX/A.prefab",
            "sample-a-new": "Assets/FX/A.prefab",
            "sample-b-human": "Assets/FX/B.prefab",
            "sample-c-regression": "Assets/FX/C.prefab",
            "sample-d": "Assets/FX/D.prefab",
        }
        for index, (sample_id, prefab_path) in enumerate(paths.items(), start=1):
            rows.append(self._record(sample_id, prefab_path, "technical_corpus", node_count=index * 10))
            rows.append(self._record(sample_id, prefab_path, "visual_feature_only", node_count=index * 10))
        rows.append(self._record("sample-a-new", paths["sample-a-new"], "ai_pseudo_label", node_count=20))
        rows.append(self._record("sample-b-human", paths["sample-b-human"], "human_gold", node_count=30))
        rows.append(self._record("sample-c-regression", paths["sample-c-regression"], "regression_gold", node_count=40))
        (dataset / "dataset_manifest.json").write_text(json.dumps({"dataset_id": "test_dataset"}), encoding="utf-8")
        (dataset / "records.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        return dataset

    def test_review_rate_adapts_to_recent_human_agreement(self) -> None:
        self.assertEqual(_recommended_rate(None), 0.06)
        self.assertEqual(_recommended_rate(0.79), 0.10)
        self.assertEqual(_recommended_rate(0.80), 0.05)
        self.assertEqual(_recommended_rate(0.90), 0.025)
        self.assertEqual(_recommended_rate(0.95), 0.01)

    def test_prefab_units_are_deduplicated_and_gold_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self._dataset(root)
            first = build_active_learning_batch(dataset, root / "first", "first", minimum_queue_size=16, cluster_count=4)
            second = build_active_learning_batch(dataset, root / "second", "second", minimum_queue_size=16, cluster_count=4)
            first_batch = json.loads(first["batch"].read_text(encoding="utf-8"))
            second_batch = json.loads(second["batch"].read_text(encoding="utf-8"))
            first_assignments = [json.loads(line) for line in first["assignments"].read_text(encoding="utf-8").splitlines()]
            second_assignments = [json.loads(line) for line in second["assignments"].read_text(encoding="utf-8").splitlines()]
            routed = [json.loads(line) for line in first["routed_records"].read_text(encoding="utf-8").splitlines()]

        queued_prefabs = [item["prefab_path"] for item in first_batch["items"]]
        self.assertEqual(first_batch["eligible_count"], 2)
        self.assertEqual(first_batch["quality_gates"]["duplicate_queue_prefabs"], 0)
        self.assertEqual(set(queued_prefabs), {"Assets/FX/A.prefab", "Assets/FX/D.prefab"})
        a_item = next(item for item in first_batch["items"] if item["prefab_path"] == "Assets/FX/A.prefab")
        self.assertEqual(a_item["ai_draft"]["labels"]["observed_element_tags"], ["火焰"])
        self.assertEqual(a_item["ai_draft"]["label_provenance"]["confidence"], 0.7)
        self.assertNotIn("Assets/FX/B.prefab", queued_prefabs)
        self.assertNotIn("Assets/FX/C.prefab", queued_prefabs)
        self.assertEqual(
            [(row["sample_id"], row["unit_key"], row["cluster_id"], row["split"]) for row in first_assignments],
            [(row["sample_id"], row["unit_key"], row["cluster_id"], row["split"]) for row in second_assignments],
        )
        a_clusters = {row["cluster_id"] for row in first_assignments if row["unit_key"] == "Assets/FX/A.prefab"}
        self.assertEqual(len(a_clusters), 1)
        regression_clusters = {row["cluster_id"] for row in first_assignments if row["unit_key"] == "Assets/FX/C.prefab"}
        self.assertTrue(regression_clusters)
        self.assertTrue(all(row["training"]["split"] == "regression" for row in routed if row["grouping"]["cluster_id"] in regression_clusters))
        cluster_splits = {}
        for row in routed:
            cluster_splits.setdefault(row["grouping"]["cluster_id"], set()).add(row["training"]["split"])
        self.assertTrue(all(len(splits) == 1 for splits in cluster_splits.values()))
        self.assertEqual(
            [(item["sample_id"], item["prefab_path"], item["cluster_id"], item["selection_reason"]) for item in first_batch["items"]],
            [(item["sample_id"], item["prefab_path"], item["cluster_id"], item["selection_reason"]) for item in second_batch["items"]],
        )


if __name__ == "__main__":
    unittest.main()
