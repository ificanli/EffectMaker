from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_hit_ablation import create_center_ablation
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashHitAblationTests(unittest.TestCase):
    def test_ablation_only_moves_hit_to_center(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_center_ablation(source)
        hit = next(node for node in baseline["nodes"] if node["role"] == "hit")
        self.assertEqual(hit["transform"]["local_position"], [0.0, 0.0, 0.0])
        self.assertEqual(changed, ["hit.transform.local_position"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
