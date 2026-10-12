param(
    [Parameter(Mandatory = $true)] [string]$Requests,
    [string]$ProjectPath,
    [string]$UnityEditor = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Unity.exe",
    [string]$LogFile,
    [switch]$NoUpm
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "effectdemo_unity_process.ps1")
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectPath)) { $ProjectPath = Join-Path $scriptDirectory "..\..\UnityDemo\EffectDemo" }
if ([string]::IsNullOrWhiteSpace($LogFile)) { $LogFile = Join-Path $scriptDirectory "..\progress\effectdemo-prefab-graph-source-export.log" }
$resolvedRequests = (Resolve-Path -LiteralPath $Requests).Path
$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
$resolvedLog = [System.IO.Path]::GetFullPath($LogFile)
if (-not (Test-Path -LiteralPath $UnityEditor)) { throw "Unity editor not found: $UnityEditor" }
if (-not (Test-Path -LiteralPath (Join-Path $resolvedProject "ProjectSettings\ProjectVersion.txt"))) { throw "Not a Unity project: $resolvedProject" }
$logParent = Split-Path -Parent $resolvedLog
if ($logParent) { New-Item -ItemType Directory -Force -Path $logParent | Out-Null }
$arguments = @("-batchmode", "-nographics", "-quit", "-projectPath", $resolvedProject, "-executeMethod", "EffectDemoPrefabGraphSourceExporter.ExportFromCommandLine", "-prefabGraphSourceRequests", $resolvedRequests, "-logFile", $resolvedLog)
if ($NoUpm) { $arguments = @("-noUpm") + $arguments }
$process = Start-EffectDemoUnityProcess -FilePath $UnityEditor -ArgumentList $arguments
if ($process.ExitCode -ne 0) { throw "Unity source PrefabGraph export failed with exit code $($process.ExitCode). See $resolvedLog" }
Write-Output "EffectDemo source PrefabGraph export completed. Log: $resolvedLog"
