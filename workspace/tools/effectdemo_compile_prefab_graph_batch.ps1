param(
    [Parameter(Mandatory = $true)] [string]$Request,
    [string]$ProjectPath,
    [string]$UnityEditor = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Unity.exe",
    [string]$LogFile,
    [switch]$NoUpm
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "effectdemo_unity_process.ps1")
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectPath)) { $ProjectPath = Join-Path $scriptDirectory "..\..\UnityDemo\EffectDemo" }
if ([string]::IsNullOrWhiteSpace($LogFile)) { $LogFile = Join-Path $scriptDirectory "..\progress\effectdemo-prefab-graph-batch-compile.log" }
$resolvedRequest = (Resolve-Path -LiteralPath $Request).Path
$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
$resolvedLog = [System.IO.Path]::GetFullPath($LogFile)
if (-not (Test-Path -LiteralPath $UnityEditor)) { throw "Unity editor not found: $UnityEditor" }
$parent = Split-Path -Parent $resolvedLog
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$arguments = @("-batchmode", "-nographics", "-quit", "-projectPath", $resolvedProject, "-executeMethod", "EffectDemoPrefabGraphCompiler.CompileBatchFromCommandLine", "-prefabGraphBatchRequest", $resolvedRequest, "-logFile", $resolvedLog)
if ($NoUpm) { $arguments = @("-noUpm") + $arguments }
$process = Start-EffectDemoUnityProcess -FilePath $UnityEditor -ArgumentList $arguments
if ($process.ExitCode -ne 0) { throw "Unity PrefabGraph batch compiler failed with exit code $($process.ExitCode). See $resolvedLog" }
Write-Output "EffectDemo PrefabGraph batch compile completed. Log: $resolvedLog"
