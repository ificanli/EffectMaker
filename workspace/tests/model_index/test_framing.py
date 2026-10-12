import math
import unittest

from workspace.tools.model_index.framing import frame_parameters


class FramingTests(unittest.TestCase):
    def test_world_bounds_and_view_frame_are_deterministic(self):
        bounds = {"min": [-2.0, -1.0, 0.0], "max": [2.0, 3.0, 4.0]}
        first = frame_parameters(bounds, "front")
        self.assertEqual(first, frame_parameters(bounds, "front"))
        self.assertEqual(first["target"], [0.0, 1.0, 2.0])
        self.assertGreater(first["distance"], 0)
        self.assertGreaterEqual(first["ortho_scale"], math.sqrt(4 * 4 + 4 * 4 + 4 * 4))
        self.assertEqual(frame_parameters(bounds, "side")["direction"], [1.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
