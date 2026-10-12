param([Parameter(Mandatory = $true)] [string]$Output, [Parameter(Mandatory = $true)] [string]$LogFile)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../tools/effectdemo_unity_process.ps1")
$previousOutput = $env:EFFECTDEMO_PIPELINE_GATE_PROBE_OUTPUT
try {
    $env:EFFECTDEMO_PIPELINE_GATE_PROBE_OUTPUT = [IO.Path]::GetFullPath($Output)
    $project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../unity-render-staging/EffectDemoPromptHumanR001"))
    $process = Start-EffectDemoUnityProcess -FilePath "C:\Program Files\Unity\Hub\Editor\2022.3.62f3c1\Editor\Unity.exe" -ArgumentList @(
        "-batchmode", "-quit", "-nographics", "-projectPath", $project,
        "-executeMethod", "EffectDemoPipelineGateProbe.VerifyNullPipelineCannotQualify",
        "-logFile", [IO.Path]::GetFullPath($LogFile)
    )
    exit $process.ExitCode
}
finally { $env:EFFECTDEMO_PIPELINE_GATE_PROBE_OUTPUT = $previousOutput }
