from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning
from workspace.tools.vfx_generation.professional_lightning_hit_ablation import create_weak_hit_ablation


class ProfessionalLightningHitAblationTests(unittest.TestCase):
    def test_ablation_only_reduces_hit_alpha(self) -> None:
        source = create_layered_lightning("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_weak_hit_ablation(source)
        roles = {node["node_id"]: node["role"] for node in baseline["nodes"]}
        hit = next(row for row in baseline["components"]["particle_systems"] if roles[row["node_id"]] == "hit")
        self.assertEqual(hit["parameters"]["start_color_rgba"][3], 0.15)
        self.assertEqual(changed, ["hit.parameters.start_color_rgba[3]"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
