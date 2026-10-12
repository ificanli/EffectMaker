from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_direction_teacher_reproduction import _graph_comparison, _variant
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashDirectionTeacherTests(unittest.TestCase):
    def test_variants_only_change_trail_rotation(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        depth = _variant(source, "depth_misaligned")
        aligned = _variant(source, "attack_aligned")
        comparison = _graph_comparison(depth, aligned)
        self.assertTrue(comparison["only_trail_rotation_differs"])
        self.assertFalse(next(node for node in depth["nodes"] if node.get("role") == "hit")["active_self"])
        self.assertFalse(next(node for node in aligned["nodes"] if node.get("role") == "hit")["active_self"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
