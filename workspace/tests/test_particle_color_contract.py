from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]


class ParticleColorContractTests(unittest.TestCase):
    def test_gradient_schema_rejects_unknown_modes_and_invalid_keys(self) -> None:
        schema = json.loads((ROOT / 'workspace/data/vfx_generation/schemas/prefab_graph.schema.json').read_text(encoding='utf-8'))
        self.assertIn('particleColorGradient', schema['$defs'])
        validator = Draft202012Validator(schema['$defs']['particleColorGradient'])
        gradient = {
            'mode': 'Fixed',
            'color_keys': [{'time': 0, 'rgb': [1, 1, 1]}, {'time': 1, 'rgb': [0, 0, 0]}],
            'alpha_keys': [{'time': 0, 'alpha': 1}, {'time': 1, 'alpha': 0}],
        }
        self.assertFalse(list(validator.iter_errors(gradient)))
        gradient['mode'] = 'Invented'
        self.assertTrue(list(validator.iter_errors(gradient)))
        gradient['mode'] = 'Blend'
        gradient['alpha_keys'][0]['alpha'] = 2
        self.assertTrue(list(validator.iter_errors(gradient)))

    def test_compiler_and_exporter_preserve_explicit_gradient_data(self) -> None:
        compiler = (ROOT / 'UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabGraphCompiler.cs').read_text(encoding='utf-8')
        readback = (ROOT / 'UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabGraphReadback.cs').read_text(encoding='utf-8')
        exporter = (ROOT / 'UnityDemo/EffectDemo/Assets/Editor/EffectDemoPrefabGraphSourceExporter.cs').read_text(encoding='utf-8')
        self.assertIn('color_over_lifetime_gradient.ToUnity()', compiler)
        self.assertIn('EffectDemoParticleColorGradient.HasData(parameters.color_over_lifetime_gradient)', compiler)
        self.assertIn('preserve_template', compiler)
        self.assertIn('EffectDemoParticleColorGradient.FromUnity', exporter)
        self.assertIn('EffectDemoParticleColorGradient.Equivalent', readback)
        self.assertIn('ComparePreservedMaterialColors', readback)
        self.assertIn('main.startColor.mode != ParticleSystemGradientMode.Color', readback)


if __name__ == '__main__':
    unittest.main()
