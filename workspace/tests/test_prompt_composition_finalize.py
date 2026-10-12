from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prompt_composition_finalize import finalize_composition


class PromptCompositionFinalizeTests(unittest.TestCase):
    def test_finalizes_real_composition_with_prompt_conditions_unscored(self) -> None:
        composition = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_composed_r001")
        retrieval = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_retrieval_r002/retrieval_manifest.json")
        self.assertTrue(composition.is_dir())
        with tempfile.TemporaryDirectory() as temporary:
            # Keep the real composition immutable: the finalizer writes a manifest, so invoke it once then compare its evidence.
            manifest_path = finalize_composition(composition, retrieval)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["candidate_count"], 6)
        self.assertEqual(manifest["technical_pass_count"], 6)
        self.assertEqual(manifest["human_aesthetic_labels_used"], 0)
        self.assertEqual(manifest["status"], "technical_pass_prompt_unscored")
        self.assertIn("style_requires_human_labels", manifest["prompt_conditions_unscored"])
        self.assertTrue(all(row["resource_clean"] for row in manifest["candidates"]))


if __name__ == "__main__":
    unittest.main()
