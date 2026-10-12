param(
    [ValidateSet("create", "remove")]
    [string]$Action = "create",
    [string]$ProjectPath = (Join-Path $PSScriptRoot "..\..\UnityDemo\EffectDemo"),
    [string]$UnityEditor = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Unity.exe",
    [string]$LogFile = (Join-Path $ProjectPath "effectdemo-cli.log")
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "effectdemo_unity_process.ps1")
if (-not (Test-Path -LiteralPath $UnityEditor)) {
    throw "Unity editor not found: $UnityEditor"
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectPath "ProjectSettings\ProjectVersion.txt"))) {
    throw "Not a Unity project: $ProjectPath"
}

$method = if ($Action -eq "create") { "CreateCliSmokeEffect" } else { "RemoveCliSmokeEffect" }
$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
$resolvedLog = Join-Path (Split-Path -Parent $LogFile) (Split-Path -Leaf $LogFile)
$arguments = @(
    "-batchmode", "-nographics", "-quit",
    "-projectPath", $resolvedProject,
    "-executeMethod", "EffectDemoCliCommands.$method",
    "-logFile", $resolvedLog
)

$process = Start-EffectDemoUnityProcess -FilePath $UnityEditor -ArgumentList $arguments
if ($process.ExitCode -ne 0) {
    throw "Unity CLI command failed with exit code $($process.ExitCode). See $LogFile"
}
Write-Output "EffectDemo CLI action '$Action' completed. Log: $LogFile"
