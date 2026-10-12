from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_graph_source_reconstruction_report import finalize


ROOT = Path(__file__).parents[2]


class PrefabGraphSourceReconstructionReportTests(unittest.TestCase):
    def test_finalizes_clean_ten_sample_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            export = root / "export.json"
            recompile = root / "recompile"
            readback = root / "readback"
            recompile.mkdir()
            readback.mkdir()
            candidates = []
            for index in range(10):
                candidate_id = f"candidate_{index}"
                candidates.append({"candidate_id": candidate_id, "prefab_path": f"Assets/{candidate_id}.prefab", "graph_path": f"graphs/{candidate_id}.json"})
                (recompile / f"{candidate_id}.json").write_text(json.dumps({"status": "pass", "output_prefab_path": f"Assets/Generated/{candidate_id}/GeneratedRoot.prefab", "source_prefab_read": False}), encoding="utf-8")
                graph_path = root / "graphs" / f"{candidate_id}.json"
                graph_path.parent.mkdir(exist_ok=True)
                graph_path.write_text(json.dumps({"schema_version": "vfx_prefab_graph.v1", "graph_id": "pfg_" + f"{index:020d}", "source": {"source_kind": "generated", "prefab_path": "Assets/Generated.prefab", "source_example_id": None}, "root_node_id": "n0000", "nodes": [{"node_id": "n0000", "name": "GeneratedRoot", "sibling_index": 0, "depth": 0, "parent_node_id": "", "hierarchy_path": "GeneratedRoot[0]", "active_self": True, "component_types": ["UnityEngine.Transform"], "transform": {"local_position": [0, 0, 0], "local_rotation": [0, 0, 0, 1], "local_scale": [1, 1, 1]}}], "components": {"particle_systems": [], "renderers": [], "animations": []}, "asset_bindings": {"materials": [], "meshes": []}, "reconstruction": {"status": "structure_only", "compiler_profile": "none", "missing_fields": [], "unsupported_components": []}, "training": {"eligible_tasks": ["hierarchy_modeling"], "excluded_tasks": ["aesthetic_preference", "prompt_condition", "full_reconstruction"], "aesthetic_label_source": "none"}, "provenance": {"source_dataset_id": "test", "source_run_id": None, "exporter": "prefab_graph_readback.v1", "assumptions": ["test"]}}), encoding="utf-8")
                (readback / f"{candidate_id}.json").write_text(json.dumps({"status": "pass", "output_graph_path": graph_path.as_posix(), "source_prefab_instantiated": False, "node_count": 1, "particle_system_count": 0, "renderer_count": 0, "differences": [], "allowed_normalizations": []}), encoding="utf-8")
            export.write_text(json.dumps({"status": "pass", "candidate_count": 10, "candidates": candidates}), encoding="utf-8")
            output = finalize(export, recompile, readback, root / "report.json")
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["quality_gates"]["graph_schema_errors"], 0)
            self.assertTrue(report["quality_gates"]["all_differences_empty"])


if __name__ == "__main__":
    unittest.main()
