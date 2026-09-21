# =======================================================
#    VOCA BASIC - AI PACKAGES INTEGRITY VERIFIER
# =======================================================
param(
    [string]$PackagesDir = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   KIEM TRA TINH TOAN VEN CAC GOI VBO AI PACKAGES     " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

function Get-FileSha256([string]$filePath) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($filePath)
    try {
        $hashBytes = $sha.ComputeHash($stream)
        return (-join ($hashBytes | ForEach-Object { "{0:x2}" -f $_ }))
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

$summaryPath = Join-Path $PackagesDir "manifests\ai-packages-summary.json"
if (-not (Test-Path -LiteralPath $summaryPath)) {
    throw "Khong tim thay file manifest tong hop tai: $summaryPath"
}

$manifest = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
$allPass = $true

foreach ($pkgKey in $manifest.packages.PSObject.Properties.Name) {
    $pkgInfo = $manifest.packages.$pkgKey
    $archivePath = Join-Path $PackagesDir $pkgInfo.archive_name

    Write-Host "`nDang kiem tra: $($pkgInfo.archive_name)..." -ForegroundColor Yellow
    if (-not (Test-Path -LiteralPath $archivePath)) {
        Write-Host "  [THAT BAI] File khong ton tai: $archivePath" -ForegroundColor Red
        $allPass = $false
        continue
    }

    $actualHash = Get-FileSha256 $archivePath
    if ($actualHash.ToLower() -eq $pkgInfo.archive_sha256.ToLower()) {
        Write-Host "  [OK] SHA-256 khop: $actualHash" -ForegroundColor Green
    } else {
        Write-Host "  [THAT BAI] SHA-256 khong khop!" -ForegroundColor Red
        Write-Host "    Expected: $($pkgInfo.archive_sha256)" -ForegroundColor Red
        Write-Host "    Actual  : $actualHash" -ForegroundColor Red
        $allPass = $false
    }
}

Write-Host "`n=======================================================" -ForegroundColor Cyan
if ($allPass) {
    Write-Host " KET QUA: TAT CA CAC GOI AI HOP LE 100%! SAN SANG!   " -ForegroundColor Green
} else {
    Write-Host " KET QUA: CO LOI HOAC SAI LECH MA BAM SHA-256!        " -ForegroundColor Red
}
Write-Host "=======================================================" -ForegroundColor Cyan
