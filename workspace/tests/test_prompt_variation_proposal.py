from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from workspace.tools.vfx_generation.prompt_variation_proposal import (
    PARENT_CANDIDATE_ID,
    VARIANTS,
    prepare_blue_fast_impact_variant,
)


class PromptVariationProposalTests(unittest.TestCase):
    def test_prepares_direct_bound_blue_fast_impact_proposal(self) -> None:
        composition = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_composed_r005_human_bound")
        staging = Path("workspace/unity-render-staging/EffectDemoPromptHumanR001")
        with tempfile.TemporaryDirectory() as temporary:
            paths = prepare_blue_fast_impact_variant(
                composition,
                Path(temporary) / "variation",
                execution_project=staging,
            )
            spec = json.loads(paths["spec"].read_text(encoding="utf-8"))
            request = json.loads(paths["execution_requests"].read_text(encoding="utf-8"))
            proposal = json.loads(paths["proposal_manifest"].read_text(encoding="utf-8"))
            schema = json.loads(Path("workspace/data/vfx_generation/schemas/material_trajectory.schema.json").read_text(encoding="utf-8"))

        Draft202012Validator(schema).validate(spec)
        self.assertEqual(spec["trajectory_id"], VARIANTS["blue-fast-explosion-ground"]["variant_id"])
        self.assertEqual(proposal["parent_candidate_id"], PARENT_CANDIDATE_ID)
        self.assertEqual(proposal["mutation_plan"]["training_status"], "proposal_only_not_training")
        self.assertEqual(request["execution_mode"], "selected")
        self.assertEqual(request["selection"]["kind"], "prompt_variation_proposal")
        self.assertTrue(request["execution_project"].endswith("EffectDemoPromptHumanR001"))
        self.assertEqual([track["property_name"] for track in spec["parameter_tracks"]], ["_Main_SolidColor", "_Main_Color", "_Distort_Dissolve_Intensity"])
        self.assertEqual(len(request["requests"][0]["track_clamps"]), len(spec["parameter_tracks"]))

    def test_can_target_the_explosion_core_renderer_material(self) -> None:
        composition = Path("workspace/data/vfx_generation/runs/prompt_cartoon_blue_energy_impact_composed_r005_human_bound")
        with tempfile.TemporaryDirectory() as temporary:
            paths = prepare_blue_fast_impact_variant(composition, Path(temporary) / "variation", variant_key="blue-fast-explosion-core")
            proposal = json.loads(paths["proposal_manifest"].read_text(encoding="utf-8"))
            spec = json.loads(paths["spec"].read_text(encoding="utf-8"))
            request = json.loads(paths["execution_requests"].read_text(encoding="utf-8"))

        self.assertEqual(proposal["proposal_id"], VARIANTS["blue-fast-explosion-core"]["variant_id"])
        self.assertEqual(proposal["mutation_plan"]["target_renderer_role"], "explosion_core_burst_start_size_6")
        self.assertTrue(spec["source_asset"]["material_path"].endswith("Mat_daodan_01.mat"))
        self.assertEqual(len(spec["particle_color_tracks"]), 10)
        self.assertTrue(all(track["disable_color_over_lifetime"] for track in spec["particle_color_tracks"]))
        self.assertEqual(len(spec["material_property_tracks"]), 20)
        self.assertIn("particle_color_changed", spec["expected_signals"])
        self.assertEqual(len(request["requests"][0]["track_clamps"]), 1)


if __name__ == "__main__":
    unittest.main()
