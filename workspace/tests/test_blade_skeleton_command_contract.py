import unittest
from pathlib import Path


class BladeSkeletonCommandContractTests(unittest.TestCase):
    source = Path(
        "E:/UnityVFX/EffectDemo6.0/Assets/Editor/VfxOrangeSlashCommands.cs"
    ).read_text(encoding="utf-8")

    def test_reproduction_command_configures_four_named_layers(self):
        self.assertIn('configure_blade_reproduction_skeleton', self.source)
        for name in ("CoreBody", "DarkBase", "FastStrike_A", "FastStrike_B"):
            self.assertIn(f'"{name}"', self.source)

    def test_reproduction_command_uses_local_particle_space(self):
        self.assertIn("ParticleSystemSimulationSpace.Local", self.source)

    def test_reproduction_command_has_delayed_fast_strike_layers(self):
        self.assertIn("fastStrikeDelay", self.source)
        self.assertIn("0.10f", self.source)


if __name__ == "__main__":
    unittest.main()
