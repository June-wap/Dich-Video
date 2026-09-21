param(
  [Parameter(Mandatory = $true)]
  [string]$StageRoot
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stage = (Resolve-Path -LiteralPath $StageRoot).Path
$manifestPath = Join-Path $stage 'cp86-staging-manifest.json'
$output = Join-Path $root 'release\cp87-repair-dist'
$configPath = Join-Path $root 'release\cp87-repair-electron-builder.json'
$buildRecord = Join-Path $root 'release\cp87-build-input.json'
$archiveEvidence = Join-Path $root 'release\cp87-evidence'
$nsisTargetPath = Join-Path $root 'node_modules\app-builder-lib\out\targets\nsis\NsisTarget.js'

function Get-Sha256([string]$Path) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $stream = [System.IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLower() }
    finally { $stream.Dispose() }
  } finally { $sha.Dispose() }
}

function Enable-Cp87ArchiveEvidenceHook {
  if (-not (Test-Path -LiteralPath $nsisTargetPath)) {
    throw "electron-builder NSIS target is missing: $nsisTargetPath"
  }

  $marker = 'CP8.7 repair evidence hook'
  $contents = Get-Content -LiteralPath $nsisTargetPath -Raw
  if ($contents.Contains($marker)) { return }

  $needle = "        timer.end();`r`n        if (isBuildDifferentialAware && this.isWebInstaller) {"
  if (-not $contents.Contains($needle)) {
    $needle = "        timer.end();`n        if (isBuildDifferentialAware && this.isWebInstaller) {"
  }
  if (-not $contents.Contains($needle)) {
    throw 'Unsupported electron-builder NsisTarget.js layout; refusing to build without archive evidence preservation.'
  }

  $replacement = @'
        timer.end();
        // CP8.7 repair evidence hook: electron-builder normally deletes this
        // completed archive after makensis consumes it. Preserve it before
        // NSIS compilation so release validation can independently test it.
        const cp87EvidenceDir = process.env.CP87_NSIS_ARCHIVE_EVIDENCE_DIR;
        if (cp87EvidenceDir) {
            await fs.promises.mkdir(cp87EvidenceDir, { recursive: true });
            const cp87EvidenceArchive = path.join(cp87EvidenceDir, path.basename(archiveFile));
            await fs.promises.copyFile(archiveFile, cp87EvidenceArchive);
            process.stderr.write(`CP87 preserved completed NSIS archive: ${cp87EvidenceArchive}\n`);
        }
        if (isBuildDifferentialAware && this.isWebInstaller) {
'@
  $contents = $contents.Replace($needle, $replacement.TrimEnd([char]13, [char]10))
  Set-Content -LiteralPath $nsisTargetPath -Value $contents -NoNewline -Encoding utf8
  if (-not (Get-Content -LiteralPath $nsisTargetPath -Raw).Contains($marker)) {
    throw 'Failed to install the CP8.7 archive-evidence hook.'
  }
}

if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'CP8.6 staging manifest is missing.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.app_version -ne '1.0.1' -or $manifest.approved_model_file_count -ne 19) {
  throw 'CP8.6 manifest version or approved model count is invalid.'
}
foreach ($key in 'backend/core/app_paths.py', 'backend/services/capability_service.py') {
  if (-not $manifest.critical_sha256.PSObject.Properties.Name.Contains($key)) {
    throw "CP8.6 manifest lacks critical hash: $key"
  }
}
foreach ($required in 'runtime-main\python.exe', 'runtime-chatterbox\python.exe', 'models\model-manifest.json') {
  if (-not (Test-Path -LiteralPath (Join-Path $stage $required))) { throw "CP8.6 payload missing $required" }
}

$critical = @('backend/core/app_paths.py', 'backend/services/capability_service.py', 'backend/config.py', 'backend/services/chatterbox_adapter.py')
$criticalHashes = @{}
foreach ($relative in $critical) {
  $source = Join-Path $root $relative
  $staged = Join-Path $stage (Join-Path 'runtime-main\app' $relative)
  if (-not (Test-Path -LiteralPath $source) -or -not (Test-Path -LiteralPath $staged)) { throw "Critical source missing: $relative" }
  $sourceHash = Get-Sha256 $source
  $stagedHash = Get-Sha256 $staged
  if ($sourceHash -ne $stagedHash) { throw "Critical source hash mismatch: $relative" }
  $criticalHashes[$relative] = $stagedHash
}

$forbidden = rg -l -i '\.venv312|\.venv-chatterbox|D:\\Tool Dich Cho Khach|F:\\Voca-CP8-Build' (Join-Path $stage 'runtime-main\app') -g '*.py' -g '*.cjs' -g '*.json'
if ($LASTEXITCODE -eq 0) { throw "Forbidden staged production reference(s): $($forbidden -join ', ')" }
if ($LASTEXITCODE -ne 1) { throw 'Unable to audit staged production references.' }

# The default NSIS Nsis7z plugin fails silently when asked to extract the
# single >19 GiB uncompressed application archive. Externalize every staged
# runtime extension as normal NSIS File records; the residual app archive is
# small enough for Nsis7z while runtime/model payload bypasses that plugin.
$preCompressedExtensions = @(Get-ChildItem -LiteralPath $stage -File -Recurse |
  ForEach-Object { $_.Extension.ToLowerInvariant() } |
  Where-Object { $_ } | Sort-Object -Unique)
if ($preCompressedExtensions.Count -eq 0) { throw 'No staged runtime file extensions discovered.' }

# This generated config is build metadata only. StageRoot is copied into the
# installer as resources/runtime; it is never a customer-runtime path.
$config = @{
  appId = 'vn.vocabasic.studio'
  productName = 'Voca Basic'
  executableName = 'Voca Basic'
  directories = @{ output = 'release/cp87-repair-dist'; buildResources = 'release' }
  asar = $false
  files = @('desktop/**', 'package.json')
  extraResources = @(
    @{ from = 'frontend/dist'; to = 'frontend' },
    @{ from = $stage; to = 'runtime' },
    @{ from = 'release/THIRD_PARTY_NOTICES.md'; to = 'THIRD_PARTY_NOTICES.md' }
  )
  win = @{ target = @(@{ target = 'nsis'; arch = @('x64') }); icon = 'release/icon.ico' }
  nsis = @{ oneClick = $false; perMachine = $true; allowElevation = $true; allowToChangeInstallationDirectory = $true; createDesktopShortcut = $true; createStartMenuShortcut = $true; shortcutName = 'Voca Basic'; runAfterFinish = $false; artifactName = 'Voca-Basic-Setup-${version}.exe'; preCompressedFileExtensions = $preCompressedExtensions }
}
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding utf8
@{ cp86_input_path = $stage; cp86_manifest_sha256 = (Get-Sha256 $manifestPath); critical_source_sha256 = $criticalHashes; generated_at_utc = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $buildRecord -Encoding utf8

if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Recurse -Force }
if (Test-Path -LiteralPath $archiveEvidence) { Remove-Item -LiteralPath $archiveEvidence -Recurse -Force }
New-Item -ItemType Directory -Path $archiveEvidence -Force | Out-Null
Enable-Cp87ArchiveEvidenceHook
& npm run build:frontend
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:CP87_NSIS_ARCHIVE_EVIDENCE_DIR = $archiveEvidence
& npx electron-builder --config $configPath --x64
exit $LASTEXITCODE
