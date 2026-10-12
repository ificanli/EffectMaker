[CmdletBinding()]
param(
    [string]$ProjectPath,
    [string]$OutputPath,
    [string]$TrainingReviewBundle,
    [string]$AuthoritativeProjectPath,
    [switch]$UsePackageManager
)

$ErrorActionPreference = "Stop"
$workspaceRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$expectedVersion = "2022.3.16f1c1"
$unityEditor = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Unity.exe"
$webglSupportPath = "C:\Program Files\Unity\Hub\Editor\2022.3.16f1\Editor\Data\PlaybackEngines\WebGLSupport"
$logPath = Join-Path $workspaceRoot "workspace\progress\effectdemo-webgl-2022-build.log"

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = Join-Path $workspaceRoot "UnityDemo\EffectDemo"
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $workspaceRoot "workspace\Builds\WebGL\VfxTrainingPlayer2022"
}
if ([string]::IsNullOrWhiteSpace($AuthoritativeProjectPath)) {
    $AuthoritativeProjectPath = Join-Path $workspaceRoot "UnityDemo\EffectDemo"
}

$projectVersionPath = Join-Path $ProjectPath "ProjectSettings\ProjectVersion.txt"
if (-not (Test-Path -LiteralPath $projectVersionPath)) {
    throw "Not a Unity project: $ProjectPath"
}

$versionText = Get-Content -LiteralPath $projectVersionPath -Raw
if ($versionText -notmatch [regex]::Escape($expectedVersion)) {
    throw "Expected Unity $expectedVersion, found: $versionText"
}
if (-not (Test-Path -LiteralPath $unityEditor)) {
    throw "Unity Editor is missing: $unityEditor"
}
if (-not (Test-Path -LiteralPath $webglSupportPath)) {
    throw "Unity WebGL Support is missing for $expectedVersion. Install the f1c1 module from download.unitychina.cn."
}
if (Test-Path -LiteralPath (Join-Path $ProjectPath "Temp\UnityLockfile")) {
    throw "Unity project is open. Build an isolated EffectDemo 2022 copy with -ProjectPath instead of closing the user's Editor."
}

$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

unity projects verify $resolvedProject --format json
if ($LASTEXITCODE -ne 0) {
    throw "Unity project verification failed with exit code $LASTEXITCODE."
}

$previousReviewBundle = $env:VFX_WEB_TRAINING_REVIEW_BUNDLE
$previousAuthoritativeProject = $env:VFX_WEB_AUTHORITATIVE_PROJECT
try {
    if ([string]::IsNullOrWhiteSpace($TrainingReviewBundle)) {
        Remove-Item Env:VFX_WEB_TRAINING_REVIEW_BUNDLE -ErrorAction SilentlyContinue
    }
    else {
        $env:VFX_WEB_TRAINING_REVIEW_BUNDLE = (Resolve-Path -LiteralPath $TrainingReviewBundle).Path
    }
    $env:VFX_WEB_AUTHORITATIVE_PROJECT = (Resolve-Path -LiteralPath $AuthoritativeProjectPath).Path

    $arguments = @(
        "-batchmode",
        "-quit",
        "-projectPath", $resolvedProject,
        "-buildTarget", "WebGL",
        "-executeMethod", "VfxPrefabWeb.Editor.VfxWebPlayerBuilder.BuildFromCommandLine",
        "-buildOutput", $resolvedOutput,
        "-logFile", $logPath
    )
    if (-not $UsePackageManager) {
        $arguments = @("-noUpm") + $arguments
    }
    $process = Start-Process -FilePath $unityEditor -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    $buildExitCode = $process.ExitCode
}
finally {
    if ($null -eq $previousReviewBundle) {
        Remove-Item Env:VFX_WEB_TRAINING_REVIEW_BUNDLE -ErrorAction SilentlyContinue
    }
    else {
        $env:VFX_WEB_TRAINING_REVIEW_BUNDLE = $previousReviewBundle
    }
    if ($null -eq $previousAuthoritativeProject) {
        Remove-Item Env:VFX_WEB_AUTHORITATIVE_PROJECT -ErrorAction SilentlyContinue
    }
    else {
        $env:VFX_WEB_AUTHORITATIVE_PROJECT = $previousAuthoritativeProject
    }
}

if ($buildExitCode -ne 0) {
    throw "Unity WebGL build failed with exit code $buildExitCode. See $logPath"
}

Write-Host "Build ready: $resolvedOutput"
Write-Host "Serve with: python -m workspace.tools.vfx_web_player_server"
