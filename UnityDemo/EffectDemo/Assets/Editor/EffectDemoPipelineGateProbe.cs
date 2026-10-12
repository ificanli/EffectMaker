using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public static class EffectDemoPipelineGateProbe
{
    [Serializable]
    private sealed class GateResult
    {
        public bool render_pipeline_verified;
        public bool technical_frame_eligible;
        public bool image_sequence_training_eligible;
        public bool full_visual_training_eligible;
        public string visual_evidence_status;
    }

    public static void VerifyNullPipelineCannotQualify()
    {
        if (RenderPipelineManager.currentPipeline != null)
            throw new InvalidOperationException("Null-pipeline test requires a non-rendering batch session.");
        var output = Environment.GetEnvironmentVariable("EFFECTDEMO_PIPELINE_GATE_PROBE_OUTPUT");
        if (string.IsNullOrWhiteSpace(output))
            throw new InvalidOperationException("EFFECTDEMO_PIPELINE_GATE_PROBE_OUTPUT is required.");
        var gameObject = new GameObject("SyntheticPipelineGateTest");
        try
        {
            var controller = gameObject.AddComponent<EffectDemoRuntimeCaptureController>();
            var owner = controller.GetType();
            owner.GetField("requestManifest", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(controller,
                new EffectDemoRuntimeCaptureController.RequestManifest
                {
                    expected_render_pipeline_type = "no_active_srp",
                    run_id = "synthetic_gate_unit_test_not_training",
                    width = 1,
                    height = 1,
                });
            var request = new EffectDemoRuntimeCaptureController.RequestItem
            {
                candidate_id = "synthetic_gate_unit_test_not_training",
                capture_dir = Path.GetDirectoryName(output),
                capture_manifest_path = output,
            };
            var frame = NewNested(owner, "CaptureFrame");
            Set(frame, "valid", true);
            Set(frame, "pixel_metrics", NewNested(owner, "FramePixelMetrics"));
            var frames = (IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(frame.GetType()));
            frames.Add(frame);
            var context = NewNested(owner, "ContextEvidence");
            Set(context, "status", "standard_context_ready");
            var evidence = NewNested(owner, "CandidateRuntimeEvidence");
            Set(evidence, "Context", context);
            var timeline = new EffectDemoMaterialStateRecorder().CreateTimeline(request);
            timeline.summary.global_shader_state_status = "instrumented";
            // Synthetic inputs pass every other gate, isolating the actual producer predicate.
            owner.GetMethod("WriteManifest", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(controller,
                new[] { request, NewNested(owner, "DurationPlan"), frames, (object)0, timeline, evidence, null });
            var result = JsonUtility.FromJson<GateResult>(File.ReadAllText(output));
            if (!result.technical_frame_eligible || result.render_pipeline_verified
                || result.image_sequence_training_eligible || result.full_visual_training_eligible
                || result.visual_evidence_status != "render_pipeline_mismatch")
                throw new InvalidOperationException("Null pipeline incorrectly qualified the synthetic capture: " + output);
            Debug.Log("Null pipeline rejected by verification and both training gates: " + output);
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(gameObject);
        }
    }

    private static object NewNested(Type owner, string name)
    {
        return Activator.CreateInstance(owner.GetNestedType(name, BindingFlags.NonPublic), true);
    }

    private static void Set(object target, string field, object value)
    {
        target.GetType().GetField(field).SetValue(target, value);
    }
}
