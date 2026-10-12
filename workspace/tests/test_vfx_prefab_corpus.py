from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.vfx_prefab_corpus import build_corpus


class VfxPrefabCorpusTests(unittest.TestCase):
    def test_builds_deduplicated_leakage_aware_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            manifest = {
                "schema_version": "source_manifest.v1",
                "source_id": "TEST_SOURCE",
                "license": {"status": "local_reference_only"},
                "unity_context": {"original_project_path": "E:/Source/Unity"},
                "files": [
                    {"role": "prefab", "path": "Assets/FX/A.prefab", "unity_guid": "guid-a", "sha256": "sha-a"},
                    {"role": "prefab", "path": "Assets/FX/B.prefab", "unity_guid": "guid-b", "sha256": "sha-b"},
                    {"role": "material", "path": "Assets/FX/A.mat", "unity_guid": "mat-a", "sha256": "mat-a"},
                    {"role": "texture", "path": "Assets/FX/A.png", "unity_guid": "tex-a", "sha256": "tex-a"},
                ],
            }
            (source / "source_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "corpus"
            paths = build_corpus([source], output, "test_corpus")
            payload = json.loads(paths["corpus_manifest"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in paths["records"].read_text(encoding="utf-8").splitlines()]
            schema = json.loads(Path("workspace/data/vfx_generation/schemas/vfx_prefab_corpus.schema.json").read_text(encoding="utf-8"))

        Draft202012Validator(schema).validate(payload)
        self.assertEqual(payload["prefab_count"], 2)
        self.assertEqual(payload["source_count"], 1)
        self.assertEqual(payload["delta"]["new_count"], 2)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(row["local_training_allowed"] for row in records))
        self.assertTrue(all(not row["training_eligibility"]["positive_generation_supervision"] for row in records))
        self.assertEqual(payload["quality_gates"]["duplicate_source_keys"], 0)

    def test_duplicate_source_keys_are_removed_from_training_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = []
            for name in ("one", "two"):
                source = root / name
                source.mkdir()
                (source / "source_manifest.json").write_text(json.dumps({
                    "source_id": "SAME_SOURCE",
                    "license": {"status": "local_reference_only"},
                    "files": [{"role": "prefab", "path": "Assets/Same.prefab", "sha256": "same"}],
                }), encoding="utf-8")
                inputs.append(source)
            paths = build_corpus(inputs, root / "corpus", "duplicate_test")
            manifest = json.loads(paths["corpus_manifest"].read_text(encoding="utf-8"))
            failures = [json.loads(line) for line in paths["failures"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(manifest["prefab_count"], 1)
        self.assertEqual(manifest["quality_gates"]["duplicate_source_keys"], 1)
        self.assertTrue(any(row["reason"] == "duplicate_source_key" for row in failures))

    def test_same_content_from_different_sources_shares_split_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = []
            for name, source_id in (("one", "SOURCE_ONE"), ("two", "SOURCE_TWO")):
                source = root / name
                source.mkdir()
                (source / "source_manifest.json").write_text(json.dumps({
                    "source_id": source_id,
                    "license": {"status": "local_reference_only"},
                    "files": [{"role": "prefab", "path": f"Assets/{name}.prefab", "sha256": "same-content"}],
                }), encoding="utf-8")
                inputs.append(source)
            paths = build_corpus(inputs, root / "corpus", "content_group_test")
            records = [json.loads(line) for line in paths["records"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(records), 2)
        self.assertEqual(len({row["split_group"] for row in records}), 1)
        self.assertEqual(len({row["split"] for row in records}), 1)


if __name__ == "__main__":
    unittest.main()
