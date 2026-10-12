import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from workspace.tools.resource_index.texture_tagger import TextureTagConfig, build_texture_tags, tag_texture_record


class TextureTaggerTests(unittest.TestCase):
    def test_tags_texture_with_semantic_geometry_pixel_slot_and_role_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            texture = root / "FXTexture" / "Slash" / "Knifelight-2.png"
            texture.parent.mkdir(parents=True)
            image = Image.new("RGBA", (32, 8), (0, 0, 0, 0))
            for x in range(8, 24):
                for y in range(2, 6):
                    image.putpixel((x, y), (255, 255, 255, 255))
            image.save(texture)
            record = {
                "asset_id": "asset-1",
                "relative_path": "FXTexture/Slash/Knifelight-2.png",
                "asset_type": "texture",
                "extension": ".png",
                "width": 32,
                "height": 8,
                "license_status": "unknown",
                "tags": [],
            }

            tagged = tag_texture_record(record, root)

        self.assertIn("semantic.slash", tagged["tags"])
        self.assertIn("shape.horizontal_strip", tagged["tags"])
        self.assertIn("alpha.sparse", tagged["tags"])
        self.assertIn("alpha.structured", tagged["tags"])
        self.assertIn("slot.base_map", tagged["tags"])
        self.assertIn("slot.ramp_map", tagged["tags"])
        self.assertIn("role.core_shape", tagged["tags"])
        self.assertIn("quality.license_unknown", tagged["tags"])
        self.assertGreater(tagged["metrics"]["transparent_ratio"], 0.0)

    def test_build_texture_tags_filters_query_and_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "resource" / "FXTexture" / "Noise").mkdir(parents=True)
            Image.new("RGBA", (16, 16), (128, 128, 128, 255)).save(root / "resource" / "FXTexture" / "Noise" / "DissolveNoise.png")
            Image.new("RGBA", (16, 16), (255, 255, 255, 255)).save(root / "resource" / "FXTexture" / "Noise" / "Other.png")
            assets = root / "assets.jsonl"
            rows = [
                {
                    "asset_id": "noise-1",
                    "relative_path": "FXTexture/Noise/DissolveNoise.png",
                    "asset_type": "texture",
                    "extension": ".png",
                    "width": 16,
                    "height": 16,
                    "license_status": "unknown",
                    "tags": [],
                },
                {
                    "asset_id": "other-1",
                    "relative_path": "FXTexture/Noise/Other.png",
                    "asset_type": "texture",
                    "extension": ".png",
                    "width": 16,
                    "height": 16,
                    "license_status": "unknown",
                    "tags": [],
                },
            ]
            assets.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            output = root / "tags.jsonl"

            records = build_texture_tags(
                TextureTagConfig(
                    resource_root=root / "resource",
                    assets_jsonl=assets,
                    output_jsonl=output,
                    query="Dissolve",
                )
            )
            written = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(records), 1)
        self.assertEqual(written[0]["asset_id"], "noise-1")
        self.assertIn("semantic.noise", written[0]["tags"])
        self.assertIn("slot.dissolve_map", written[0]["tags"])
        self.assertIn("slot.distortion_map", written[0]["tags"])
        self.assertIn("role.noise_control", written[0]["tags"])


if __name__ == "__main__":
    unittest.main()
