from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.full_prefab_technical_baseline import build_full_prefab_baseline


ROOT = Path(__file__).parents[2]


class FullPrefabTechnicalBaselineTests(unittest.TestCase):
    def _prefab(self, path: str, *, valid_graph: bool = True) -> dict:
        nodes = [{"hierarchy_path": "Root[0]", "active_self": True, "component_types": ["UnityEngine.Transform"]}] if valid_graph else []
        return {
            "prefab_path": path,
            "status": "static_or_contextual" if valid_graph else "audit_error",
            "reasons": [],
            "node_count": len(nodes),
            "particle_system_count": 0,
            "particle_renderer_count": 0,
            "renderer_count": 0,
            "material_slot_count": 0,
            "missing_material_slot_count": 0,
            "serialized_empty_material_slot_count": 0,
            "missing_shader_count": 0,
            "missing_script_count": 1 if not valid_graph else 0,
            "max_particle_count": 0,
            "estimated_duration_seconds": 0.0,
            "looping": False,
            "animator_count": 0,
            "legacy_animation_count": 0,
            "playable_director_count": 0,
            "nodes": nodes,
            "particle_systems": [],
            "renderers": [],
            "animations": [],
        }

    def test_builds_full_technical_coverage_and_excludes_only_invalid_graphs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "EffectDemo"
            (project / "Assets/PackA").mkdir(parents=True)
            (project / "Assets/PackB").mkdir(parents=True)
            (project / "Assets/PackA/A.prefab").write_text("prefab", encoding="utf-8")
            (project / "Assets/PackB/B.prefab").write_text("prefab", encoding="utf-8")
            audit = {
                "schema_version": "effectdemo_prefab_structure_audit.v3",
                "created_at": "2026-09-02T00:00:00Z",
                "audit_revision": 3,
                "unity_version": "2022.3.16f1c1",
                "import_root": "Assets",
                "sample_times_seconds": [0.05],
                "prefab_count": 2,
                "particle_structure_count": 0,
                "particle_playable_count": 0,
                "particle_context_required_count": 0,
                "static_or_contextual_count": 1,
                "empty_or_invalid_count": 1,
                "total_particle_system_count": 0,
                "total_renderer_count": 0,
                "total_missing_material_slot_count": 0,
                "total_serialized_empty_material_slot_count": 0,
                "total_missing_shader_count": 0,
                "total_missing_script_count": 1,
                "prefabs": [self._prefab("Assets/PackA/A.prefab"), self._prefab("Assets/PackB/B.prefab", valid_graph=False)],
            }
            audit_path = root / "audit.json"
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            paths = build_full_prefab_baseline(audit_path, project, root / "output", "full_test_r001")
            baseline = json.loads(paths["baseline_manifest"].read_text(encoding="utf-8"))
            graph_manifest = json.loads(paths["prefab_graph_manifest"].read_text(encoding="utf-8"))
            technical = paths["technical_records"].read_text(encoding="utf-8").splitlines()
            exclusions = paths["graph_exclusions"].read_text(encoding="utf-8").splitlines()

        self.assertEqual(baseline["disk_prefab_count"], 2)
        self.assertEqual(baseline["technical_record_count"], 2)
        self.assertEqual(baseline["quality_gates"]["technical_coverage"], 1.0)
        self.assertEqual(baseline["graph_count"], 1)
        self.assertEqual(baseline["graph_exclusion_count"], 1)
        self.assertEqual(len(technical), 2)
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(graph_manifest["example_count"], 1)
        self.assertEqual(graph_manifest["quality_gates"]["aesthetic_labels_consumed"], 0)

    def test_unity_auditor_supports_legacy_and_full_asset_markers(self) -> None:
        source = (ROOT / "UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabPlayabilityAudit.cs").read_text(encoding="utf-8")
        self.assertIn("Library/VFXSourceIngest/prefab-playability-audit.marker", source)
        self.assertIn("Library/VFXTraining/full-prefab-audit.marker", source)
        self.assertIn('WriteReport(projectRoot, "Assets", FullAssetReportRelativePath)', source)
        self.assertIn('AssetDatabase.FindAssets("t:Prefab", new[] { importRoot })', source)
        self.assertIn('Replace("%", "%25").Replace("/", "%2F")', source)


if __name__ == "__main__":
    unittest.main()
