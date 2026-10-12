from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prompt_composition_prepare import build_requests


class PromptCompositionPrepareTests(unittest.TestCase):
    def test_writes_execution_provenance_required_by_finalizer(self) -> None:
        retrieval = Path(
            "workspace/data/vfx_generation/runs/"
            "prompt_cartoon_blue_energy_impact_retrieval_r004_human_bound/retrieval_manifest.json"
        )
        unity_project = Path("UnityDemo/EffectDemo")
        execution_project = Path("workspace/unity-render-staging/EffectDemoPromptHumanR001")
        with tempfile.TemporaryDirectory() as temporary:
            request_path = build_requests(
                retrieval,
                Path(temporary) / "composition",
                unity_project=unity_project,
                execution_project=execution_project,
            )
            request = json.loads(request_path.read_text(encoding="utf-8"))

        self.assertEqual(request["execution_mode"], "selected")
        self.assertEqual(request["selection"]["kind"], "prompt_composition")
        self.assertTrue(request["curriculum_root"].endswith("material_trajectory_curriculum_r002"))
        self.assertEqual(request["unity_project"], unity_project.resolve().as_posix())
        self.assertEqual(request["execution_project"], execution_project.resolve().as_posix())
        self.assertEqual(request["selection"]["count"], 6)
        self.assertEqual(len(request["selection"]["candidate_ids"]), 6)


if __name__ == "__main__":
    unittest.main()
