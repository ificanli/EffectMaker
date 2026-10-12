using UnityEngine;

public sealed class EffectDemoMaterialStateProbeDriver : MonoBehaviour, IEffectDemoCaptureTimingProvider
{
    private Renderer targetRenderer;
    private Material primaryMaterial;
    private Material alternateMaterial;
    private Texture2D primaryTexture;
    private Texture2D alternateTexture;
    private MaterialPropertyBlock propertyBlock;
    private float enabledAt;
    private bool initialized;

    public float CaptureDurationSeconds => 1f;

    private void Awake()
    {
        targetRenderer = GetComponent<Renderer>();
        InitializeAssets();
    }

    private void OnEnable()
    {
        InitializeAssets();
        ResetState();
    }

    private void Update()
    {
        var elapsed = Mathf.Max(0f, Time.time - enabledAt);
        var progress = Mathf.Clamp01(elapsed);
        var activeMaterial = elapsed >= 0.6f ? alternateMaterial : primaryMaterial;
        if (targetRenderer.sharedMaterial != activeMaterial)
            targetRenderer.sharedMaterial = activeMaterial;

        activeMaterial.SetTexture("_MainTex", elapsed >= 0.3f ? alternateTexture : primaryTexture);
        activeMaterial.SetFloat("_FlowSpeed", progress * 2f);
        EffectDemoDynamicShaderStateTracker.SetGlobalFloat("_EffectDemoTrackedGlobalAlpha", Mathf.Lerp(1f, 0.45f, progress), nameof(EffectDemoMaterialStateProbeDriver));
        if (elapsed >= 0.4f)
            activeMaterial.EnableKeyword("PROBE_FLOW_ON");
        else
            activeMaterial.DisableKeyword("PROBE_FLOW_ON");

        propertyBlock.Clear();
        propertyBlock.SetFloat("_DissolveAmount", progress * 0.8f);
        propertyBlock.SetColor("_TintColor", Color.Lerp(new Color(0.2f, 0.8f, 1f, 1f), new Color(1f, 0.2f, 0.05f, 1f), progress));
        EffectDemoDynamicShaderStateTracker.SetPropertyBlock(targetRenderer, propertyBlock, 0, nameof(EffectDemoMaterialStateProbeDriver), "_DissolveAmount", "_TintColor");
    }

    private void InitializeAssets()
    {
        if (initialized)
            return;
        var shader = Shader.Find("Hidden/EffectDemo/MaterialStateProbe");
        if (shader == null)
            throw new MissingReferenceException("Hidden/EffectDemo/MaterialStateProbe shader was not found.");
        primaryTexture = CreateTexture("ProbeTextureBlue", new Color(0.1f, 0.65f, 1f, 1f), Color.white);
        alternateTexture = CreateTexture("ProbeTextureOrange", new Color(1f, 0.2f, 0.03f, 1f), new Color(1f, 0.9f, 0.2f, 1f));
        primaryMaterial = new Material(shader) { name = "ProbePrimary_Runtime" };
        alternateMaterial = new Material(shader) { name = "ProbeAlternate_Runtime" };
        primaryMaterial.SetTexture("_MainTex", primaryTexture);
        alternateMaterial.SetTexture("_MainTex", alternateTexture);
        propertyBlock = new MaterialPropertyBlock();
        initialized = true;
    }

    private void ResetState()
    {
        enabledAt = Time.time;
        primaryMaterial.DisableKeyword("PROBE_FLOW_ON");
        alternateMaterial.DisableKeyword("PROBE_FLOW_ON");
        primaryMaterial.SetTexture("_MainTex", primaryTexture);
        alternateMaterial.SetTexture("_MainTex", alternateTexture);
        targetRenderer.sharedMaterial = primaryMaterial;
        EffectDemoDynamicShaderStateTracker.SetGlobalFloat("_EffectDemoTrackedGlobalAlpha", 1f, nameof(EffectDemoMaterialStateProbeDriver));
        propertyBlock.Clear();
        propertyBlock.SetFloat("_DissolveAmount", 0f);
        propertyBlock.SetColor("_TintColor", new Color(0.2f, 0.8f, 1f, 1f));
        EffectDemoDynamicShaderStateTracker.SetPropertyBlock(targetRenderer, propertyBlock, 0, nameof(EffectDemoMaterialStateProbeDriver), "_DissolveAmount", "_TintColor");
    }

    private static Texture2D CreateTexture(string name, Color left, Color right)
    {
        var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false) { name = name, wrapMode = TextureWrapMode.Repeat };
        texture.SetPixels(new[] { left, right, right, left });
        texture.Apply(false, false);
        return texture;
    }

    private void OnDestroy()
    {
        if (primaryMaterial != null) Destroy(primaryMaterial);
        if (alternateMaterial != null) Destroy(alternateMaterial);
        if (primaryTexture != null) Destroy(primaryTexture);
        if (alternateTexture != null) Destroy(alternateTexture);
    }
}

public static class EffectDemoMaterialStateProbeFactory
{
    public const string PrefabPath = "__effectdemo_material_state_probe__";

    public static GameObject Create(bool startInactive = false)
    {
        var root = GameObject.CreatePrimitive(PrimitiveType.Quad);
        root.name = "EffectDemoMaterialStateProbe";
        if (startInactive)
            root.SetActive(false);
        var collider = root.GetComponent<Collider>();
        if (collider != null)
            Object.DestroyImmediate(collider);
        root.transform.localScale = new Vector3(3f, 3f, 3f);
        root.AddComponent<EffectDemoMaterialStateProbeDriver>();
        return root;
    }
}
