from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_layer_ablation import create_equal_layer_ablation
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashLayerAblationTests(unittest.TestCase):
    def test_ablation_only_equalizes_inner_size_and_alpha(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_equal_layer_ablation(source)
        roles = {node["node_id"]: node["role"] for node in baseline["nodes"]}
        layers = {roles[row["node_id"]]: row["parameters"] for row in baseline["components"]["particle_systems"]}
        self.assertEqual(layers["core"]["start_size_max"], layers["support"]["start_size_max"])
        self.assertEqual(layers["core"]["start_color_rgba"][3], layers["support"]["start_color_rgba"][3])
        self.assertEqual(len(changed), 2)
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
