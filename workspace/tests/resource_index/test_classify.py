import json
import unittest
from pathlib import Path

from workspace.tools.resource_index.classify import (
    classify_asset,
    derive_tags,
    infer_license,
)
from workspace.tools.resource_index.models import AssetRecord, ScanConfig


class ClassificationTests(unittest.TestCase):
    def test_classifies_supported_extensions_case_insensitively(self):
        cases = {
            "spark.PNG": "texture",
            "mesh.fbx": "model",
            "surface.mat": "material",
            "effect.shader": "shader",
            "bundle.unitypackage": "package",
            "readme.PDF": "document",
            "source.zip": "archive",
            "unknown.bin": "other",
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                self.assertEqual(classify_asset(Path(filename)), expected)

    def test_normalizes_bilingual_path_tags_and_uses_stable_order(self):
        path = Path("素材/火/fire/噪声/noise/序列/flipbook/刀光/slash.png")
        self.assertEqual(
            derive_tags(path),
            ["fire", "noise", "flipbook", "slash"],
        )

    def test_maps_specialized_vfx_vocabulary(self):
        path = Path("冰/法阵/遮罩/扰动/水/烟雾/闪电/护盾/传送门/地面/UI/model.fbx")
        self.assertEqual(
            derive_tags(path),
            [
                "ice", "magic-circle", "mask", "distortion", "water", "smoke",
                "lightning", "shield", "portal", "ground", "UI", "model",
            ],
        )

    def test_license_stays_unknown_while_collecting_hints(self):
        status, hints = infer_license(Path("来源/免责声明/某商店页面/素材.png"))
        self.assertEqual(status, "unknown")
        self.assertEqual(hints, ["免责声明", "商店页面", "来源"])

    def test_models_are_json_safe(self):
        config = ScanConfig(root=Path("resource"))
        record = AssetRecord(
            asset_id="abc",
            relative_path="fire/spark.png",
            asset_type="texture",
            extension=".png",
            size_bytes=10,
            modified_time=1.5,
            tags=["fire"],
        )
        payload = record.to_dict()
        json.dumps(payload)
        self.assertEqual(payload["license_status"], "unknown")
        self.assertEqual(config.to_dict()["root"], "resource")


if __name__ == "__main__":
    unittest.main()
