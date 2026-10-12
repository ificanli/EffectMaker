from __future__ import annotations

import unittest

import torch

from workspace.tools.vfx_generation.prefab_graph_multitask_model import (
    AE_BOS_TOKEN,
    AE_EOS_TOKEN,
    MASK_TOKEN,
    PrefabGraphMultiTaskModel,
    _encode_examples,
    _masked_component_rows,
    build_multitask_vocabulary,
)


def example(identifier: str, group: str) -> dict:
    return {
        "example_id": identifier,
        "split_group": {"prefab_group": group},
        "tokens": ["<PREFAB>", "RECON_STRUCTURE_ONLY", "<NODE>", "COMP_TRANSFORM", "COMP_PARTICLESYSTEM", "</NODE>", "</PREFAB>"],
        "eligible_tasks": ["hierarchy_modeling", "component_prediction"],
    }


class PrefabGraphMultitaskModelTests(unittest.TestCase):
    def test_vocabulary_contains_explicit_task_tokens(self) -> None:
        vocabulary = build_multitask_vocabulary([example("one", "one")])
        self.assertIn(MASK_TOKEN, vocabulary)
        self.assertIn(AE_BOS_TOKEN, vocabulary)
        self.assertIn(AE_EOS_TOKEN, vocabulary)

    def test_shared_encoder_heads_have_expected_shapes(self) -> None:
        rows = [example("one", "one")]
        vocabulary = build_multitask_vocabulary(rows)
        encoded = _encode_examples(rows, vocabulary)
        masked = _masked_component_rows(encoded)
        model = PrefabGraphMultiTaskModel(len(vocabulary), 8, 12, vocabulary["<PAD>"])
        sequence = torch.tensor([encoded[0][1]], dtype=torch.long)
        lengths = torch.tensor([len(encoded[0][1])], dtype=torch.long)
        next_logits = model.next_token(sequence[:, :-1], lengths - 1)
        masked_logits = model.masked_component(sequence, torch.tensor([masked[0][1]], dtype=torch.long))
        decoder_inputs = torch.tensor([[vocabulary[AE_BOS_TOKEN], *encoded[0][1]]], dtype=torch.long)
        reconstruction_logits = model.reconstruct(sequence, lengths, decoder_inputs)
        self.assertEqual(tuple(next_logits.shape), (1, len(encoded[0][1]) - 1, len(vocabulary)))
        self.assertEqual(tuple(masked_logits.shape), (1, len(vocabulary)))
        self.assertEqual(tuple(reconstruction_logits.shape), (1, len(encoded[0][1]) + 1, len(vocabulary)))

    def test_component_mask_rows_cover_component_tokens(self) -> None:
        vocabulary = build_multitask_vocabulary([example("one", "one")])
        encoded = _encode_examples([example("one", "one")], vocabulary)
        masked = _masked_component_rows(encoded)
        self.assertEqual([row[2] for row in masked], ["COMP_TRANSFORM", "COMP_PARTICLESYSTEM"])


if __name__ == "__main__":
    unittest.main()
