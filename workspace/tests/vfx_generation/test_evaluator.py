from __future__ import annotations

import unittest

from workspace.tools.vfx_generation.evaluator import register_family_scorer, score_candidate, score_render_metrics


class VfxEvaluatorTests(unittest.TestCase):
    def test_slash_score_is_a_spec_prior_when_not_rendered(self) -> None:
        spec = {
            "effect_family": "slash",
            "adapter": {
                "evaluation_metrics": ["sharpness", "attack_direction", "silhouette_readability"],
                "topology": {
                    "arc_topology": "single_sweep",
                    "attack_direction": "diagonal",
                    "control_point_count": 5,
                    "asymmetry": 0.62,
                },
                "shape": {
                    "tip_shape": "sharp",
                    "width_profile": "tapered",
                    "edge_breakup": 0.22,
                    "residual_flow": "along_attack",
                },
            },
        }

        result = score_candidate(spec)

        self.assertEqual(result["schema_version"], "candidate_score.v1")
        self.assertEqual(result["provenance"]["specialized_scores"], "spec_parameters")
        self.assertEqual(result["provenance"]["render_scores"], "not_rendered")
        self.assertIsNone(result["render_score"])
        self.assertIsNone(result["overall_score"])
        self.assertGreater(result["spec_prior_score"], 80.0)
        self.assertIn("sharpness", result["specialized_scores"])
        self.assertFalse(result["provenance"]["final_visual_acceptance"])

    def test_render_scores_use_measurable_metrics_only(self) -> None:
        metrics = {
            "visible_area_ratio_peak": 0.12,
            "mean_luminance_peak": 0.30,
            "overexposed_ratio_peak": 0.02,
            "frame_delta_mean": 0.012,
            "particle_count_peak": None,
            "draw_call_count": None,
        }

        result = score_render_metrics(
            metrics,
            rendered=True,
            render_context={
                "scene_match": True,
                "camera_match": True,
                "resolution_match": True,
            },
        )

        self.assertGreater(result["readability"], 0.0)
        self.assertGreater(result["timing"], 0.0)
        self.assertGreater(result["material"], 0.0)
        self.assertEqual(result["camera_readability"], 100.0)
        self.assertIsNone(result["layer_separation"])

    def test_fire_dimensions_do_not_use_slash_rules(self) -> None:
        spec = {
            "effect_family": "fire",
            "adapter": {
                "evaluation_metrics": ["turbulence", "root_brightness", "afterburn_quality"],
                "topology": {"edge_breakup": 0.7},
                "behavior": {
                    "turbulence": 0.8,
                    "root_brightness": 0.9,
                    "ember_behavior": "rising_sparks",
                    "smoke_afterburn": "soft_residue",
                },
            },
        }

        result = score_candidate(spec)

        self.assertIn("turbulence", result["specialized_scores"])
        self.assertIn("root_brightness", result["specialized_scores"])
        self.assertNotIn("sharpness", result["specialized_scores"])
        self.assertGreater(result["spec_prior_score"], 80.0)

    def test_unknown_family_is_explicitly_unscored(self) -> None:
        result = score_candidate(
            {
                "effect_family": "smoke",
                "adapter": {"evaluation_metrics": ["density"]},
            }
        )

        self.assertEqual(result["specialized_scores"], {"density": None})
        self.assertIsNone(result["spec_prior_score"])
        self.assertIn("density", result["unscored_dimensions"])

    def test_all_declared_families_have_explicit_dimension_contracts(self) -> None:
        for family in ("slash", "fire", "lightning", "shield", "magic_circle", "smoke", "explosion", "water"):
            result = score_candidate({"effect_family": family, "adapter": {}})
            self.assertTrue(result["specialized_scores"])
            self.assertEqual(result["provenance"]["specialized_scores"], "spec_parameters")

    def test_custom_family_scorer_can_be_registered(self) -> None:
        register_family_scorer(
            "test_family",
            lambda adapter, dimensions: {dimension: 42.0 for dimension in dimensions},
            ("custom_metric",),
        )

        result = score_candidate(
            {
                "effect_family": "test_family",
                "adapter": {"evaluation_metrics": ["custom_metric"]},
            }
        )

        self.assertEqual(result["specialized_scores"], {"custom_metric": 42.0})


if __name__ == "__main__":
    unittest.main()
