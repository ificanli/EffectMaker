from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class PrefabGraphSourceExportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabGraphSourceExporter.cs").read_text(encoding="utf-8")

    def test_uses_unity_api_and_preserves_asset_edges(self) -> None:
        self.assertIn("AssetDatabase.LoadAssetAtPath<GameObject>", self.source)
        self.assertIn("GetComponentsInChildren<Transform>", self.source)
        self.assertIn("GetComponent<ParticleSystem>()", self.source)
        self.assertIn("GetAssetPath", self.source)
        self.assertIn("serialized_modules", self.source)
        self.assertIn("renderer == null", self.source)
        self.assertIn("ParticleSystemWithoutParticleSystemRenderer", self.source)
        self.assertIn("start_size_3d = main.startSize3D", self.source)
        self.assertIn("GetActiveVertexStreams", self.source)
        self.assertIn("active_vertex_streams", self.source)
        self.assertIn('unsupported.Add("ParticleSystem.custom_data")', self.source)
        self.assertNotIn("ReadAllText(request.prefab_path)", self.source)

    def test_marks_unsupported_source_components_and_aesthetic_boundary(self) -> None:
        self.assertIn("unsupported_components", self.source)
        self.assertIn('aesthetic_label_source = "none"', self.source)
        self.assertIn("aesthetic_preference", self.source)
        self.assertIn("prefab_graph_source_unity.v1", self.source)

    def test_preparation_filters_to_particle_v1(self) -> None:
        source = (ROOT / "workspace/tools/vfx_generation/prepare_prefab_graph_source_export.py").read_text(encoding="utf-8")
        self.assertIn("ParticleSystemRenderer", source)
        self.assertIn("particle_playable", source)
        self.assertIn("particle_node_paths", source)
