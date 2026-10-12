from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_explosion_rhythm_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalExplosionRhythmRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_timing_and_visual_evidence(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 0.2, FEATURE_NAMES[-1]: 0.8}})
        self.assertTrue(any(name.startswith("timing.") for name in FEATURE_NAMES))
        self.assertTrue(any(name.startswith("visual.") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.2)
        self.assertEqual(vector[-1], 0.8)


if __name__ == "__main__":
    unittest.main()
