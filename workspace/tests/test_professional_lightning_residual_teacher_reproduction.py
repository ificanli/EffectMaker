from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning
from workspace.tools.vfx_generation.professional_lightning_residual_teacher_reproduction import _controlled_graph_comparison, _variant


class ProfessionalLightningResidualTeacherTests(unittest.TestCase):
    def test_variants_only_change_residual_alpha(self) -> None:
        source = create_layered_lightning("x", 7, 0)
        original = copy.deepcopy(source)
        empty = _variant(source, "abrupt_no_residual")
        residual = _variant(source, "staged_residual")
        comparison = _controlled_graph_comparison(empty, residual)
        self.assertTrue(comparison["only_residual_alpha_differs"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
