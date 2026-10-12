from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_lightning_hierarchy_rule_model import FEATURE_NAMES, feature_vector


class ProfessionalLightningHierarchyRuleModelTests(unittest.TestCase):
    def test_feature_vector_contains_main_branch_and_visual_features(self) -> None:
        vector = feature_vector({"features": {FEATURE_NAMES[0]: 1.5, FEATURE_NAMES[-1]: 0.2}})
        self.assertTrue(any(name.startswith("layer.main_branch") for name in FEATURE_NAMES))
        self.assertTrue(any(name.startswith("visual.") for name in FEATURE_NAMES))
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 1.5)
        self.assertEqual(vector[-1], 0.2)


if __name__ == "__main__":
    unittest.main()
