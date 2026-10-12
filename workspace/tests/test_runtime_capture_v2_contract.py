from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class RuntimeCaptureV2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.controller = (ROOT / "UnityDemo/EffectDemo/Assets/VFXCapture/EffectDemoRuntimeCaptureController.cs").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "UnityDemo/EffectDemo/Assets/Editor/EffectDemoRuntimeCaptureBootstrap.cs").read_text(encoding="utf-8")
        cls.recorder = (ROOT / "UnityDemo/EffectDemo/Assets/VFXCapture/EffectDemoMaterialStateRecorder.cs").read_text(encoding="utf-8")

    def test_bootstrap_passes_asset_reference_instead_of_reusing_instance(self) -> None:
        self.assertIn("prefab_asset = prefab", self.bootstrap)
        self.assertIn("use_material_state_probe_factory", self.bootstrap)
        self.assertIn("runtime_factory_id", self.bootstrap)
        self.assertNotIn("PrefabUtility.InstantiatePrefab", self.bootstrap)

    def test_capture_uses_three_distinct_runtime_instances(self) -> None:
        self.assertIn("BoundsProbeInstanceId = boundsProbe.GetInstanceID()", self.controller)
        self.assertIn("CameraProbeInstanceId = cameraProbe.GetInstanceID()", self.controller)
        self.assertIn("CaptureInstanceId = captureRoot.GetInstanceID()", self.controller)
        self.assertIn("fresh_bounds_probe_then_fresh_camera_probe_then_fresh_capture_instance", self.controller)

    def test_camera_selection_renders_front_side_and_top(self) -> None:
        self.assertIn('Name = "front"', self.controller)
        self.assertIn('Name = "side"', self.controller)
        self.assertIn('Name = "top"', self.controller)
        self.assertIn("RenderPixelMetrics(cameraEvaluationTarget", self.controller)
        self.assertIn("border_touch_ratio", self.controller)
        self.assertIn("center_offset_normalized", self.controller)

    def test_controlled_pairs_can_force_the_same_camera_view(self) -> None:
        self.assertIn("forced_camera_view", self.controller)
        self.assertIn('"forced_request_view"', self.controller)
        self.assertIn('"forced_request_view_fixed_frame"', self.controller)
        self.assertIn("forced_orthographic_size", self.controller)
        self.assertIn("captureCamera.orthographicSize = request.forced_orthographic_size", self.controller)
        self.assertIn("Unsupported forced camera view", self.controller)

    def test_subject_framing_uses_mesh_bounds_and_profile_views(self) -> None:
        self.assertIn("AccumulateSubjectBounds", self.controller)
        self.assertIn("ParticleSystemRenderMode.Mesh", self.controller)
        self.assertIn('string.Equals(captureCategory, "slash"', self.controller)
        self.assertIn('AddCameraView(views, $"subject_normal_{index}"', self.controller)
        self.assertIn('fit_basis = useSubjectBounds ? "subject_bounds" : "accumulated_bounds"', self.controller)
        self.assertIn("request.force_orthographic || IsOrthographicProfile", self.controller)
        self.assertIn("captureCamera.orthographicSize", self.controller)

    def test_short_subject_duration_uses_burst_lifetime_and_finer_sampling(self) -> None:
        self.assertIn("EstimateSubjectDuration", self.controller)
        self.assertIn("main.loop && !continuousEmission", self.controller)
        self.assertIn("subject_duration_override", self.controller)
        self.assertIn("short_effect_target_intervals", self.controller)
        self.assertIn("component_duration_seconds", self.controller)

    def test_standard_context_and_evidence_are_explicit(self) -> None:
        self.assertIn('cameraObject.tag = "MainCamera"', self.controller)
        self.assertIn("VFXCaptureEventSystem", self.controller)
        self.assertIn("VFXCaptureGroundAnchor", self.controller)
        self.assertIn("VFXCaptureTarget", self.controller)
        self.assertIn("source_scripts_excluded", self.controller)
        self.assertIn("full_visual_training_eligible", self.controller)
        self.assertIn("controlled_custom_script_count", self.controller)
        self.assertIn("unknown_custom_script_count", self.controller)
        self.assertIn("IEffectDemoCaptureTimingProvider", self.controller)

    def test_timing_and_random_seed_evidence_are_recorded(self) -> None:
        self.assertIn("max_duration_seconds = 8f", self.controller)
        self.assertIn("Time.realtimeSinceStartupAsDouble", self.controller)
        self.assertIn("unity_frame_count", self.controller)
        self.assertIn("useAutoRandomSeed = false", self.controller)
        self.assertIn("duration_clamped", self.controller)
        self.assertIn("pendingLateCaptureNotBeforeSimulationTime", self.controller)
        self.assertIn("Time.captureDeltaTime", self.controller)

    def test_unknown_material_state_is_not_silently_complete(self) -> None:
        self.assertIn("has_unenumerated_property_block_values", self.recorder)
        self.assertIn("EffectDemoDynamicShaderStateTracker.CaptureGlobals", self.recorder)
        self.assertIn('"not_instrumented_unknown_shader"', (ROOT / "UnityDemo/EffectDemo/Assets/VFXCapture/EffectDemoDynamicShaderStateTracker.cs").read_text(encoding="utf-8"))
        self.assertIn("Shader global properties are not instrumented", self.controller)

    def test_controlled_global_and_mpb_writes_are_explicitly_tracked(self) -> None:
        tracker = (ROOT / "UnityDemo/EffectDemo/Assets/VFXCapture/EffectDemoDynamicShaderStateTracker.cs").read_text(encoding="utf-8")
        probe = (ROOT / "UnityDemo/EffectDemo/Assets/VFXCapture/EffectDemoMaterialStateProbeDriver.cs").read_text(encoding="utf-8")
        self.assertIn("RequiredGlobalsByShader", tracker)
        self.assertIn("SetGlobalFloat", tracker)
        self.assertIn("IsPropertyBlockFullyTracked", tracker)
        self.assertIn("EffectDemoDynamicShaderStateTracker.SetPropertyBlock", probe)
        self.assertIn("EffectDemoDynamicShaderStateTracker.Reset()", self.controller)
        self.assertIn("controlled_script_duration", self.controller)

    def test_error_magenta_is_a_technical_material_render_failure(self) -> None:
        self.assertIn("unity_error_magenta_ratio", self.controller)
        self.assertIn("unity_error_magenta_pixel_count", self.controller)
        self.assertIn("unity_error_magenta_visible_ratio", self.controller)
        self.assertIn("material_render_error", self.controller)
        self.assertIn("errorMagentaVisibleRatio >= 0.5f", self.controller)
        self.assertIn("color.r >= 250 && color.g <= 8 && color.b >= 250", self.controller)
        self.assertIn("materialRenderErrorFrameCount", self.controller)
        self.assertIn('visualEvidenceStatus = !technicalFrameEligible ? "technical_failure"', self.controller)
        self.assertIn('? "material_render_error"', self.controller)

    def test_pipeline_instance_must_match_before_training(self) -> None:
        self.assertIn("RenderPipelineManager.currentPipeline", self.controller)
        self.assertIn("pipelineVerified = pipelineInstance != null &&", self.controller)
        self.assertIn("expected_render_pipeline_type", self.controller)
        self.assertIn("render_pipeline_instance_type = pipelineInstanceType", self.controller)
        self.assertIn("render_pipeline_verified = pipelineVerified", self.controller)
        self.assertIn("imageSequenceEligible = pipelineVerified &&", self.controller)
        self.assertIn('? "render_pipeline_mismatch"', self.controller)

    def test_capture_background_can_reveal_black_occlusion(self) -> None:
        self.assertIn('public float[] background_color_rgba', self.controller)
        self.assertIn('requestManifest.background_color_rgba', self.controller)

    def test_duplicate_shader_properties_do_not_abort_material_timeline(self) -> None:
        self.assertIn("if (!names.Add(name))", self.recorder)
        self.assertIn("LastPropertyByName", self.recorder)
        self.assertIn(".GroupBy(item => item.property_name, StringComparer.Ordinal)", self.recorder)


if __name__ == "__main__":
    unittest.main()
