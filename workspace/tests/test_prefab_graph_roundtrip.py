from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_graph_roundtrip import validate_roundtrip_batch


ROOT = Path(__file__).parents[2]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


class PrefabGraphRoundtripTests(unittest.TestCase):
    def test_passes_ten_clean_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(1, 11):
                sample_id = f"{index:02d}"
                graph = {
                    "schema_version": "vfx_prefab_graph.v1",
                    "graph_id": f"pfg_{index:020d}",
                    "source": {"source_kind": "generated", "prefab_path": "Assets/Generated.prefab", "source_example_id": None},
                    "root_node_id": "n0000",
                    "nodes": [{"node_id": "n0000", "name": "Root", "sibling_index": 0, "depth": 0, "parent_node_id": "", "hierarchy_path": "Root[0]", "active_self": True, "component_types": ["UnityEngine.Transform"], "transform": {"local_position": [0, 0, 0], "local_rotation": [0, 0, 0, 1], "local_scale": [1, 1, 1]}}],
                    "components": {"particle_systems": [], "renderers": [], "animations": []},
                    "asset_bindings": {"materials": [], "meshes": []},
                    "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []},
                    "training": {"eligible_tasks": ["full_reconstruction"], "excluded_tasks": ["aesthetic_preference", "prompt_condition"], "aesthetic_label_source": "ai_hypothesis"},
                    "provenance": {"source_dataset_id": "generated_seed", "source_run_id": None, "exporter": "prefab_graph_readback.v1", "assumptions": ["readback"]},
                }
                write_json(root / "roundtrip_graphs_final" / f"graph_{sample_id}.json", graph)
                write_json(root / "roundtrip_results_final" / f"result_{sample_id}.json", {"status": "pass", "unity_api_readback": True, "source_prefab_instantiated": False, "differences": [], "allowed_normalizations": []})
            output = validate_roundtrip_batch(root, ROOT / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json", root / "manifest.json")
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["sample_count"], 10)
            self.assertEqual(report["schema_error_count"], 0)


if __name__ == "__main__":
    unittest.main()
