import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).parents[1] / "unity-verification" / "Packages" / "com.coplaydev.unity-mcp" / "UnityMcpServer~" / "src" / "tools" / "read_local_image.py"


class NativeImageToolContractTests(unittest.TestCase):
    def test_tool_uses_native_fastmcp_image_result(self):
        source = TOOL_PATH.read_text(encoding="utf-8")
        self.assertIn("from mcp.server.fastmcp import Image", source)
        self.assertIn("def read_local_image(", source)
        self.assertIn(") -> Image:", source)
        self.assertIn("return Image(data=image_path.read_bytes(), format=image_format)", source)
        self.assertNotIn("return Image(path=", source)

    def test_tool_is_registered_in_existing_mcp_registry(self):
        source = TOOL_PATH.read_text(encoding="utf-8")
        self.assertIn("from registry import mcp_for_unity_tool", source)
        self.assertIn('name="read_local_image"', source)


if __name__ == "__main__":
    unittest.main()
