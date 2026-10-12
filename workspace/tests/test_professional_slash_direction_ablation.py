from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_direction_ablation import create_depth_ablation
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashDirectionAblationTests(unittest.TestCase):
    def test_ablation_only_rotates_direction_trail_to_depth(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_depth_ablation(source)
        trail = next(node for node in baseline["nodes"] if node["role"] == "residual")
        self.assertEqual(trail["transform"]["local_rotation"], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(changed, ["residual.transform.local_rotation"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
