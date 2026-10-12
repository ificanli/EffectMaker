param(
    [Parameter(Mandatory = $true)]
    [string]$Requests,
    [string]$ProjectPath,
    [string]$UnityEditor = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Unity.exe",
    [string]$LogFile,
    [switch]$NoUpm
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "effectdemo_unity_process.ps1")
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = Join-Path $scriptDirectory "..\..\UnityDemo\EffectDemo"
}
if ([string]::IsNullOrWhiteSpace($LogFile)) {
    $LogFile = Join-Path $scriptDirectory "..\progress\effectdemo-material-trajectory-executor.log"
}
$resolvedRequests = (Resolve-Path -LiteralPath $Requests).Path
$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not (Test-Path -LiteralPath $UnityEditor)) {
    throw "Unity editor not found: $UnityEditor"
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedProject "ProjectSettings\ProjectVersion.txt"))) {
    throw "Not a Unity project: $resolvedProject"
}

$resolvedLog = [System.IO.Path]::GetFullPath($LogFile)
$logParent = Split-Path -Parent $resolvedLog
if ($logParent) {
    New-Item -ItemType Directory -Force -Path $logParent | Out-Null
}
$previousRequests = $env:EFFECTDEMO_MATERIAL_TRAJECTORY_REQUESTS
$env:EFFECTDEMO_MATERIAL_TRAJECTORY_REQUESTS = $resolvedRequests
try {
    $arguments = @(
        "-batchmode",
        "-projectPath", $resolvedProject,
        "-executeMethod", "EffectDemoMaterialTrajectoryBootstrap.StartFromEnvironment",
        "-logFile", $resolvedLog
    )
    if ($NoUpm) {
        $arguments = @("-noUpm") + $arguments
    }
    $process = Start-EffectDemoUnityProcess -FilePath $UnityEditor -ArgumentList $arguments
    if ($process.ExitCode -ne 0) {
        throw "Unity material trajectory execution failed with exit code $($process.ExitCode). See $resolvedLog"
    }
}
finally {
    $env:EFFECTDEMO_MATERIAL_TRAJECTORY_REQUESTS = $previousRequests
}

Write-Output "EffectDemo material trajectory execution completed. Log: $resolvedLog"
