from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_debris_ablation import create_debris_ablation


class ProfessionalDebrisAblationTests(unittest.TestCase):
    def test_ablation_only_removes_debris_start_alpha(self) -> None:
        source = create_layered_explosion("x", 7, 0)
        original = copy.deepcopy(source)
        ablation, changed = create_debris_ablation(source)
        roles = {node["node_id"]: node["role"] for node in ablation["nodes"]}
        debris = next(row for row in ablation["components"]["particle_systems"] if roles[row["node_id"]] == "hit")

        self.assertEqual(debris["parameters"]["start_color_rgba"][3], 0.0)
        self.assertEqual(changed, ["hit.parameters.start_color_rgba[3]"])
        self.assertEqual(source, original)
        self.assertNotEqual(ablation["graph_id"], source["graph_id"])


if __name__ == "__main__":
    unittest.main()
