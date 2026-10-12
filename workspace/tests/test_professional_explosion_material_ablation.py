from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.explosion_family_generator import CORE_TEXTURE, create_layered_explosion
from workspace.tools.vfx_generation.professional_explosion_material_ablation import create_flat_texture_ablation


class ProfessionalExplosionMaterialAblationTests(unittest.TestCase):
    def test_ablation_only_replaces_core_texture(self) -> None:
        source = create_layered_explosion("x", 7, 0, "structured_flame")
        original = copy.deepcopy(source)
        flat, changed = create_flat_texture_ablation(source)
        roles = {node["node_id"]: node["role"] for node in flat["nodes"]}
        core = next(row for row in flat["components"]["particle_systems"] if roles[row["node_id"]] == "core")
        self.assertEqual(core["parameters"]["texture_asset_path"], CORE_TEXTURE)
        self.assertEqual(changed, ["core.parameters.texture_asset_path"])
        self.assertEqual(source, original)
        self.assertNotEqual(flat["graph_id"], source["graph_id"])


if __name__ == "__main__":
    unittest.main()
