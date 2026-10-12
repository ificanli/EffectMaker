from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_slash_direction_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalSlashDirectionRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_direction_and_motion(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 0.2, FEATURE_NAMES[-1]: 0.8}})
        self.assertTrue(any(name.startswith("direction.") for name in FEATURE_NAMES))
        self.assertTrue(any(name.startswith("motion.") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.2)
        self.assertEqual(vector[-1], 0.8)


if __name__ == "__main__":
    unittest.main()
