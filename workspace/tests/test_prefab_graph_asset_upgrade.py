from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prefab_graph_asset_upgrade import TEMPLATE_PATH, _upgrade_graph
from workspace.tools.vfx_generation.prefab_graph_constrained import tokens_to_graph, valid_templates
from workspace.tools.vfx_generation.prefab_graph_model import build_vocabulary


ROOT = Path(__file__).parents[2]


class PrefabGraphAssetUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        examples = [json.loads(line) for line in (ROOT / "workspace/data/vfx_generation/datasets/prefab_graph_r001/examples.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.vocabulary = build_vocabulary(examples)

    def test_upgrade_makes_particle_graph_reconstructable_without_parent(self) -> None:
        tokens = valid_templates(self.vocabulary, "particle_v1")[0]
        source = tokens_to_graph(tokens, "particle_v1", "测试Prompt", "cartoon", 1)
        graph, plan = _upgrade_graph(source, "particle_v1", "测试Prompt", "explosion", "cartoon", 1, ROOT)
        self.assertEqual(graph["reconstruction"]["status"], "reconstructable")
        self.assertIsNone(graph["condition"]["parent_prefab_path"])
        self.assertEqual(graph["components"]["particle_systems"][0]["parameters"]["material_template_path"], TEMPLATE_PATH)
        self.assertEqual(plan["assets"][0]["shader_name"], "Common/ColorDefault")
        self.assertEqual(plan["assets"][0]["authorization_status"], "local_source_unconfirmed")
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_graph.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(graph)), [])

    def test_root_only_upgrade_has_no_fake_material(self) -> None:
        tokens = valid_templates(self.vocabulary, "root_only")[0]
        source = tokens_to_graph(tokens, "root_only", "测试Prompt", "cartoon", 1)
        _, plan = _upgrade_graph(source, "root_only", "测试Prompt", "explosion", "cartoon", 1, ROOT)
        self.assertEqual(plan["assets"], [])


if __name__ == "__main__":
    unittest.main()
