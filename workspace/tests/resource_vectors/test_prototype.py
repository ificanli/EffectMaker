import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from workspace.tools.resource_vectors.index import (
    build_vector_index,
    build_full_vector_index,
    load_vector_index,
    search_vectors,
)
from workspace.tools.resource_vectors.query import normalize_text_query, resolve_query_image
from workspace.tools.resource_vectors.sample import select_sample


class FakeEncoder:
    model_id = "test/fake-clip"
    revision = "local-test"

    def __init__(self):
        self.image_calls = []

    def encode_images(self, paths):
        self.image_calls.extend(Path(path).name for path in paths)
        values = []
        for path in paths:
            name = Path(path).stem
            values.append([1.0, 0.0] if name.startswith("red") else [0.0, 1.0])
        return np.asarray(values, dtype=np.float32)

    def encode_text(self, text):
        return np.asarray([1.0, 0.0] if "red" in text else [0.0, 1.0], dtype=np.float32)


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "resource"
        self.output = Path(self.temp.name) / "vectors"
        self.root.mkdir()
        for folder, name, color in [
            ("z", "blue_b.png", "blue"),
            ("a", "red_b.png", "red"),
            ("a", "red_a.png", "red"),
            ("z", "blue_a.png", "blue"),
        ]:
            path = self.root / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 8), color).save(path)

    def tearDown(self):
        self.temp.cleanup()

    def test_direct_sample_is_deterministic_and_preserves_stable_metadata(self):
        first = select_sample(self.root, limit=3)
        second = select_sample(self.root, limit=3)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        for item in first:
            expected_hash = hashlib.sha256((self.root / item["relative_path"]).read_bytes()).hexdigest()
            self.assertEqual(item["sha256"], expected_hash)
            self.assertEqual(
                item["asset_id"],
                hashlib.sha256(item["relative_path"].encode("utf-8")).hexdigest(),
            )

    def test_sample_rejects_first_phase_record_outside_resource_root(self):
        outside = Path(self.temp.name) / "outside.png"
        Image.new("RGB", (8, 8), "white").save(outside)
        database = Path(self.temp.name) / "assets-outside.sqlite3"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "CREATE TABLE assets (asset_id TEXT, relative_path TEXT, asset_type TEXT, "
                "extension TEXT, sha256 TEXT, status TEXT, error TEXT)"
            )
            connection.execute(
                "INSERT INTO assets VALUES (?, ?, 'texture', '.png', ?, 'present', NULL)",
                ("outside-id", "../outside.png", "outside-hash"),
            )
            connection.commit()
        finally:
            connection.close()
        sample = select_sample(self.root, limit=64, sqlite_path=database)
        self.assertNotIn("../outside.png", [row["relative_path"] for row in sample])

    def test_sample_prefers_first_phase_sqlite_records(self):
        database = Path(self.temp.name) / "assets.sqlite3"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "CREATE TABLE assets (asset_id TEXT, relative_path TEXT, asset_type TEXT, "
                "extension TEXT, sha256 TEXT, status TEXT, error TEXT)"
            )
            connection.execute(
                "INSERT INTO assets VALUES (?, ?, 'texture', '.png', ?, 'present', NULL)",
                ("phase-one-id", "a/red_a.png", "phase-one-hash"),
            )
            connection.commit()
        finally:
            connection.close()
        sample = select_sample(self.root, limit=64, sqlite_path=database)
        self.assertEqual(sample, [{
            "asset_id": "phase-one-id",
            "relative_path": "a/red_a.png",
            "sha256": "phase-one-hash",
        }])

    def test_cosine_search_normalizes_and_orders_stably(self):
        vectors = np.asarray([[2.0, 0.0], [1.0, 1.0], [-1.0, 0.0]], dtype=np.float32)
        metadata = [
            {"asset_id": "b", "relative_path": "b.png", "sha256": "2"},
            {"asset_id": "a", "relative_path": "a.png", "sha256": "1"},
            {"asset_id": "c", "relative_path": "c.png", "sha256": "3"},
        ]
        results = search_vectors(np.asarray([10.0, 0.0]), vectors, metadata, limit=3)
        self.assertEqual([row["asset_id"] for row in results], ["b", "a", "c"])
        self.assertAlmostEqual(results[0]["score"], 1.0)

    def test_relative_query_image_resolves_against_resource_root(self):
        resolved = resolve_query_image(Path("a/red_a.png"), self.root)
        self.assertEqual(resolved, (self.root / "a" / "red_a.png").resolve())

    def test_missing_query_image_lists_both_checked_locations(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            resolve_query_image(Path("missing.png"), self.root)

    def test_resource_relative_query_cannot_escape_resource_root(self):
        outside = Path(self.temp.name) / "outside.png"
        Image.new("RGB", (8, 8), "white").save(outside)
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            with self.assertRaisesRegex(ValueError, "outside resource root"):
                resolve_query_image(Path("../outside.png"), self.root)
        finally:
            os.chdir(previous)

    def test_chinese_vfx_query_is_normalized_for_english_clip(self):
        normalized = normalize_text_query("蓝色闪电拖尾，适合刀光")
        self.assertIn("blue", normalized)
        self.assertIn("lightning", normalized)
        self.assertIn("trail", normalized)
        self.assertIn("slash", normalized)
        self.assertIn("VFX texture", normalized)

    def test_incremental_build_reuses_unchanged_hashes(self):
        encoder = FakeEncoder()
        sample = select_sample(self.root, limit=4)
        first = build_vector_index(sample, self.root, self.output, encoder)
        self.assertEqual(first["encoded"], 4)
        self.assertEqual(first["reused"], 0)

        encoder.image_calls.clear()
        changed = self.root / "a" / "red_a.png"
        Image.new("RGB", (8, 8), "green").save(changed)
        second_sample = select_sample(self.root, limit=4)
        second = build_vector_index(second_sample, self.root, self.output, encoder)
        self.assertEqual(second["encoded"], 1)
        self.assertEqual(second["reused"], 3)
        self.assertEqual(encoder.image_calls, ["red_a.png"])
        vectors, metadata, manifest = load_vector_index(self.output)
        self.assertEqual(vectors.shape, (4, 2))
        self.assertEqual(len(metadata), 4)
        self.assertEqual(manifest["model_id"], "test/fake-clip")

    def test_full_build_batches_without_loading_all_images_and_resumes(self):
        encoder = FakeEncoder()
        records = select_sample(self.root, limit=4)
        first = build_full_vector_index(records, self.root, self.output, encoder, batch_size=2)
        self.assertEqual(first["encoded"], 4)
        self.assertEqual(first["batches"], 2)
        (self.output / "vectors.npy").unlink()
        (self.output / "metadata.jsonl").unlink()
        (self.output / "manifest.json").unlink()
        encoder.image_calls.clear()
        second = build_full_vector_index(records, self.root, self.output, encoder, batch_size=2)
        self.assertEqual(second["encoded"], 0)
        self.assertEqual(second["reused"], 4)
        self.assertEqual(encoder.image_calls, [])
        self.assertTrue((self.output / "progress.jsonl").is_file())

    def test_full_build_records_failed_image_and_continues(self):
        encoder = FakeEncoder()
        original = encoder.encode_images
        def fail_bad(paths):
            if any(Path(path).name == "bad.png" for path in paths):
                good = [path for path in paths if Path(path).name != "bad.png"]
                if good:
                    return original(good)
                raise OSError("cannot decode bad.png")
            return original(paths)
        encoder.encode_images = fail_bad
        (self.root / "bad.png").write_bytes(b"not a valid png")
        records = select_sample(self.root, limit=5)
        result = build_full_vector_index(records, self.root, self.output, encoder, batch_size=1)
        self.assertEqual(result["failed"], 1)
        progress = [json.loads(line) for line in (self.output / "progress.jsonl").read_text().splitlines()]
        self.assertTrue(any(row["status"] == "failed" for row in progress))
        self.assertEqual(load_vector_index(self.output)[0].shape[0], result["indexed"])

    def test_full_build_empty_input_has_clear_summary(self):
        result = build_full_vector_index([], self.root, self.output, FakeEncoder(), batch_size=2)
        self.assertEqual(result["indexed"], 0)
        self.assertEqual(result["encoded"], 0)
        self.assertEqual(result["failed"], 0)


if __name__ == "__main__":
    unittest.main()
