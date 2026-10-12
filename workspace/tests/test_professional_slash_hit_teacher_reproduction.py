from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.professional_slash_hit_teacher_reproduction import CONTACT_POSITION, _graph_comparison, _variant
from workspace.tools.vfx_generation.slash_family_generator import create_layered_slash


class ProfessionalSlashHitTeacherTests(unittest.TestCase):
    def test_variants_only_change_hit_position(self) -> None:
        source = create_layered_slash("x", 7, 0)
        original = copy.deepcopy(source)
        center = _variant(source, "center_misplaced")
        aligned = _variant(source, "contact_aligned")
        comparison = _graph_comparison(center, aligned)
        self.assertTrue(comparison["only_hit_position_differs"])
        self.assertEqual(next(node for node in center["nodes"] if node.get("role") == "hit")["transform"]["local_position"], [0.0, 0.0, 0.0])
        self.assertEqual(next(node for node in aligned["nodes"] if node.get("role") == "hit")["transform"]["local_position"], CONTACT_POSITION)
        self.assertFalse(next(node for node in center["nodes"] if node.get("role") == "residual")["active_self"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
