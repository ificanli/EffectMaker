from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_graph_source_export import finalize_source_export


ROOT = Path(__file__).parents[2]


class PrefabGraphSourceExportManifestTests(unittest.TestCase):
    def test_finalizes_clean_export_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requests = []
            graph = {
                "schema_version": "vfx_prefab_graph.v1",
                "graph_id": "pfg_00000000000000000001",
                "source": {"source_kind": "unity_audit", "prefab_path": "Assets/Fx.prefab", "source_example_id": "fx"},
                "root_node_id": "n0000",
                "nodes": [{"node_id": "n0000", "name": "Fx", "sibling_index": 0, "depth": 0, "parent_node_id": "", "hierarchy_path": "Fx[0]", "active_self": True, "component_types": ["UnityEngine.Transform"], "transform": {"local_position": [0, 0, 0], "local_rotation": [0, 0, 0, 1], "local_scale": [1, 1, 1]}}],
                "components": {"particle_systems": [], "renderers": [], "animations": []},
                "asset_bindings": {"materials": [], "meshes": []},
                "reconstruction": {"status": "structure_only", "compiler_profile": "none", "missing_fields": [], "unsupported_components": []},
                "training": {"eligible_tasks": ["hierarchy_modeling"], "excluded_tasks": ["aesthetic_preference", "prompt_condition", "full_reconstruction"], "aesthetic_label_source": "none"},
                "provenance": {"source_dataset_id": "source", "source_run_id": None, "exporter": "prefab_graph_source_unity.v1", "assumptions": ["api"]},
            }
            for index in range(2):
                candidate = f"fx_{index}"
                graph_path = root / "graphs" / f"{candidate}.json"
                report_path = root / "reports" / f"{candidate}.json"
                graph_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.parent.mkdir(parents=True, exist_ok=True)
                graph["graph_id"] = f"pfg_{index:020d}"
                graph_path.write_text(json.dumps(graph), encoding="utf-8")
                report_path.write_text(json.dumps({"status": "pass", "reconstruction_status": "structure_only", "node_count": 1, "particle_system_count": 0, "renderer_count": 0, "material_paths": [], "mesh_paths": [], "missing_fields": [], "unsupported_components": []}), encoding="utf-8")
                requests.append({"candidate_id": candidate, "prefab_path": f"Assets/{candidate}.prefab", "graph_path": graph_path.as_posix(), "report_path": report_path.as_posix()})
            (root / "export_requests.json").write_text(json.dumps({"requests": requests}), encoding="utf-8")
            output = finalize_source_export(root, ROOT / "UnityDemo/EffectDemo", "source", root / "manifest.json")
            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["quality_gates"]["graph_schema_errors"], 0)
            self.assertEqual(manifest["quality_gates"]["aesthetic_labels_consumed"], 0)


if __name__ == "__main__":
    unittest.main()
