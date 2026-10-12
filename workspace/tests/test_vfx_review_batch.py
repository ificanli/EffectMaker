from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_review_batch import select_review_batch


def _case(case_id: str, category: str, family: str, *, missing: int = 0, ignored: int = 0, bound: int = 1) -> dict:
    return {
        "case_id": case_id,
        "source": {"prefab_path": f"Assets/{case_id}.prefab", "source_category": [category], "effect_family_hint": family},
        "inputs": {
            "target_style_profile": {"family": "unknown"},
            "material_selection": {"material_count": 1, "materials": [{"editor_bound_texture_slot_count": bound}]},
        },
        "observations": {
            "observed_style_profile": {"family": "unknown"},
            "dependency_health": {"missing_dependency_count": missing, "ignored_dependency_count": ignored},
        },
        "training": {"supervision_status": "blocked_source_missing" if missing else "needs_render_and_style_annotation"},
    }


class VfxReviewBatchTests(unittest.TestCase):
    def test_selects_diverse_healthy_material_cases(self) -> None:
        rows = [
            _case("battle_fire", "battle", "fire"),
            _case("ui_unknown", "ui", "unclassified"),
            _case("scene_smoke", "scene", "smoke"),
            _case("enemy_ice", "enemy", "ice"),
            _case("missing", "battle", "fire", missing=1),
            _case("runtime", "battle", "shield", ignored=1),
            _case("no_texture", "battle", "lightning", bound=0),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases_path = root / "cases.jsonl"
            cases_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            output = select_review_batch(cases_path, root / "batch.json", batch_id="batch-001", count=4)
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["selected_count"], 4)
        self.assertEqual(set(payload["category_counts"]), {"battle", "ui", "scene", "enemy"})
        self.assertNotIn("missing", {record["case_id"] for record in payload["records"]})
        self.assertNotIn("runtime", {record["case_id"] for record in payload["records"]})


if __name__ == "__main__":
    unittest.main()
