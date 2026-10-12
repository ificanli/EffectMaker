from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from PIL import Image

from workspace.tools.vfx_generation.professional_teacher_reproduction import (
    CORE_MATERIAL_TEMPLATE,
    CORE_TEXTURE,
    _controlled_graph_comparison,
    _frame_metrics,
    _variant,
    _write_jsonl,
)


class ProfessionalTeacherReproductionTests(unittest.TestCase):
    def test_only_core_alpha_changes_between_variants(self) -> None:
        source = {
            "schema_version": "vfx_prefab_graph.v1",
            "source": {"source_kind": "generated", "prefab_path": None, "source_example_id": None},
            "condition": {"prompt": "x", "effect_family": "explosion", "style_family": "cartoon", "seed": 1, "parent_prefab_path": None},
            "root_node_id": "n0000",
            "nodes": [{"node_id": "n0000", "role": "root"}, {"node_id": "n0001", "role": "core"}, {"node_id": "n0002", "role": "support"}],
            "components": {"particle_systems": [{"component_id": "p0", "node_id": "n0001", "parameters": {"start_color_rgba": [1, 1, 1, 1], "serialized_modules": {}}, "material_paths": [], "mesh_paths": []}, {"component_id": "p1", "node_id": "n0002", "parameters": {"start_color_rgba": [1, 1, 1, 1]}, "material_paths": [], "mesh_paths": []}], "renderers": [{"component_id": "r0", "node_id": "n0001", "parameters": {"sorting_order": 2}}, {"component_id": "r1", "node_id": "n0002", "parameters": {"sorting_order": 2}}], "animations": []},
            "asset_bindings": {"materials": [], "meshes": []},
            "reconstruction": {"status": "reconstructable", "compiler_profile": "particle_v1", "missing_fields": [], "unsupported_components": []},
            "training": {"eligible_tasks": [], "excluded_tasks": [], "aesthetic_label_source": "ai_hypothesis"},
            "provenance": {"source_dataset_id": "test", "source_run_id": None, "exporter": "test", "assumptions": []},
        }
        empty = _variant(source, "empty_core")
        reinforced = _variant(source, "reinforced_core")
        self.assertEqual(empty["components"]["particle_systems"][0]["parameters"]["start_color_rgba"][3], 0.0)
        self.assertEqual(reinforced["components"]["particle_systems"][0]["parameters"]["start_color_rgba"][3], 0.95)
        self.assertEqual(empty["components"]["particle_systems"][1], reinforced["components"]["particle_systems"][1])
        self.assertEqual(empty["components"]["particle_systems"][0]["parameters"]["material_template_path"], CORE_MATERIAL_TEMPLATE)
        self.assertEqual(empty["components"]["particle_systems"][0]["parameters"]["texture_asset_path"], CORE_TEXTURE)
        self.assertEqual(empty["components"]["renderers"][0]["parameters"]["sorting_order"], 10)
        self.assertNotEqual(empty["graph_id"], reinforced["graph_id"])
        comparison = _controlled_graph_comparison(empty, reinforced)
        self.assertTrue(comparison["only_core_alpha_differs"])
        self.assertEqual(
            comparison["difference_paths"],
            ["components.particle_systems[0].parameters.start_color_rgba[3]"],
        )

    def test_teacher_records_are_written_as_single_line_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "records.jsonl"
            _write_jsonl(path, [{"record_id": "rule-1", "excerpt": "爆炸核心"}])
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["record_id"], "rule-1")

    def test_center_luminance_and_local_contrast_measure_core_prominence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_path = Path(temp_dir) / "empty.png"
            reinforced_path = Path(temp_dir) / "reinforced.png"
            empty = Image.new("RGB", (100, 100), (0, 0, 0))
            reinforced = Image.new("RGB", (100, 100), (0, 0, 0))
            for image in (empty, reinforced):
                for x in range(30, 70):
                    for y in range(30, 70):
                        image.putpixel((x, y), (20, 60, 120))
            for x in range(42, 58):
                for y in range(42, 58):
                    reinforced.putpixel((x, y), (180, 220, 255))
            empty.save(empty_path)
            reinforced.save(reinforced_path)
            empty_metrics = _frame_metrics(empty_path)
            reinforced_metrics = _frame_metrics(reinforced_path)
            self.assertGreater(reinforced_metrics["center_luminance"], empty_metrics["center_luminance"])
            self.assertGreater(reinforced_metrics["center_local_contrast"], empty_metrics["center_local_contrast"])


if __name__ == "__main__":
    unittest.main()
