from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.professional_core_rule_model import FEATURE_NAMES, _pair_splits, feature_vector


class ProfessionalCoreRuleModelTests(unittest.TestCase):
    def test_pair_splits_keep_every_pair_in_exactly_one_partition(self) -> None:
        pair_ids = [f"pair-{index}" for index in range(8)]
        splits = _pair_splits(pair_ids)

        self.assertEqual(set(splits), set(pair_ids))
        self.assertEqual(sum(value == "train" for value in splits.values()), 4)
        self.assertEqual(sum(value == "validation" for value in splits.values()), 2)
        self.assertEqual(sum(value == "test" for value in splits.values()), 2)

    def test_feature_vector_has_stable_order_and_zero_fills_missing_values(self) -> None:
        row = {"image_features": {FEATURE_NAMES[0]: 0.25, FEATURE_NAMES[-1]: 0.75}}
        vector = feature_vector(row)

        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(vector[0], 0.25)
        self.assertEqual(vector[-1], 0.75)
        self.assertEqual(sum(vector[1:-1]), 0.0)

    def test_too_few_pairs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least six"):
            _pair_splits(["a", "b", "c", "d", "e"])

    def test_feature_contract_is_core_local(self) -> None:
        self.assertTrue(FEATURE_NAMES)
        self.assertTrue(all(name.startswith("core.") for name in FEATURE_NAMES))


if __name__ == "__main__":
    unittest.main()
