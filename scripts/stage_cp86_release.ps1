param(
  [string]$SeedRoot = "",
  [string]$Destination = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $Destination) { $Destination = Join-Path $root 'release\staged-runtime' }
if (-not $SeedRoot) { $SeedRoot = $env:LOCAL_AI_RELEASE_SEED_ROOT }
if (-not $SeedRoot) { throw 'Specify -SeedRoot or LOCAL_AI_RELEASE_SEED_ROOT; no implicit stale-release seed is allowed.' }
$mainSeed = Join-Path $SeedRoot 'cp82\runtime-main'
$chatterboxSeed = Join-Path $SeedRoot 'cp82\runtime-chatterbox'
$modelSeed = Join-Path $SeedRoot 'cp81b\models'
if (-not (Test-Path (Join-Path $mainSeed 'python.exe')) -or
    -not (Test-Path (Join-Path $chatterboxSeed 'python.exe')) -or
    -not (Test-Path (Join-Path $modelSeed 'model-manifest.json'))) {
  throw "CP8.6 requires an approved clean runtime seed (runtime-main, runtime-chatterbox, models); refusing stale release reuse."
}

function Assert-ModelManifest([string]$ModelRoot) {
  $manifestPath = Join-Path $ModelRoot 'model-manifest.json'
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  foreach ($artifact in $manifest.artifacts) {
    $candidate = Join-Path $ModelRoot $artifact.relative_path
    if (-not (Test-Path -LiteralPath $candidate)) { throw "Approved model missing: $($artifact.relative_path)" }
    $item = Get-Item -LiteralPath $candidate -Force
    if ($item.LinkType) { throw "Model symlink is forbidden: $($artifact.relative_path)" }
    if ($item.Length -ne [int64]$artifact.size_bytes) { throw "Approved model size mismatch: $($artifact.relative_path)" }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $stream = [System.IO.File]::OpenRead($candidate)
      try { $hash = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLower() }
      catch { throw "Unable to hash approved model $($artifact.relative_path): $($_.Exception.Message)" }
      finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
    if ($hash -ne $artifact.sha256) {
      throw "Approved model hash mismatch: $($artifact.relative_path)"
    }
  }
  return $manifest.artifacts.Count
}

function Get-Sha256([string]$Path) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try { $stream = [System.IO.File]::OpenRead($Path); try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLower() } finally { $stream.Dispose() } } finally { $sha.Dispose() }
}

$modelCount = Assert-ModelManifest $modelSeed

Remove-Item -LiteralPath $Destination -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -LiteralPath $mainSeed -Destination (Join-Path $Destination 'runtime-main') -Recurse -Force
Copy-Item -LiteralPath $chatterboxSeed -Destination (Join-Path $Destination 'runtime-chatterbox') -Recurse -Force
Copy-Item -LiteralPath $modelSeed -Destination (Join-Path $Destination 'models') -Recurse -Force
$stagedModelCount = Assert-ModelManifest (Join-Path $Destination 'models')
if ($stagedModelCount -ne $modelCount) { throw 'Staged model manifest count mismatch.' }
$app = Join-Path $Destination 'runtime-main\app'
Remove-Item -LiteralPath $app -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $app | Out-Null
foreach ($item in 'backend','requirements-backend.txt') {
  Copy-Item -LiteralPath (Join-Path $root $item) -Destination $app -Recurse -Force
}
Get-ChildItem $app -Force -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem $app -Force -Recurse -Directory -Filter 'tests' | Remove-Item -Recurse -Force
@{
  schema_version = 1
  app_version = (Get-Content (Join-Path $root 'package.json') -Raw | ConvertFrom-Json).version
  critical_sha256 = @{
    'backend/core/app_paths.py' = Get-Sha256 (Join-Path $root 'backend\core\app_paths.py')
    'backend/services/capability_service.py' = Get-Sha256 (Join-Path $root 'backend\services\capability_service.py')
  }
  approved_model_file_count = $modelCount
} | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Destination 'cp86-staging-manifest.json') -Encoding utf8
Write-Host "CP8.6 clean staging complete: $Destination"
