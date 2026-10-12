from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.professional_teacher_catalog import merge_indexes


class ProfessionalTeacherCatalogTests(unittest.TestCase):
    def _index(self, root: Path, index_id: str, record: dict) -> Path:
        root.mkdir(parents=True)
        (root / "records.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
        (root / "course_knowledge_index.json").write_text(json.dumps({"index_id": index_id, "files": {"records": "records.jsonl"}}), encoding="utf-8")
        return root

    def test_merges_unique_records_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._index(root / "one", "one", {"record_id": "a", "record_type": "tutorial_fact", "status": "verified", "effect_family": "explosion"})
            second = self._index(root / "two", "two", {"record_id": "b", "record_type": "tutorial_fact", "status": "verified", "effect_family": "explosion"})
            paths = merge_indexes([first, second], root / "output", "catalog")
            index = json.loads(paths["index"].read_text(encoding="utf-8"))
            records = [json.loads(line) for line in paths["records"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(index["record_count"], 2)
        self.assertEqual([row["record_id"] for row in records], ["a", "b"])
        self.assertEqual([row["index_id"] for row in index["source_indexes"]], ["one", "two"])

    def test_conflicting_duplicate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._index(root / "one", "one", {"record_id": "a", "status": "verified"})
            second = self._index(root / "two", "two", {"record_id": "a", "status": "pending"})
            with self.assertRaisesRegex(ValueError, "conflicting Teacher record"):
                merge_indexes([first, second], root / "output", "catalog")


if __name__ == "__main__":
    unittest.main()
