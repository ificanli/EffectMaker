import unittest
from pathlib import Path


class BladeCaptureCommandContractTests(unittest.TestCase):
    source = Path(
        "E:/UnityVFX/EffectDemo6.0/Assets/Editor/VfxOrangeSlashCommands.cs"
    ).read_text(encoding="utf-8")

    def test_blade_capture_command_resets_and_simulates_blade_root(self):
        self.assertIn("simulate_blade_reproduction_at_time", self.source)
        self.assertIn('GameObject.Find("BladeRoot")', self.source)
        self.assertIn("StopEmittingAndClear", self.source)
        self.assertIn("Simulate(Mathf.Max(0f, time)", self.source)


if __name__ == "__main__":
    unittest.main()
