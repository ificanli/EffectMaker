import json
import tempfile
import unittest
from pathlib import Path

from workspace.tools.vfx_library_index.clustering import build_clusters, classify_title


class ClusteringTests(unittest.TestCase):
    def test_classify_title_returns_explicit_theme_and_match(self):
        result = classify_title("Magic lightning energy ball.gif")
        self.assertEqual(result["theme"], "lightning")
        self.assertIn("lightning", result["matched_terms"])
        self.assertEqual(result["evidence_level"], "title-keyword")

    def test_noise_only_title_is_unclassified(self):
        result = classify_title("videoplayback (1).mp4")
        self.assertEqual(result["theme"], "unclassified")
        self.assertEqual(result["evidence_level"], "no-theme-evidence")

    def test_build_clusters_is_deterministic_and_traceable(self):
        records = [
            {"relative_path": "images/a_fire.gif", "media_id": "a", "media_type": "gif", "sha256": "1"},
            {"relative_path": "images/b_fire(1).gif", "media_id": "b", "media_type": "gif", "sha256": "1"},
            {"relative_path": "images/c_lightning.mp4", "media_id": "c", "media_type": "video", "sha256": "2"},
        ]
        clusters = build_clusters(records)
        self.assertEqual([c["theme"] for c in clusters], ["fire", "lightning"])
        self.assertEqual(clusters[0]["media_count"], 2)
        self.assertEqual(clusters[0]["media_ids"], ["a", "b"])
        self.assertEqual(clusters[0]["evidence_level"], "title-keyword")


if __name__ == "__main__":
    unittest.main()
