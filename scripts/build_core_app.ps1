# Build Voca Basic Core App (Standalone Lightweight Package)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root 'release\core-electron-builder.json'
$outputBase = Join-Path $root 'release\core-dist'
$finalCoreDir = Join-Path $outputBase 'Voca Basic Core'

Write-Host "=== 1. Building Frontend ===" -ForegroundColor Cyan
Push-Location (Join-Path $root 'frontend')
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with code $LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host "=== 2. Preparing Isolated Staging Environment ===" -ForegroundColor Cyan
$ffmpegSource = Join-Path $root 'release\bin\ffmpeg.exe'
if (-not (Test-Path -LiteralPath $ffmpegSource)) {
    throw "Missing required FFmpeg binary at: $ffmpegSource"
}

New-Item -ItemType Directory -Force -Path $outputBase | Out-Null
$unpacked = Join-Path $outputBase 'win-unpacked'
if (Test-Path -LiteralPath $unpacked) {
    Remove-Item -LiteralPath $unpacked -Recurse -Force
}

Write-Host "=== 3. Packaging Voca Basic Core with electron-builder ===" -ForegroundColor Cyan
Push-Location $root
try {
    & npx electron-builder --config $configPath --dir --x64
    if ($LASTEXITCODE -ne 0) { throw "electron-builder failed with code $LASTEXITCODE" }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $unpacked)) {
    throw "Expected unpacked directory not found: $unpacked"
}

$gitHash = "candidate"
try {
    $resolvedHash = (git rev-parse --short HEAD 2>$null)
    if ($resolvedHash) { $gitHash = $resolvedHash.Trim() }
} catch {}

$candidateName = "Voca Basic Core $gitHash"
$candidateDir = Join-Path $outputBase $candidateName

if (Test-Path -LiteralPath $candidateDir) {
    Remove-Item -LiteralPath $candidateDir -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $candidateDir) {
        $candidateName = "Voca Basic Core $gitHash-" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $candidateDir = Join-Path $outputBase $candidateName
    }
}
Rename-Item -LiteralPath $unpacked -NewName $candidateName

Write-Host "=== 4. Adding AI Package Config, Tools and Helpers ===" -ForegroundColor Cyan
$bundledFfmpeg = Join-Path $candidateDir 'resources\bin\ffmpeg.exe'
if (-not (Test-Path -LiteralPath $bundledFfmpeg)) {
    Write-Host "[WARN] resources\bin\ffmpeg.exe was not created by electron-builder, copying directly..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path (Join-Path $candidateDir 'resources\bin') | Out-Null
    Copy-Item -LiteralPath $ffmpegSource -Destination $bundledFfmpeg -Force
}
if ((Get-Item -LiteralPath $bundledFfmpeg).Length -eq 0) {
    throw "Bundled FFmpeg binary is empty: $bundledFfmpeg"
}
Write-Host "  -> Bundled FFmpeg verified: $bundledFfmpeg ($([math]::Round((Get-Item $bundledFfmpeg).Length/1MB, 2)) MB)" -ForegroundColor Green

# Ensure 7-Zip tools (7z.exe + 7z.dll v26.03) are present in candidate
$sevenZipDir = Join-Path $root 'release\tools\7zip'
if (Test-Path -LiteralPath (Join-Path $sevenZipDir '7z.exe')) {
    Copy-Item -LiteralPath (Join-Path $sevenZipDir '7z.exe') -Destination (Join-Path $candidateDir '7z.exe') -Force
    Copy-Item -LiteralPath (Join-Path $sevenZipDir '7z.dll') -Destination (Join-Path $candidateDir '7z.dll') -Force
    Write-Host "  -> Bundled 7-Zip 26.03 verified in Core candidate" -ForegroundColor Green
}

$defaultConfig = @{
    ai_packages_dir = "./ai-packages"
    description = "Duong dan den thu muc AI Packages. Mac dinh: ./ai-packages (nam canh Voca Basic.exe)"
} | ConvertTo-Json -Depth 4
Set-Content -LiteralPath (Join-Path $candidateDir 'ai-package-config.json') -Value $defaultConfig -Encoding utf8
Set-Content -LiteralPath (Join-Path $candidateDir 'resources\ai-package-config.json') -Value $defaultConfig -Encoding utf8

$batContent = @'
@echo off
chcp 65001 >nul
title Tao Phim Tat Desktop - Voca Basic
setlocal
set "TARGET=%~dp0Voca Basic.exe"
set "WORKDIR=%~dp0"

if not exist "%TARGET%" (
    echo [LOI] Khong tim thay file "Voca Basic.exe"!
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); $shortcut = Join-Path $desktop 'Voca Basic.lnk'; $ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut($shortcut); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%WORKDIR%'; $s.Save(); if (Test-Path -LiteralPath $shortcut) { Write-Host '[THANH CONG] Da tao phim tat Voca Basic ngoai Desktop!' -ForegroundColor Green } else { Write-Host '[LOI] Khong the tao phim tat.' -ForegroundColor Red }"

timeout /t 3 >nul 2>&1
'@
Set-Content -LiteralPath (Join-Path $candidateDir 'Tao-Phim-Tat-Desktop.bat') -Value $batContent -Encoding ascii

$resetContent = @'
@echo off
chcp 65001 >nul
title Reset Du Lieu - Voca Basic
setlocal

tasklist /FI "IMAGENAME eq Voca Basic.exe" 2>nul | find /I "Voca Basic.exe" >nul
if not errorlevel 1 (
    echo.
    echo [LOI] Voca Basic dang chay.
    echo Hay dong ung dung Voca Basic binh thuong, sau do chay lai file nay.
    echo Khong co tien trinh nao bi buoc dung boi cong cu reset.
    echo.
    pause
    exit /b 1
)

set "TARGET_DIR=%LOCALAPPDATA%\Voca Basic"

if exist "%TARGET_DIR%" (
    echo Dang xoa toan bo du lieu cu...
    rmdir /s /q "%TARGET_DIR%"
    echo.
    echo ==========================================================
    echo  [THANH CONG] Da xoa sach toan bo du lieu va ban quyen!
    echo  Ung dung da tro ve BAN TRANG TINH 100%%.
    echo ==========================================================
) else (
    echo.
    echo [THONG BAO] Ung dung hien tai da la ban trang tinh (chua co du lieu).
)

echo.
pause
'@
Set-Content -LiteralPath (Join-Path $candidateDir 'Reset-Data-Ban-Trang.bat') -Value $resetContent -Encoding ascii

Write-Host "=== 5. Promoting Candidate to Standard Core Directory ===" -ForegroundColor Cyan
$activeCoreDir = $candidateDir
try {
    if (Test-Path -LiteralPath $finalCoreDir) {
        $backupName = "Voca Basic Core.old." + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $backupPath = Join-Path $outputBase $backupName
        Rename-Item -LiteralPath $finalCoreDir -NewName $backupName -ErrorAction Stop
        Remove-Item -LiteralPath $backupPath -Recurse -Force -ErrorAction SilentlyContinue
    }
    Copy-Item -LiteralPath $candidateDir -Destination $finalCoreDir -Recurse -Force -ErrorAction Stop
    $activeCoreDir = $finalCoreDir
    Write-Host "=== Successfully promoted to: $finalCoreDir ===" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Could not update standard directory '$finalCoreDir' (likely locked by another process): $_" -ForegroundColor Yellow
    Write-Host "Validated candidate core is preserved at: $candidateDir" -ForegroundColor Yellow
}

$coreSizeMB = [math]::Round(((Get-ChildItem -LiteralPath $activeCoreDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
Write-Host "=== Voca Basic Core App built successfully ===" -ForegroundColor Green
Write-Host "Candidate Location: $candidateDir"
Write-Host "Active Location:    $activeCoreDir"
Write-Host "Size:               $coreSizeMB MB"
