from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'workspace/tools/effectdemo_unity_process.ps1'
POWERSHELL = shutil.which('powershell')
WRAPPERS = (
    'effectdemo_cli', 'effectdemo_render_source', 'effectdemo_compile_prefab_graph',
    'effectdemo_compile_prefab_graph_batch', 'effectdemo_readback_prefab_graph',
    'effectdemo_export_prefab_graph_source', 'effectdemo_execute_material_trajectories',
    'effectdemo_audit_asset_routes',
)


@unittest.skipUnless(os.name == 'nt' and POWERSHELL, 'Windows process environment')
class EffectDemoUnityProcessTests(unittest.TestCase):
    def run_probe(self, setup: str, fail: bool = False) -> dict:
        self.assertTrue(HELPER.exists(), 'Unity process helper must be implemented')
        source = f"""
$ErrorActionPreference = 'Stop'
. '{str(HELPER).replace("'", "''")}'
{setup}
function Start-Process {{
    param($FilePath, $ArgumentList, $WindowStyle, [switch]$Wait, [switch]$PassThru)
    $script:observed = [ordered]@{{ profile = $env:ALLUSERSPROFILE; arguments = $ArgumentList; style = "$WindowStyle" }}
    {'throw "launch failed"' if fail else '[pscustomobject]@{ ExitCode = 17 }'}
}}
$caught = $false
try {{ $result = Start-EffectDemoUnityProcess -FilePath 'Unity.exe' -ArgumentList @('-batchmode', '-projectPath', 'Example') }}
catch {{ $caught = $true }}
[ordered]@{{ observed = $script:observed; restored = $env:ALLUSERSPROFILE; caught = $caught; exit_code = $result.ExitCode; common = [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData) }} | ConvertTo-Json -Compress -Depth 4
"""
        result = subprocess.run(
            [POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand',
             base64.b64encode(source.encode('utf-16le')).decode('ascii')],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_missing_profile_is_filled_only_for_child_launch(self) -> None:
        result = self.run_probe('$env:ALLUSERSPROFILE = $null')
        self.assertEqual(result['common'], result['observed']['profile'])
        self.assertIsNone(result['restored'])
        self.assertFalse(result['caught'])
        self.assertEqual(17, result['exit_code'])
        self.assertEqual('Hidden', result['observed']['style'])
        self.assertNotIn('-noUpm', result['observed']['arguments'])

    def test_existing_profile_is_preserved(self) -> None:
        result = self.run_probe("$env:ALLUSERSPROFILE = 'D:\\ExistingProfile'")
        self.assertEqual('D:\\ExistingProfile', result['observed']['profile'])
        self.assertEqual('D:\\ExistingProfile', result['restored'])

    def test_launch_failure_also_restores_missing_profile(self) -> None:
        result = self.run_probe('$env:ALLUSERSPROFILE = $null', fail=True)
        self.assertTrue(result['caught'])
        self.assertEqual(result['common'], result['observed']['profile'])
        self.assertIsNone(result['restored'])

    def test_all_effectdemo_entrypoints_use_guarded_launch(self) -> None:
        for name in WRAPPERS:
            with self.subTest(name=name):
                source = (ROOT / f'workspace/tools/{name}.ps1').read_text(encoding='utf-8-sig')
                self.assertIn('effectdemo_unity_process.ps1', source)
                self.assertIn('Start-EffectDemoUnityProcess', source)
                self.assertNotIn('$process = Start-Process', source)


if __name__ == '__main__':
    unittest.main()
