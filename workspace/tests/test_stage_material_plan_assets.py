from __future__ import annotations

import unittest
from pathlib import Path

from workspace.tools.vfx_generation.stage_material_plan_assets import _selected_asset_paths


ROOT = Path(__file__).parents[2]


class StageMaterialPlanAssetsTests(unittest.TestCase):
    def test_reads_selected_assets_from_real_asset_aware_manifest(self) -> None:
        manifest = ROOT / "workspace/data/vfx_generation/generated/prompt_asset_aware_full_r002/generation_manifest.json"
        if not manifest.is_file():
            self.skipTest("asset-aware generation fixture is not available")
        paths = _selected_asset_paths(manifest)
        self.assertTrue(paths)
        self.assertTrue(all(path.startswith("Assets/") for path in paths))
        self.assertTrue(any(path.endswith(".mat") for path in paths))
        self.assertTrue(any(path.endswith(".shader") for path in paths))
        self.assertTrue(any(path.endswith(".png") for path in paths))

    def test_reads_selected_assets_from_tutorial_guided_manifest(self) -> None:
        manifest = ROOT / "workspace/data/vfx_generation/generated/tutorial_lightning_effectdemo2022_r001/generation_manifest.json"
        if not manifest.is_file():
            self.skipTest("tutorial-guided generation fixture is not available")
        paths = _selected_asset_paths(manifest)
        self.assertTrue(any(path.endswith(".mat") for path in paths))
        self.assertTrue(any(path.endswith(".shader") for path in paths))
        self.assertTrue(any("lightning" in path.lower() and path.endswith(".png") for path in paths))


if __name__ == "__main__":
    unittest.main()
