using System.IO;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
internal static class EffectDemoInspectorRecovery
{
    private const string MarkerRelativePath = "Library/VFXSourceIngest/reset-inspector-once.marker";

    static EffectDemoInspectorRecovery()
    {
        EditorApplication.delayCall += RecoverOnce;
    }

    private static void RecoverOnce()
    {
        var projectRoot = Directory.GetParent(Application.dataPath).FullName;
        var markerPath = Path.Combine(projectRoot, MarkerRelativePath);
        if (!File.Exists(markerPath))
            return;

        File.Delete(markerPath);
        foreach (var window in Resources.FindObjectsOfTypeAll<EditorWindow>())
        {
            if (window.GetType().FullName == "UnityEditor.InspectorWindow")
                window.Close();
        }
        EditorApplication.delayCall += OpenFreshInspector;
    }

    private static void OpenFreshInspector()
    {
        EditorApplication.ExecuteMenuItem("Window/General/Inspector");
    }
}
