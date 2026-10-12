param(
    [string]$ProjectPath = "",
    [string]$MaterialAudit = "",
    [string]$MeshRoot = "",
    [string]$Output = "",
    [string]$Request = "",
    [string]$UnityEditor = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Unity.exe",
    [string]$LogFile = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "effectdemo_unity_process.ps1")
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ProjectPath)) { $ProjectPath = Join-Path $scriptDirectory "..\..\UnityDemo\EffectDemo" }
if ([string]::IsNullOrWhiteSpace($MaterialAudit)) { $MaterialAudit = Join-Path $ProjectPath "Library\VFXSourceIngest\material-binding-audit.json" }
if ([string]::IsNullOrWhiteSpace($MeshRoot)) { $MeshRoot = Join-Path $ProjectPath "Assets\VFXSourceIngest\Shared\Meshes" }
if ([string]::IsNullOrWhiteSpace($Output)) { $Output = Join-Path $scriptDirectory "..\data\vfx_generation\generated\prefab_asset_routes_r001\mesh_audit.json" }
if ([string]::IsNullOrWhiteSpace($Request)) { $Request = Join-Path $scriptDirectory "..\data\vfx_generation\generated\prefab_asset_routes_r001\mesh_audit_request.json" }
if ([string]::IsNullOrWhiteSpace($LogFile)) { $LogFile = Join-Path $scriptDirectory "..\progress\effectdemo-asset-route-audit.log" }

$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
$resolvedMaterialAudit = (Resolve-Path -LiteralPath $MaterialAudit).Path
$resolvedMeshRoot = (Resolve-Path -LiteralPath $MeshRoot).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($Output)
$resolvedRequest = [System.IO.Path]::GetFullPath($Request)
$resolvedLog = [System.IO.Path]::GetFullPath($LogFile)
$assetsRoot = (Resolve-Path -LiteralPath (Join-Path $resolvedProject "Assets")).Path
if (-not (Test-Path -LiteralPath $UnityEditor)) { throw "Unity editor not found: $UnityEditor" }
$audit = Get-Content -LiteralPath $resolvedMaterialAudit -Raw | ConvertFrom-Json
$materialPaths = @($audit.materials | ForEach-Object { $_.material_path } | Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $resolvedProject $_)) } | Sort-Object -Unique)
$meshPaths = @(
    Get-ChildItem -LiteralPath $resolvedMeshRoot -Recurse -File -Filter "*.fbx" |
        ForEach-Object { ("Assets/" + $_.FullName.Substring($assetsRoot.Length + 1).Replace("\", "/")) } |
        Sort-Object -Unique
)
foreach ($parent in @((Split-Path -Parent $resolvedOutput), (Split-Path -Parent $resolvedRequest), (Split-Path -Parent $resolvedLog))) {
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
}
$requestPayload = [ordered]@{ output_path = $resolvedOutput; mesh_paths = $meshPaths; material_paths = $materialPaths }
$requestPayload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedRequest -Encoding UTF8
$arguments = @(
    "-batchmode", "-nographics", "-quit",
    "-projectPath", $resolvedProject,
    "-executeMethod", "EffectDemoAssetRouteAudit.Run",
    "-assetRouteAuditRequest", $resolvedRequest,
    "-logFile", $resolvedLog
)
$process = Start-EffectDemoUnityProcess -FilePath $UnityEditor -ArgumentList $arguments
if ($process.ExitCode -ne 0) { throw "Unity asset route audit failed with exit code $($process.ExitCode). See $resolvedLog" }
if (-not (Test-Path -LiteralPath $resolvedOutput)) { throw "Unity asset route audit did not write output: $resolvedOutput" }
Write-Output "EffectDemo asset route audit completed. Output: $resolvedOutput"
