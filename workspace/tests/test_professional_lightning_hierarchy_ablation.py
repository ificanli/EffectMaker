from __future__ import annotations

import copy
import unittest

from workspace.tools.vfx_generation.lightning_family_generator import create_layered_lightning
from workspace.tools.vfx_generation.professional_lightning_hierarchy_ablation import _paired_visual_metrics, create_equal_branch_ablation


class ProfessionalLightningHierarchyAblationTests(unittest.TestCase):
    def test_ablation_only_equalizes_branch_size_and_alpha(self) -> None:
        source = create_layered_lightning("x", 7, 0)
        original = copy.deepcopy(source)
        baseline, changed = create_equal_branch_ablation(source)
        roles = {node["node_id"]: node["role"] for node in baseline["nodes"]}
        particles = {roles[row["node_id"]]: row for row in baseline["components"]["particle_systems"]}
        self.assertEqual(particles["core"]["parameters"]["start_size_max"], particles["support"]["parameters"]["start_size_max"])
        self.assertEqual(particles["core"]["parameters"]["start_color_rgba"][3], particles["support"]["parameters"]["start_color_rgba"][3])
        self.assertEqual(set(changed), {"support.parameters.start_size_max", "support.parameters.start_color_rgba[3]"})
        self.assertEqual(source, original)

    def test_visual_metrics_compare_matching_times(self) -> None:
        equal = {"frames": [{"time_seconds": 0.0, "visible_area_ratio": 0.1, "visible_width_ratio": 0.8, "high_luma_width_ratio": 0.5}, {"time_seconds": 0.1, "visible_area_ratio": 0.1, "visible_width_ratio": 0.6, "high_luma_width_ratio": 0.3}]}
        dominant = {"frames": [{"time_seconds": 0.0, "visible_area_ratio": 0.1, "visible_width_ratio": 0.72, "high_luma_width_ratio": 0.35}, {"time_seconds": 0.1, "visible_area_ratio": 0.1, "visible_width_ratio": 0.54, "high_luma_width_ratio": 0.28}]}
        metrics = _paired_visual_metrics(equal, dominant)
        self.assertEqual(metrics["paired_frame_count"], 2.0)
        self.assertAlmostEqual(metrics["paired_max_high_luma_width_reduction"], 0.15)
        self.assertAlmostEqual(metrics["paired_median_visible_width_retained"], 0.9)


if __name__ == "__main__":
    unittest.main()
