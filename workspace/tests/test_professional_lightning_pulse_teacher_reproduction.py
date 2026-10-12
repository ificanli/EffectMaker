from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning
from workspace.tools.vfx_generation.professional_lightning_pulse_teacher_reproduction import _graph_comparison, _variant


class ProfessionalLightningPulseTeacherTests(unittest.TestCase):
    def test_variants_only_change_core_lifetime(self) -> None:
        source = create_layered_lightning("x", 7, 0)
        original = copy.deepcopy(source)
        slow = _variant(source, "slow_pulse")
        instant = _variant(source, "instant_pulse")
        comparison = _graph_comparison(slow, instant)
        self.assertTrue(comparison["only_core_lifetime_differs"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
