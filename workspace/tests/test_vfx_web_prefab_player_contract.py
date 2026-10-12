import unittest
from pathlib import Path


PROJECT_ROOT = Path("E:/Unity特效人工智能学习/UnityDemo/EffectDemo")
FEATURE_ROOT = PROJECT_ROOT / "Assets/Art/VFX/WebPrefabPlayer"
TEMPLATE_ROOT = PROJECT_ROOT / "Assets/WebGLTemplates/VfxPrefabPlayer"


class VfxWebPrefabPlayerContractTests(unittest.TestCase):
    player_source = (FEATURE_ROOT / "Runtime/VfxWebPlayer.cs").read_text(
        encoding="utf-8"
    )
    builder_source = (FEATURE_ROOT / "Editor/VfxWebPlayerBuilder.cs").read_text(
        encoding="utf-8"
    )
    template_source = (TEMPLATE_ROOT / "index.html").read_text(encoding="utf-8")
    app_source = (TEMPLATE_ROOT / "TemplateData/app.js").read_text(
        encoding="utf-8"
    )

    def test_runtime_instantiates_and_controls_real_prefabs(self):
        self.assertIn("Instantiate(currentEntry.Prefab", self.player_source)
        self.assertIn("particleSystem.Play(true)", self.player_source)
        self.assertIn("public void SelectEffect(string id)", self.player_source)
        self.assertIn("public void Replay(string unused)", self.player_source)
        self.assertIn("public void FitView(string unused)", self.player_source)
        self.assertIn("Application.absoluteURL", self.player_source)
        self.assertIn('GetQueryParameter(Application.absoluteURL, "catalogId")', self.player_source)

    def test_webgl_builder_targets_effectdemo_2022_training_assets(self):
        self.assertIn('"Assets/VFXSourceIngest/Trains/Trains_FX_All_001"', self.builder_source)
        self.assertIn("BuildTarget.WebGL", self.builder_source)
        self.assertIn('PlayerSettings.WebGL.template = "PROJECT:VfxPrefabPlayer"', self.builder_source)
        self.assertIn("WebGLCompressionFormat.Disabled", self.builder_source)
        self.assertIn("DefaultPreviewLimit = 5", self.builder_source)
        self.assertIn("does not belong to EffectDemo 2022", self.builder_source)
        self.assertNotIn("E:/UnityVFX", self.builder_source)

    def test_page_uses_unity_canvas_and_send_message_controls(self):
        self.assertIn('id="unity-canvas"', self.template_source)
        self.assertIn("createUnityInstance", self.template_source)
        self.assertIn('SendMessage("VfxWebPlayer"', self.app_source)
        self.assertIn('send("SelectEffect"', self.app_source)
        self.assertIn('query.get("catalogId")', self.app_source)
        self.assertIn('type: "vfx-web-selected"', self.app_source)
        self.assertNotIn("<video", self.template_source)

    def test_web_bridge_returns_catalog_and_runtime_metrics(self):
        self.assertIn("VfxWebDispatch", self.player_source)
        self.assertIn('type = "catalog"', self.player_source)
        self.assertIn('type = "runtime"', self.player_source)
        self.assertIn("liveParticles", self.player_source)
        self.assertIn("materialStateFingerprint", self.player_source)
        self.assertIn("webglMaterialStateChanges", self.player_source)
        self.assertIn("UNITY_6000_0_OR_NEWER", self.player_source)
        self.assertIn("GetInstanceID()", self.player_source)

    def test_training_review_links_material_timeline_and_feedback(self):
        catalog_source = (FEATURE_ROOT / "Runtime/VfxWebCatalog.cs").read_text(encoding="utf-8")
        self.assertIn("MaterialTimelinePath", catalog_source)
        self.assertIn("TrainingCaseId", catalog_source)
        self.assertIn("vfx_web_training_review_bundle.v1", self.builder_source)
        self.assertIn('id="material-key-times"', self.template_source)
        self.assertIn('id="save-review-button"', self.template_source)
        self.assertIn('schema_version: "human_feedback.v1"', self.app_source)
        self.assertIn('evidence_role: "dynamic_human_review_only"', self.app_source)
        self.assertIn('send("ReplayAt"', self.app_source)
        self.assertIn("Unity 2022 Web", self.template_source)


if __name__ == "__main__":
    unittest.main()
