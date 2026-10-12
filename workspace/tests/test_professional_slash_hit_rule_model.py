from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_slash_hit_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalSlashHitRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_hit_and_visual_contact_features(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 0.2, FEATURE_NAMES[-1]: 4.0}})
        self.assertTrue(any(name.startswith("hit.") for name in FEATURE_NAMES))
        self.assertTrue(any(name.startswith("visual.contact") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.2)
        self.assertEqual(vector[-1], 4.0)


if __name__ == "__main__":
    unittest.main()
