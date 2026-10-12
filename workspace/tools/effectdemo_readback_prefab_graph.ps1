param(
    [Parameter(Mandatory = $true)] [string]$Graph,
    [Parameter(Mandatory = $true)] [string]$Prefab,
    [Parameter(Mandatory = $true)] [string]$OutputGraph,
    [Parameter(Mandatory = $true)] [string]$Result,
    [string]$ProjectPath,
    [string]$UnityEditor = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Unity.exe",
    [string]$LogFile,
    [switch]$NoUpm
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "effectdemo_unity_process.ps1")
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectPath)) { $ProjectPath = Join-Path $scriptDirectory "..\..\UnityDemo\EffectDemo" }
if ([string]::IsNullOrWhiteSpace($LogFile)) { $LogFile = Join-Path $scriptDirectory "..\progress\effectdemo-prefab-graph-readback.log" }
$resolvedGraph = (Resolve-Path -LiteralPath $Graph).Path
$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
$resolvedResult = [System.IO.Path]::GetFullPath($Result)
$resolvedOutputGraph = [System.IO.Path]::GetFullPath($OutputGraph)
$resolvedLog = [System.IO.Path]::GetFullPath($LogFile)
if (-not (Test-Path -LiteralPath $UnityEditor)) { throw "Unity editor not found: $UnityEditor" }
if (-not (Test-Path -LiteralPath (Join-Path $resolvedProject "ProjectSettings\ProjectVersion.txt"))) { throw "Not a Unity project: $resolvedProject" }
foreach ($parent in @((Split-Path -Parent $resolvedResult), (Split-Path -Parent $resolvedOutputGraph), (Split-Path -Parent $resolvedLog))) { if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null } }
$arguments = @(
    "-batchmode", "-nographics", "-quit", "-projectPath", $resolvedProject,
    "-executeMethod", "EffectDemoPrefabGraphReadback.ReadbackFromCommandLine",
    "-prefabGraphPath", $resolvedGraph, "-prefabGraphInput", $Prefab,
    "-prefabGraphReadbackOutput", $resolvedOutputGraph, "-prefabGraphReadbackResult", $resolvedResult,
    "-logFile", $resolvedLog
)
if ($NoUpm) { $arguments = @("-noUpm") + $arguments }
$process = Start-EffectDemoUnityProcess -FilePath $UnityEditor -ArgumentList $arguments
if ($process.ExitCode -ne 0) { throw "Unity PrefabGraph readback failed with exit code $($process.ExitCode). See $resolvedLog" }
if (-not (Test-Path -LiteralPath $resolvedResult)) { throw "Unity PrefabGraph readback did not write result: $resolvedResult" }
Write-Output "EffectDemo PrefabGraph readback completed. Result: $resolvedResult"
