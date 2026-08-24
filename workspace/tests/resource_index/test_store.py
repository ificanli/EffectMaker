import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.resource_index.models import AssetRecord
from workspace.tools.resource_index.store import ResourceIndexStore


def record(path, *, asset_id=None, sha256=None, tags=None, width=None, height=None,
           asset_type="texture", license_status="unknown"):
    return AssetRecord(
        asset_id=asset_id or path.replace("/", "_"), relative_path=path,
        asset_type=asset_type, extension=Path(path).suffix, size_bytes=10,
        modified_time=1.5, sha256=sha256, tags=tags or [],
        license_status=license_status, license_hints=["source"], width=width,
        height=height, mode="RGBA", channels=4, thumbnail_status="created",
        error=None,
    )


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = ResourceIndexStore(self.root / "index.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_initialize_creates_schema(self):
        self.store.initialize()
        tables = {row[0] for row in self.store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        self.assertTrue({"assets", "asset_tags", "scans"} <= tables)

    def test_upsert_is_idempotent_and_persists_sorted_tags(self):
        asset = record("fire/z.png", sha256="hash", tags=["z", "fire", "fire"])
        self.store.upsert_assets([asset])
        self.store.upsert_assets([asset])
        self.assertEqual(self.store.stats()["total"], 1)
        self.assertEqual(self.store.get_by_path("fire/z.png").tags, ["fire", "z"])

    def test_mark_missing_sets_only_unseen_assets_and_records_scan(self):
        self.store.upsert_assets([record("a.png"), record("b.png")])
        self.store.mark_missing({"a.png"}, "scan-1")
        self.assertEqual(self.store.get_by_path("a.png").status, "present")
        self.assertEqual(self.store.get_by_path("b.png").status, "missing")
        self.assertEqual(self.store.stats()["missing"], 1)
        self.assertEqual(self.store.connection.execute("SELECT scan_id FROM scans").fetchone()[0], "scan-1")

    def test_duplicates_returns_hash_groups(self):
        self.store.upsert_assets([
            record("b.png", sha256="same"), record("a.png", sha256="same"),
            record("unique.png", sha256="other"), record("none.png"),
        ])
        self.assertEqual(self.store.duplicates(), [{"sha256": "same", "count": 2, "paths": ["a.png", "b.png"]}])

    def test_query_filters_type_tag_license_dimensions_and_limit(self):
        self.store.upsert_assets([
            record("a.png", tags=["fire"], width=100, height=80),
            record("b.png", tags=["fire", "ice"], width=200, height=120, license_status="restricted"),
            record("c.fbx", tags=["model"], width=300, height=300, asset_type="model"),
        ])
        result = self.store.query(asset_type="texture", tag="fire", license_status="restricted",
                                  min_width=150, min_height=100, limit=1)
        self.assertEqual([item.relative_path for item in result], ["b.png"])

    def test_jsonl_export_has_deterministic_sorted_rows(self):
        self.store.upsert_assets([record("z.png", tags=["z", "a"]), record("a.png")])
        output = self.root / "assets.jsonl"
        self.store.export_jsonl(output)
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["relative_path"] for row in rows], ["a.png", "z.png"])
        self.assertEqual(len(rows), self.store.stats()["total"])
        self.assertEqual(rows[1]["tags"], ["a", "z"])


if __name__ == "__main__":
    unittest.main()
