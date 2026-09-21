# High-Performance Package & Verify AI Bundles (7-Zip Multi-Threaded Direct Archive)
param(
    [string]$SeedRoot = "F:\Voca-CP8-Build\cp86\staged-runtime",
    [string]$OutputDir = "F:\Voca-AI-Packages",
    [string]$SevenZipPath = "C:\Program Files\7-Zip\7z.exe",
    [int]$CompressionLevel = 3, # 3 = Fast LZMA2 (optimal speed vs size ratio)
    [int]$VolumeSizeMB = 0      # 0 = single .7z archive per package
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $SeedRoot)) {
    throw "SeedRoot not found: $SeedRoot"
}
if (-not (Test-Path -LiteralPath $SevenZipPath)) {
    throw "7-Zip not found at: $SevenZipPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$manifestsDir = Join-Path $OutputDir "manifests"
New-Item -ItemType Directory -Force -Path $manifestsDir | Out-Null

function Get-FileSha256([string]$FilePath) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($FilePath)
        try {
            return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLower()
        } finally {
            $stream.Dispose()
        }
    } finally {
        $sha.Dispose()
    }
}

$packages = @("runtime-main", "runtime-chatterbox", "models")
$summaryManifest = @{
    release_version = "1.0.1"
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    compression_method = "7z LZMA2 mx=$CompressionLevel"
    packages = @{}
}

$stopwatchTotal = [System.Diagnostics.Stopwatch]::StartNew()

foreach ($pkg in $packages) {
    $src = Join-Path $SeedRoot $pkg
    if (-not (Test-Path -LiteralPath $src)) {
        throw "Missing required package in SeedRoot: $src"
    }

    Write-Host "`n=======================================================" -ForegroundColor Yellow
    Write-Host " [PACKAGE] $pkg" -ForegroundColor Yellow
    Write-Host " Source: $src" -ForegroundColor Yellow
    Write-Host "=======================================================" -ForegroundColor Yellow

    # 1. Critical binary hash verification before archiving
    $criticalHashes = @{}
    if ($pkg -eq "runtime-main") {
        $py = Join-Path $src "python.exe"
        $dll = Join-Path $src "python312.dll"
        if (Test-Path -LiteralPath $py) { $criticalHashes["python.exe"] = Get-FileSha256 $py }
        if (Test-Path -LiteralPath $dll) { $criticalHashes["python312.dll"] = Get-FileSha256 $dll }
    } elseif ($pkg -eq "runtime-chatterbox") {
        $py = Join-Path $src "python.exe"
        if (Test-Path -LiteralPath $py) { $criticalHashes["python.exe"] = Get-FileSha256 $py }
    } elseif ($pkg -eq "models") {
        $mm = Join-Path $src "model-manifest.json"
        if (Test-Path -LiteralPath $mm) {
            $criticalHashes["model-manifest.json"] = Get-FileSha256 $mm
            Copy-Item -LiteralPath $mm -Destination (Join-Path $manifestsDir "models-original-manifest.json") -Force
        }
    }

    # 2. Direct 7-Zip compression from $src into $archivePath (No intermediate copy!)
    $archivePath = Join-Path $OutputDir "$pkg.7z"
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }

    Write-Host "  -> Compressing directly from source to $archivePath..." -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    $args = @("a", "-t7z", "-m0=lzma2", "-mx=$CompressionLevel", "-mmt=on")
    if ($VolumeSizeMB -gt 0) {
        $args += "-v$($VolumeSizeMB)m"
    }
    $args += $archivePath
    $args += "$src\*"

    & $SevenZipPath @args
    if ($LASTEXITCODE -ne 0) {
        throw "7-Zip compression failed for $pkg with exit code $LASTEXITCODE"
    }
    $sw.Stop()
    $archiveSizeMB = [math]::Round(((Get-Item $archivePath).Length / 1MB), 2)
    Write-Host "  -> Compression complete in $([math]::Round($sw.Elapsed.TotalSeconds, 1))s (Archive size: $archiveSizeMB MB)" -ForegroundColor Green

    # 3. Archive Integrity Verification with '7z t'
    Write-Host "  -> Running 7-Zip archive integrity check (7z t)..." -ForegroundColor Cyan
    $swVerify = [System.Diagnostics.Stopwatch]::StartNew()
    & $SevenZipPath t $archivePath
    if ($LASTEXITCODE -ne 0) {
        throw "Archive integrity check FAILED for $archivePath! Code: $LASTEXITCODE"
    }
    $swVerify.Stop()
    Write-Host "  -> Integrity Check: 100% PASS (Checked in $([math]::Round($swVerify.Elapsed.TotalSeconds, 1))s)" -ForegroundColor Green

    # 4. Record Archive SHA-256
    $archiveHash = Get-FileSha256 $archivePath
    Set-Content -LiteralPath "$archivePath.sha256" -Value "$archiveHash  $(Split-Path -Leaf $archivePath)" -Encoding ascii

    $summaryManifest.packages[$pkg] = @{
        archive_name = Split-Path -Leaf $archivePath
        archive_size_mb = $archiveSizeMB
        archive_sha256 = $archiveHash
        critical_hashes = $criticalHashes
        compression_seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        integrity_verified = $true
    }
}

$stopwatchTotal.Stop()

# 5. Save master summary manifest
$summaryPath = Join-Path $manifestsDir "ai-packages-summary.json"
$summaryManifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding utf8

Write-Host "`n=======================================================" -ForegroundColor Green
Write-Host " All AI Packages compressed & verified successfully!" -ForegroundColor Green
Write-Host " Total time: $([math]::Round($stopwatchTotal.Elapsed.TotalMinutes, 2)) minutes" -ForegroundColor Green
Write-Host " Output archives in: $OutputDir" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
