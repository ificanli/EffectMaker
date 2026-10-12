from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_slash_residual_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalSlashResidualRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_timing_and_late_visual_features(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 0.18, FEATURE_NAMES[-1]: 0.48}})
        self.assertTrue(any(name.startswith("residual.") for name in FEATURE_NAMES))
        self.assertTrue(any(name.startswith("visual.late") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.18)
        self.assertEqual(vector[-1], 0.48)


if __name__ == "__main__":
    unittest.main()
