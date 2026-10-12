using UnityEngine;

public static class VerificationSceneBuilder
{
    public static void Build()
    {
        var scene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
            UnityEditor.SceneManagement.NewSceneSetup.EmptyScene,
            UnityEditor.SceneManagement.NewSceneMode.Single);

        var cameraObject = new GameObject("VerificationCamera");
        var camera = cameraObject.AddComponent<Camera>();
        camera.transform.position = new Vector3(0f, 2f, -8f);
        camera.transform.LookAt(Vector3.zero);
        camera.fieldOfView = 45f;

        var lightObject = new GameObject("VerificationLight");
        var light = lightObject.AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1f;
        light.transform.rotation = Quaternion.Euler(35f, -30f, 0f);

        var environment = GameObject.CreatePrimitive(PrimitiveType.Plane);
        environment.name = "EnvironmentReference";
        environment.transform.localScale = Vector3.one * 5f;

        var effectRoot = new GameObject("EffectRoot");
        var stageNames = new[] { "Prelude", "Core", "Burst", "Residue" };
        foreach (var stageName in stageNames)
        {
            var stage = new GameObject(stageName);
            stage.transform.SetParent(effectRoot.transform, false);
        }

        var actor = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        actor.name = "ActorReference";
        actor.transform.position = new Vector3(0f, 1f, 0f);

        UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene, "Assets/Scenes/VerificationBaseline.unity");
        Debug.Log("VERIFICATION_SCENE_BUILT");
    }
}
