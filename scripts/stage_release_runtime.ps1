param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $root 'release\staged-runtime'
$copyLog = Join-Path $root 'release\stage-runtime.log'

function Copy-ReleaseDirectory([string]$Source, [string]$Destination, [string[]]$ExcludeDirectories = @()) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $arguments = @($Source, $Destination, '/E', '/COPY:DAT', '/R:1', '/W:1', '/NFL', '/NDL', "/LOG+:$copyLog")
    if ($ExcludeDirectories.Count -gt 0) { $arguments += '/XD'; $arguments += $ExcludeDirectories }
    & robocopy @arguments
    if ($LASTEXITCODE -gt 7) { throw "Failed to stage '$Source' (robocopy exit $LASTEXITCODE). See $copyLog" }
}

$mainRuntime = Join-Path $root '.runtime\cp82\runtime-main'
$chatterboxRuntime = Join-Path $root '.runtime\cp82\runtime-chatterbox'
$models = Join-Path $root '.runtime\cp81b\models'
foreach ($required in @((Join-Path $mainRuntime 'python.exe'), (Join-Path $chatterboxRuntime 'python.exe'), (Join-Path $models 'huggingface\hub'), (Join-Path $models 'model-manifest.json'))) {
    if (-not (Test-Path $required)) { throw "Missing approved CP8 runtime artifact: $required" }
}

Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $copyLog -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-ReleaseDirectory $mainRuntime (Join-Path $stage 'runtime-main') @('__pycache__','tests','test')
Copy-ReleaseDirectory $chatterboxRuntime (Join-Path $stage 'runtime-chatterbox') @('__pycache__','tests','test')
Copy-ReleaseDirectory $models (Join-Path $stage 'models') @('__pycache__')
Write-Host "Staged audited runtime at $stage"
