from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prefab_graph_constrained import (
    PROFILES,
    _validate_graph,
    tokens_to_graph,
    valid_templates,
    validate_token_grammar,
)
from workspace.tools.vfx_generation.prefab_graph_model import build_vocabulary


ROOT = Path(__file__).parents[2]


class PrefabGraphConstrainedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        examples = [json.loads(line) for line in (ROOT / "workspace/data/vfx_generation/datasets/prefab_graph_r001/examples.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.vocabulary = build_vocabulary(examples)

    def test_all_profiles_produce_legal_token_sequences(self) -> None:
        for profile in PROFILES:
            templates = valid_templates(self.vocabulary, profile)
            self.assertGreaterEqual(len(templates), 1)
            for tokens in templates:
                events = validate_token_grammar(tokens, profile)
                self.assertEqual(len(events), len(tokens))
                graph = tokens_to_graph(tokens, profile, "测试Prompt", "cartoon", 1)
                _validate_graph(graph)
                self.assertIsNone(graph["condition"]["parent_prefab_path"])
                self.assertEqual(graph["training"]["aesthetic_label_source"], "ai_hypothesis")

    def test_illegal_token_is_rejected(self) -> None:
        tokens = valid_templates(self.vocabulary, "root_only")[0]
        tokens.insert(2, "COMP_NOT_ALLOWED")
        with self.assertRaisesRegex(ValueError, "grammar rejected"):
            validate_token_grammar(tokens, "root_only")

    def test_prefix_is_a_valid_template_prefix(self) -> None:
        template = valid_templates(self.vocabulary, "particle_v1")[0]
        prefix = template[:8]
        self.assertEqual(template[:len(prefix)], prefix)
        with self.assertRaisesRegex(ValueError, "grammar ended in incomplete state"):
            validate_token_grammar(prefix, "particle_v1")

    def test_decode_manifest_schema_is_strict(self) -> None:
        schema = json.loads((ROOT / "workspace/data/vfx_generation/schemas/prefab_graph_constrained_decode.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["status"]["const"], "pass")
        self.assertEqual(schema["properties"]["candidate_count"]["type"], "integer")
        self.assertIn("created_at", schema["required"])


if __name__ == "__main__":
    unittest.main()
