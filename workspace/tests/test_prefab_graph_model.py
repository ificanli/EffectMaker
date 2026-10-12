from __future__ import annotations

import unittest

import torch

from workspace.tools.vfx_generation.prefab_graph_model import (
    PAD_TOKEN,
    PrefabGraphNextTokenModel,
    build_vocabulary,
    encode_examples,
    split_by_prefab_group,
)


def example(identifier: str, group: str, tokens: list[str]) -> dict:
    return {"example_id": identifier, "tokens": tokens, "split_group": {"prefab_group": group}}


class PrefabGraphModelTests(unittest.TestCase):
    def test_prefab_groups_are_disjoint(self) -> None:
        rows = [example(f"item-{index}", f"group-{index}", ["<PREFAB>", "COMP_TRANSFORM", "</PREFAB>"]) for index in range(100)]
        splits = split_by_prefab_group(rows)
        groups = {name: {row["split_group"]["prefab_group"] for row in values} for name, values in splits.items()}
        self.assertFalse(groups["train"] & groups["validation"])
        self.assertFalse(groups["train"] & groups["test"])
        self.assertFalse(groups["validation"] & groups["test"])

    def test_encoding_and_model_shape(self) -> None:
        rows = [example("item", "group", ["<PREFAB>", "COMP_TRANSFORM", "</PREFAB>"])]
        vocabulary = build_vocabulary(rows)
        encoded = encode_examples(rows, vocabulary)
        self.assertEqual(encoded[0][1][0], vocabulary["<PREFAB>"])
        model = PrefabGraphNextTokenModel(len(vocabulary), 8, 12, vocabulary[PAD_TOKEN])
        logits = model(torch.tensor([[encoded[0][1][0], encoded[0][1][1]]], dtype=torch.long))
        self.assertEqual(tuple(logits.shape), (1, 2, len(vocabulary)))

    def test_vocabulary_is_train_only(self) -> None:
        vocabulary = build_vocabulary([example("train", "group", ["<PREFAB>", "TRAIN_ONLY", "</PREFAB>"])])
        self.assertIn("TRAIN_ONLY", vocabulary)
        self.assertNotIn("TEST_ONLY", vocabulary)


if __name__ == "__main__":
    unittest.main()
