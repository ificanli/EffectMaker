from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.explosion_family_generator import create_layered_explosion
from workspace.tools.vfx_generation.professional_residual_teacher_reproduction import (
    _controlled_graph_comparison,
    _non_residual_end_seconds,
    _variant,
)


class ProfessionalResidualTeacherReproductionTests(unittest.TestCase):
    def test_only_residual_alpha_changes(self) -> None:
        source = create_layered_explosion("x", 7, 0)
        empty = _variant(source, "abrupt_no_residual")
        residual = _variant(source, "staged_residual")
        comparison = _controlled_graph_comparison(empty, residual)

        self.assertTrue(comparison["only_residual_alpha_differs"])
        self.assertEqual(comparison["difference_paths"], ["components.particle_systems[3].parameters.start_color_rgba[3]"])
        self.assertGreater(_non_residual_end_seconds(source), 0.5)


if __name__ == "__main__":
    unittest.main()
