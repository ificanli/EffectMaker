from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.material_curriculum_generator import (
    build_curriculum,
    generate_specs,
    load_material_candidates,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _material_yaml(name: str, texture_guid: str, keyword: str = "") -> str:
    keywords = f"[{keyword}]" if keyword else "[]"
    return f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!21 &2100000
Material:
  serializedVersion: 8
  m_Name: {name}
  m_ValidKeywords: {keywords}
  m_SavedProperties:
    serializedVersion: 3
    m_TexEnvs:
    - _MainTex:
        m_Texture: {{fileID: 2800000, guid: {texture_guid}, type: 3}}
        m_Scale: {{x: 1, y: 1}}
        m_Offset: {{x: 0, y: 0}}
    m_Ints: []
    m_Floats:
    - _Dissolve_Value: 0
    - _Main_SpeedU: 0
    - _Distort_Intensity: 0.1
    m_Colors:
    - _Color: {{r: 1, g: 0.5, b: 0.25, a: 1}}
    - _EmissionColor: {{r: 0.2, g: 0.4, b: 1, a: 1}}
"""


class MaterialCurriculumGeneratorTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        project = root / "EffectDemo"
        dataset = root / "dataset"
        materials = [
            "Assets/VFXSourceIngest/Materials/FireA.mat",
            "Assets/VFXSourceIngest/Materials/FireB.mat",
            "Assets/VFXSourceIngest/Materials/FireC.mat",
        ]
        textures = [
            "Assets/VFXSourceIngest/Shared/Textures/noise_a.png",
            "Assets/VFXSourceIngest/Shared/Textures/noise_b.png",
            "Assets/VFXSourceIngest/Shared/Textures/ring.png",
        ]
        for index, material in enumerate(materials):
            path = project / material
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_material_yaml(Path(material).stem, f"{index + 1:032x}", "FLOW_ON" if index == 0 else ""), encoding="utf-8")
        cases = [
            {
                "source": {"effect_family_hint": "fire", "source_category": ["battle"]},
                "inputs": {
                    "target_style_profile": {"family": "cartoon", "keywords": ["stylized"]},
                    "material_selection": {
                        "materials": [
                            {"material_path": material, "primary_shader_path": "Assets/Shaders/VFX.shader"}
                            for material in materials
                        ]
                    },
                },
                "observations": {"observed_style_profile": {"family": "unknown", "keywords": []}},
            }
        ]
        _write_jsonl(dataset / "prefab_cases.jsonl", cases)
        _write_jsonl(
            dataset / "texture_tags.jsonl",
            [
                {"relative_path": textures[0], "tags": ["slot.dissolve_map", "semantic.noise"]},
                {"relative_path": textures[1], "tags": ["slot.dissolve_map", "semantic.noise"]},
                {"relative_path": textures[2], "tags": ["semantic.ring", "role.impact_ring"]},
            ],
        )
        audit = {
            "materials": [
                {
                    "material_path": material,
                    "shader_name": "VFX/TestShader",
                    "properties": [
                        {"property_name": "_Dissolve_Value", "property_type": "float"},
                        {"property_name": "_Main_SpeedU", "property_type": "float"},
                        {"property_name": "_Distort_Intensity", "property_type": "range"},
                        {"property_name": "_Color", "property_type": "color"},
                        {"property_name": "_EmissionColor", "property_type": "color"},
                        {"property_name": "_MainTex", "property_type": "texture"},
                    ],
                    "bindings": [
                        {
                            "property_name": "_MainTex",
                            "is_bound": True,
                            "texture_path": textures[index],
                        }
                    ],
                }
                for index, material in enumerate(materials)
            ]
        }
        audit_path = root / "material-audit.json"
        _write_json(audit_path, audit)
        return project, dataset, audit_path

    def test_builds_deterministic_schema_valid_curriculum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, dataset, audit_path = self._fixture(root)
            quotas = {
                "dissolve": 1,
                "flow_distortion": 1,
                "emission_alpha": 1,
                "mpb": 1,
                "texture_swap": 1,
                "keyword_material": 1,
                "negative": 1,
            }
            manifest = build_curriculum(project, dataset, audit_path, root / "output", "test_curriculum", 42, quotas)
            schema = json.loads(Path("workspace/data/vfx_generation/schemas/material_trajectory.schema.json").read_text(encoding="utf-8"))
            specs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((root / "output/specs").glob("*.json"))]

            self.assertEqual(manifest["spec_count"], 7)
            self.assertEqual(manifest["category_counts"], quotas)
            self.assertEqual(manifest["label_counts"], {"negative": 1, "positive": 6})
            self.assertTrue(all(not list(Draft202012Validator(schema).iter_errors(spec)) for spec in specs))
            self.assertTrue(all(spec["source_asset"]["material_path"].endswith(".mat") for spec in specs))
            self.assertTrue(any(spec["texture_swap_events"] for spec in specs))
            self.assertTrue(any(spec["keyword_events"] or spec["material_replace_events"] for spec in specs))

            candidates = load_material_candidates(project, dataset / "prefab_cases.jsonl", audit_path, dataset / "texture_tags.jsonl")
            texture_records = [
                {"property_name": binding["property_name"], "texture_path": binding["texture_path"], "tags": binding["tags"]}
                for candidate in candidates
                for binding in candidate.texture_bindings
            ]
            first = generate_specs(candidates, texture_records, "deterministic", 99, quotas)
            second = generate_specs(candidates, texture_records, "deterministic", 99, quotas)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
