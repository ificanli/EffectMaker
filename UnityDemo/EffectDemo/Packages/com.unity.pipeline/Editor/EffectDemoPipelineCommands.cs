using System;
using System.Linq;
using System.Reflection;
using Unity.Pipeline.Commands;

/// <summary>
/// Live Pipeline command surface for the Unity 2022 EffectDemo project.
/// </summary>
public static class EffectDemoPipelineCommands
{
    [CliCommand("create_cli_smoke_effect", "Create the repeatable EffectDemo CLI smoke effect", Tags = new[] { "vfx", "assets" })]
    public static string CreateCliSmokeEffect()
    {
        InvokeEffectDemoCommand("CreateCliSmokeEffect");
        return "Assets/Art/VFX/CliSamples/CliSmokeEffect.prefab";
    }

    [CliCommand("remove_cli_smoke_effect", "Remove the EffectDemo CLI smoke effect", Tags = new[] { "vfx", "assets" })]
    public static string RemoveCliSmokeEffect()
    {
        InvokeEffectDemoCommand("RemoveCliSmokeEffect");
        return "removed";
    }

    private static void InvokeEffectDemoCommand(string methodName)
    {
        var commandType = AppDomain.CurrentDomain.GetAssemblies()
            .Select(assembly => assembly.GetType("EffectDemoCliCommands", throwOnError: false))
            .FirstOrDefault(type => type != null);
        var method = commandType?.GetMethod(methodName, BindingFlags.Public | BindingFlags.Static);
        if (method == null)
            throw new InvalidOperationException($"EffectDemoCliCommands.{methodName} was not found.");
        method.Invoke(null, null);
    }
}
