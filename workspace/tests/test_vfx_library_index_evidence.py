import unittest

from workspace.tools.vfx_library_index.evidence import select_evidence_points


class EvidenceTests(unittest.TestCase):
    def test_long_media_has_start_middle_end_points(self):
        points = select_evidence_points(10.0, None, "video")
        self.assertEqual([label for label, _ in points], ["start", "middle", "end"])
        self.assertEqual(points[1][1], 5.0)

    def test_short_media_has_one_representative_point(self):
        self.assertEqual(select_evidence_points(0.2, None, "gif"), [("representative", 0.1)])

    def test_unknown_gif_uses_unresolved_representative(self):
        self.assertEqual(select_evidence_points(None, None, "gif"), [("representative", None)])

    def test_unknown_video_has_no_fake_timestamp(self):
        self.assertEqual(select_evidence_points(None, None, "video"), [])


if __name__ == "__main__":
    unittest.main()
