from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_slash_rhythm_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalSlashRhythmRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_delay_gaps_and_visual_timing(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 0.01, FEATURE_NAMES[-1]: 0.48}})
        self.assertTrue(any(name.startswith("timing.") for name in FEATURE_NAMES))
        self.assertTrue(any(name.startswith("visual.") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.01)
        self.assertEqual(vector[-1], 0.48)


if __name__ == "__main__":
    unittest.main()
