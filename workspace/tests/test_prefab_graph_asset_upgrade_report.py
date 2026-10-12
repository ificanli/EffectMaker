from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_generation.prefab_graph_asset_upgrade_report import build_report


ROOT = Path(__file__).parents[2]


class PrefabGraphAssetUpgradeReportTests(unittest.TestCase):
    def test_report_requires_three_profiles_and_nine_valid_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upgrade = root / "upgrade"
            capture = root / "capture"
            candidates = []
            for profile in ("root_only", "particle_v1", "multi_particle"):
                candidate_id = f"pfg_{profile.replace('_', '0'):<20}"[:25]
                candidate_id = "pfg_" + (profile.encode("utf-8").hex() + "0" * 40)[:20]
                candidates.append({"candidate_id": candidate_id, "profile": profile, "graph_path": "graph.json", "asset_plan_path": "plan.json", "graph_status": "reconstructable", "parent_prefab_path": None})
                (upgrade / "compile_results").mkdir(parents=True, exist_ok=True)
                (capture / profile).mkdir(parents=True, exist_ok=True)
                (upgrade / "compile_results" / f"{profile}.json").write_text(json.dumps({"output_prefab_path": f"Assets/{profile}.prefab", "status": "pass", "source_prefab_read": False, "node_count": 1, "particle_system_count": 0, "generated_material_paths": [] if profile == "root_only" else ["Assets/a.mat"], "generated_texture_paths": [] if profile == "root_only" else ["Assets/a.asset"], "generated_shader_names": [] if profile == "root_only" else ["Common/ColorDefault"]}), encoding="utf-8")
                (capture / profile / "capture_manifest.json").write_text(json.dumps({"valid_frame_count": 9, "render_error": None, "frames": [{} for _ in range(9)]}), encoding="utf-8")
            (upgrade / "upgrade_manifest.json").parent.mkdir(parents=True, exist_ok=True)
            (upgrade / "upgrade_manifest.json").write_text(json.dumps({"candidates": candidates}), encoding="utf-8")
            output = build_report(upgrade, capture, root / "report.json")
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["candidate_count"], 3)


if __name__ == "__main__":
    unittest.main()
