param(
    [string]$PythonRuntime = $env:LOCAL_VOICE_PYTHON_RUNTIME,
    [string]$FfmpegDirectory = $env:LOCAL_VOICE_FFMPEG_DIRECTORY,
    [string]$ApprovedModelsDirectory = $env:LOCAL_VOICE_APPROVED_MODELS_DIRECTORY
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root 'release\model-manifest.json'
$stage = Join-Path $root 'release\staged-runtime'
$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json

if (-not $manifest.models -or @($manifest.models).Count -eq 0) {
    throw 'Release blocked: release/model-manifest.json has no approved model. Do not ship cached or unreviewed model files.'
}
foreach ($model in $manifest.models) {
    if ($model.approved_for_distribution -ne $true -or -not $model.sha256 -or -not $model.license_notice -or -not $model.artifact_path) {
        throw "Release blocked: model manifest entry '$($model.id)' is missing approval, SHA-256, license notice, or artifact path."
    }
}
if (-not $PythonRuntime -or -not (Test-Path (Join-Path $PythonRuntime 'python.exe'))) {
    throw 'Set LOCAL_VOICE_PYTHON_RUNTIME to an audited, portable Python runtime folder containing python.exe.'
}
if (-not $FfmpegDirectory -or -not (Test-Path (Join-Path $FfmpegDirectory 'ffmpeg.exe'))) {
    throw 'Set LOCAL_VOICE_FFMPEG_DIRECTORY to the audited FFmpeg folder containing ffmpeg.exe.'
}
if (-not $ApprovedModelsDirectory -or -not (Test-Path $ApprovedModelsDirectory)) {
    throw 'Set LOCAL_VOICE_APPROVED_MODELS_DIRECTORY to the reviewed model-artifact directory.'
}

Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage, (Join-Path $stage 'backend'), (Join-Path $stage 'backend\external'), (Join-Path $stage 'models') | Out-Null
Copy-Item -LiteralPath $PythonRuntime -Destination (Join-Path $stage 'python') -Recurse
Copy-Item -LiteralPath $FfmpegDirectory -Destination (Join-Path $stage 'ffmpeg') -Recurse
Copy-Item -LiteralPath (Join-Path $root 'backend') -Destination (Join-Path $stage 'backend\backend') -Recurse
Copy-Item -LiteralPath (Join-Path $root 'prototype') -Destination (Join-Path $stage 'backend\prototype') -Recurse
# Source only.  Never accidentally pull this development checkout's venv,
# benchmark WAVs, or caches into a customer installer.
Copy-Item -LiteralPath (Join-Path $root 'external\OmniVoice') -Destination (Join-Path $stage 'backend\external\OmniVoice') -Recurse -Exclude '.venv312','artifacts*','benchmark*','*.wav','*.mp3'
foreach ($model in $manifest.models) {
    $source = Join-Path $ApprovedModelsDirectory $model.artifact_path
    if (-not (Test-Path $source)) { throw "Approved artifact missing: $source" }
    $actual = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $model.sha256.ToLowerInvariant()) { throw "Checksum mismatch for model '$($model.id)'" }
    $destination = Join-Path (Join-Path $stage 'models') $model.artifact_path
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $stage 'model-manifest.json')
Write-Host "Staged audited runtime at $stage"
