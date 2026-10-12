import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


WORKSPACE = Path(__file__).resolve().parents[1]
DATA = WORKSPACE / "data/vfx_generation"


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.references = []
        self.in_report = False
        self.report_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if attrs.get("id") == "report":
            self.in_report = True
        if self.in_report or tag in {"script", "link"}:
            value = attrs.get("src") or attrs.get("href")
            if value:
                self.references.append(value)

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_report = False

    def handle_data(self, data):
        if self.in_report:
            self.report_text.append(data)


class ReportPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (WORKSPACE / "vfx_generation_architecture.html").read_text(encoding="utf-8")
        cls.page = ReportParser()
        cls.page.feed(cls.html)
        cls.text = " ".join(cls.page.report_text)

    def test_unique_ids_and_preserved_architecture_anchors(self):
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        for name in ("report", "report-case", "report-next", "architecture", "start", "flow",
                     "spec", "evidence", "inputs", "tools", "roles", "automation", "transfer", "status", "next"):
            self.assertIn(name, self.page.ids)

    def test_report_links_images_and_runtime_assets_exist_under_server_root(self):
        for reference in self.page.references:
            with self.subTest(reference=reference):
                url = urlsplit(reference)
                self.assertFalse(url.scheme, "The report must not need remote runtime dependencies")
                if not url.path:
                    self.assertIn(url.fragment, self.page.ids)
                    continue
                target = (WORKSPACE / unquote(url.path)).resolve()
                self.assertTrue(target.is_relative_to(WORKSPACE))
                self.assertTrue(target.is_file(), str(target))

    def test_historical_statistics_match_the_named_manifests(self):
        graph = json.loads((DATA / "datasets/prefab_graph_full_r002/dataset_manifest.json").read_text())
        assets = json.loads((DATA / "asset_registry/asset_registry_r003/registry_manifest.json").read_text())
        tiers = json.loads((DATA / "datasets/prefab_five_layer_full_r009/dataset_manifest.json").read_text())
        self.assertIn(f'{graph["example_count"]:,}', self.text)
        for field in ("texture_count", "shader_count", "material_count"):
            self.assertIn(f'{assets["counts"][field]:,}', self.text)
        self.assertEqual(tiers["tier_counts"]["human_gold"], 32)
        self.assertIn("2026-09-02", self.text)
        self.assertIn("2026-09-03", self.text)

    def test_case_is_not_presented_as_a_trained_positive(self):
        case = json.loads((DATA / "generated/tutorial_lightning_fixed_color_r003/calibration_manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(case["training_eligibility"]["controller_sft"])
        self.assertFalse(case["training_eligibility"]["positive_generation_supervision"])
        self.assertIn(case["prompt"], self.text)
        self.assertIn("非训练模型从零生成", self.text)
        self.assertIn("非实时 WebGL", self.text)
        self.assertIn("不进入正式正向 SFT", self.text)

    def test_case_pixel_frames_and_report_counts_agree(self):
        report = json.loads((DATA / "generated/tutorial_lightning_fixed_color_r003/tutorial_color_report.json").read_text())
        self.assertEqual(report["status"], "pass_tutorial_color_mechanism_only")
        self.assertEqual(sum(case["valid_frames"] for case in report["cases"].values()), 123)
        self.assertTrue(all(report["gates"].values()))

    def test_local_lucide_icons_have_license_and_valid_svg(self):
        folder = WORKSPACE / "vfx_guide_assets/icons"
        self.assertIn("ISC", (folder / "LICENSE").read_text())
        for icon in ("play", "pause", "chevron-left", "chevron-right", "rotate-ccw", "copy"):
            root = ElementTree.parse(folder / f"{icon}.svg").getroot()
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")


if __name__ == "__main__":
    unittest.main()
