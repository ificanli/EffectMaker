from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_core_ablation import create_core_ablation


class ProfessionalCoreAblationTests(unittest.TestCase):
    def test_ablation_only_changes_core_alpha_and_provenance(self) -> None:
        source = create_layered_explosion("x", 7, 0)
        original = copy.deepcopy(source)
        ablation, changed = create_core_ablation(source)

        roles = {node["node_id"]: node["role"] for node in ablation["nodes"]}
        core = next(row for row in ablation["components"]["particle_systems"] if roles[row["node_id"]] == "core")
        self.assertEqual(core["parameters"]["start_color_rgba"][3], 0.0)
        self.assertEqual(core["parameters"]["end_color_rgba"][3], 0.0)
        self.assertEqual(changed, ["core.parameters.start_color_rgba[3]", "core.parameters.end_color_rgba[3]"])
        self.assertEqual(source, original)
        self.assertNotEqual(ablation["graph_id"], source["graph_id"])


if __name__ == "__main__":
    unittest.main()
