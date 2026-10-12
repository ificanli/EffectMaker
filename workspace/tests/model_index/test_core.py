import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from workspace.tools.model_index.core import (
    PARSER_VERSION,
    asset_id_for,
    content_hash_for,
    discover_assets,
    build_all,
    build_sample,
    query_metadata,
)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "resource"
        self.root.mkdir()
        (self.root / "nested").mkdir()
        (self.root / "nested" / "a.FBX").write_bytes(b"a")
        (self.root / "b.obj").write_bytes(b"b")
        (self.root / "ignore.txt").write_text("x")
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_hash_contracts(self):
        rel = "nested/a.FBX"
        self.assertEqual(asset_id_for(rel), hashlib.sha256(rel.encode()).hexdigest())
        self.assertEqual(content_hash_for(self.root / "nested/a.FBX"), hashlib.sha256(b"a").hexdigest())

    def test_discovery_is_sorted_filtered_and_limited(self):
        self.assertEqual([p.relative_to(self.root).as_posix() for p in discover_assets(self.root, 1)], ["b.obj"])

    def test_build_records_failure_and_writes_outputs(self):
        def runner(path, preview_dir, asset_id):
            if path.name == "b.obj":
                raise RuntimeError("bad import")
            preview_root = Path(preview_dir) / asset_id
            return {"vertex_count": 3, "polygon_count": 1, "triangle_count": 1,
                    "bounds": {"min": [0, 0, 0], "max": [1, 1, 0]},
                    "uv_layer_count": 1, "has_vertex_colors": False,
                    "has_normals": True, "material_slot_count": 1,
                    "animation_count": 0, "previews": {name: str(preview_root / (name + ".png")) for name in ("front", "side", "perspective")}}
        with patch("workspace.tools.model_index.core.run_blender", side_effect=runner):
            result = build_sample(self.root, self.out, limit=5, blender="blender", runner=runner)
        self.assertEqual(result["processed"], 2)
        rows = [json.loads(line) for line in (self.out / "metadata.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        by_path = {row["relative_path"]: row for row in rows}
        self.assertEqual(by_path["nested/a.FBX"]["status"], "ok")
        self.assertEqual(by_path["b.obj"]["status"], "error")
        self.assertTrue((self.out / "manifest.json").exists())
        self.assertTrue((self.out / "checkpoint.json").exists())
        self.assertEqual(set(by_path["nested/a.FBX"]["previews"]), {"front", "side", "perspective"})
        self.assertIn("model", by_path["nested/a.FBX"]["tags"])
        self.assertTrue(all("0e058" in value for value in by_path["nested/a.FBX"]["previews"].values()))

    def test_jsonl_write_uses_replace_and_preserves_previous_on_failure(self):
        from workspace.tools.model_index import core
        path = self.out / "rows.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"old": true}\n', encoding="utf-8")
        with patch("workspace.tools.model_index.core.os.replace", side_effect=OSError("interrupt")):
            with self.assertRaises(OSError):
                core._write_jsonl(path, [{"new": True}])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"old": True})

        value = {"vertex_count": 1, "polygon_count": 0, "triangle_count": 0,
                 "bounds": None, "uv_layer_count": 0, "has_vertex_colors": False,
                 "has_normals": False, "material_slot_count": 0, "animation_count": 0,
                 "previews": {}}
        with patch("workspace.tools.model_index.core.run_blender", return_value=value) as runner:
            build_sample(self.root, self.out, limit=1, blender="blender")
            build_sample(self.root, self.out, limit=1, blender="blender", resume=True)
        runner.assert_called_once()


class BuildAllTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "resource"
        self.root.mkdir()
        (self.root / "a.obj").write_bytes(b"a")
        (self.root / "b.fbx").write_bytes(b"b")
        self.out = Path(self.tmp.name) / "full"

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def result(preview_dir, asset_id, vertices=3, triangles=1):
        target = Path(preview_dir) / asset_id
        target.mkdir(parents=True, exist_ok=True)
        previews = {}
        for index, view in enumerate(("front", "side", "perspective")):
            path = target / f"{asset_id}-{view}.png"
            image = Image.new("RGB", (2, 2), "white")
            image.putpixel((index % 2, index // 2), (0, 0, 0))
            image.save(path)
            previews[view] = str(path)
        return {"vertex_count": vertices, "polygon_count": 1, "triangle_count": triangles,
                "bounds": {"min": [0, 0, 0], "max": [1, 2, 3]}, "uv_layer_count": 0,
                "has_vertex_colors": False, "has_normals": True, "material_slot_count": 0,
                "animation_count": 0, "previews": previews, "tags": ["prop"]}

    def test_build_all_rejects_output_inside_resource(self):
        with self.assertRaisesRegex(ValueError, "outside resource"):
            build_all(self.root, self.root / "generated", runner=lambda *args: {})

    def test_build_all_persists_after_each_model_and_isolates_failures(self):
        snapshots = []

        def runner(path, preview_dir, asset_id, timeout):
            self.assertEqual(timeout, 17)
            if path.name == "b.fbx":
                raise TimeoutError("timed out")
            return self.result(preview_dir, asset_id)

        def observe(path, value):
            if path.name == "progress.jsonl":
                snapshots.append(len(value))

        result = build_all(self.root, self.out, blender="blender", timeout=17, runner=runner,
                           write_observer=observe)
        self.assertEqual(snapshots, [1, 2])
        self.assertEqual(result, {"input": 2, "processed": 2, "succeeded": 1, "failed": 1,
                                  "skipped": 0, "remaining": 0})
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["counts"], result)
        self.assertEqual(len(manifest["failures"]), 1)
        rows = [json.loads(line) for line in (self.out / "metadata.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual({row["status"] for row in rows}, {"ok", "error"})

    def test_resume_reuses_only_valid_success_and_retries_failure(self):
        calls = []

        def first(path, preview_dir, asset_id, timeout):
            if path.name == "b.fbx":
                raise RuntimeError("first failure")
            return self.result(preview_dir, asset_id)

        build_all(self.root, self.out, runner=first)

        def second(path, preview_dir, asset_id, timeout):
            calls.append(path.name)
            return self.result(preview_dir, asset_id)

        result = build_all(self.root, self.out, resume=True, runner=second)
        self.assertEqual(calls, ["b.fbx"])
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["failed"], 0)

    def test_resume_preserves_existing_records_when_retrying_subset(self):
        build_all(self.root, self.out, runner=lambda path, preview_dir, asset_id, timeout:
                  self.result(preview_dir, asset_id))
        rows = [json.loads(line) for line in (self.out / "metadata.jsonl").read_text(encoding="utf-8").splitlines()]
        rows[0]["status"] = "error"
        rows[0]["previews"] = {}
        (self.out / "metadata.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        calls = []

        def retry(path, preview_dir, asset_id, timeout):
            calls.append(path.name)
            return self.result(preview_dir, asset_id)

        result = build_all(self.root, self.out, resume=True, runner=retry)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["remaining"], 0)
        final_rows = [json.loads(line) for line in (self.out / "metadata.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(final_rows), 2)

        (self.root / "c.obj").write_bytes(b"c")
        build_all(self.root, self.out, runner=lambda path, preview_dir, asset_id, timeout:
                  self.result(preview_dir, asset_id))
        result = build_all(self.root, self.out, limit=2, resume=True,
                           runner=lambda *args: self.fail("limited resume should reuse"))
        rows = [json.loads(line) for line in (self.out / "metadata.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(result, {"input": 2, "processed": 2, "succeeded": 2, "failed": 0,
                                  "skipped": 2, "remaining": 0})

    def test_resume_rebuilds_zero_byte_corrupt_and_blank_previews(self):
        cases = ("zero", "corrupt", "blank")
        for case in cases:
            with self.subTest(case=case):
                output = self.out / case
                build_all(self.root, output, limit=1,
                           runner=lambda path, preview_dir, asset_id, timeout: self.result(preview_dir, asset_id))
                row = json.loads((output / "metadata.jsonl").read_text(encoding="utf-8").splitlines()[0])
                damaged = Path(row["previews"]["front"])
                if case == "zero":
                    damaged.write_bytes(b"")
                elif case == "corrupt":
                    damaged.write_bytes(b"not a png")
                else:
                    Image.new("RGB", (2, 2), "white").save(damaged)
                calls = []

                def rebuild(path, preview_dir, asset_id, timeout):
                    calls.append(path.name)
                    return self.result(preview_dir, asset_id)

                result = build_all(self.root, output, limit=1, resume=True, runner=rebuild)
                self.assertEqual(calls, ["a.obj"])
                self.assertEqual(result["skipped"], 0)

    def test_query_metadata_filters_format_tags_and_geometry(self):
        metadata = self.out / "metadata.jsonl"
        self.out.mkdir()
        rows = [
            {"asset_id": "a", "format": "obj", "tags": ["prop", "stone"], "vertex_count": 10, "triangle_count": 5},
            {"asset_id": "b", "format": "fbx", "tags": ["character"], "vertex_count": 100, "triangle_count": 80},
        ]
        metadata.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        self.assertEqual([row["asset_id"] for row in query_metadata(
            metadata, asset_type="obj", tag="prop", min_vertices=5, max_vertices=20,
            min_triangles=1, max_triangles=10)], ["a"])


if __name__ == "__main__":
    unittest.main()
