using UnityEngine;

public sealed class EffectDemoMovingCaptureProbeDriver : MonoBehaviour
{
    private Material runtimeMaterial;
    private float enabledAt;

    private void Awake()
    {
        var shader = Shader.Find("Hidden/EffectDemo/MaterialStateProbe");
        if (shader == null)
            throw new MissingReferenceException("Hidden/EffectDemo/MaterialStateProbe shader was not found.");
        runtimeMaterial = new Material(shader) { name = "MovingCaptureProbe_Runtime" };
        runtimeMaterial.SetColor("_TintColor", new Color(0.05f, 0.9f, 1f, 1f));
        Shader.SetGlobalFloat("_EffectDemoTrackedGlobalAlpha", 1f);
        GetComponent<Renderer>().sharedMaterial = runtimeMaterial;
    }

    private void OnEnable()
    {
        enabledAt = Time.time;
        Shader.SetGlobalFloat("_EffectDemoTrackedGlobalAlpha", 1f);
        transform.localPosition = new Vector3(-2f, 0f, 0f);
    }

    private void Update()
    {
        var progress = Mathf.Clamp01(Time.time - enabledAt);
        transform.localPosition = new Vector3(Mathf.Lerp(-2f, 2f, progress), Mathf.Sin(progress * Mathf.PI) * 0.5f, 0f);
    }

    private void OnDestroy()
    {
        if (runtimeMaterial != null)
            Destroy(runtimeMaterial);
    }
}

public static class EffectDemoRuntimeCaptureRegressionProbeFactory
{
    public const string MovingPath = "__effectdemo_capture_moving_probe__";

    public static bool CanCreate(string path)
    {
        return path == MovingPath;
    }

    public static GameObject Create(string path, bool startInactive)
    {
        if (path != MovingPath)
            return null;
        var root = GameObject.CreatePrimitive(PrimitiveType.Quad);
        root.name = "EffectDemoMovingCaptureProbe";
        if (startInactive)
            root.SetActive(false);
        var collider = root.GetComponent<Collider>();
        if (collider != null)
            Object.DestroyImmediate(collider);
        root.transform.localScale = new Vector3(0.65f, 0.65f, 0.65f);
        root.AddComponent<EffectDemoMovingCaptureProbeDriver>();
        return root;
    }
}
