from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
import json

from workspace.tools.vfx_generation.professional_lightning_pulse_rule_model import FEATURE_NAMES, feature_vector, prepare_evaluation_graphs
from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning


class ProfessionalLightningPulseRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_lifetime_and_visibility(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 0.14, FEATURE_NAMES[-1]: 0.12}})
        self.assertEqual(FEATURE_NAMES[0], "pulse.core_lifetime")
        self.assertTrue(any(name.startswith("visual.") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.14)
        self.assertEqual(vector[-1], 0.12)

    def test_evaluation_graph_disables_non_core_layers(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            graph_path = root / "source.json"
            compile_path = root / "compile.json"
            manifest_path = root / "manifest.json"
            graph = create_layered_lightning("x", 7, 0)
            graph_path.write_text(json.dumps(graph), encoding="utf-8")
            compile_path.write_text(json.dumps({"status": "pass", "output_prefab_path": "Assets/Source.prefab"}), encoding="utf-8")
            manifest_path.write_text(json.dumps({"run_id": "r", "candidates": [{"candidate_id": "c", "graph_id": graph["graph_id"], "graph_path": graph_path.as_posix(), "compile_result_path": compile_path.as_posix()}]}), encoding="utf-8")
            paths = prepare_evaluation_graphs(manifest_path, root / "evaluation", "Assets/Generated/Test")
            result = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            isolated = json.loads(Path(result["candidates"][0]["graph_path"]).read_text(encoding="utf-8"))
            roles = {node["role"]: node for node in isolated["nodes"]}
            self.assertTrue(roles["core"]["active_self"])
            for role in ("support", "hit", "residual"):
                self.assertFalse(roles[role]["active_self"])


if __name__ == "__main__":
    unittest.main()
