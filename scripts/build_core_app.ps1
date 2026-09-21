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

Write-Host "=== 2. Cleaning Previous Core Output ===" -ForegroundColor Cyan
if (Test-Path -LiteralPath $outputBase) {
    Remove-Item -LiteralPath $outputBase -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "=== 3. Packaging Voca Basic Core with electron-builder ===" -ForegroundColor Cyan
Push-Location $root
try {
    & npx electron-builder --config $configPath --dir --x64
    if ($LASTEXITCODE -ne 0) { throw "electron-builder failed with code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$unpacked = Join-Path $outputBase 'win-unpacked'
if (-not (Test-Path -LiteralPath $unpacked)) {
    throw "Expected unpacked directory not found: $unpacked"
}

if (Test-Path -LiteralPath $finalCoreDir) {
    Remove-Item -LiteralPath $finalCoreDir -Recurse -Force
}
Rename-Item -LiteralPath $unpacked -NewName 'Voca Basic Core'

Write-Host "=== 4. Adding AI Package Config and Desktop Shortcut Helper ===" -ForegroundColor Cyan
$defaultConfig = @{
    ai_packages_dir = "./ai-packages"
    description = "Duong dan den thu muc AI Packages. Mac dinh: ./ai-packages (nam canh Voca Basic.exe)"
} | ConvertTo-Json -Depth 4
Set-Content -LiteralPath (Join-Path $finalCoreDir 'ai-package-config.json') -Value $defaultConfig -Encoding utf8
Set-Content -LiteralPath (Join-Path $finalCoreDir 'resources\ai-package-config.json') -Value $defaultConfig -Encoding utf8

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
Set-Content -LiteralPath (Join-Path $finalCoreDir 'Tao-Phim-Tat-Desktop.bat') -Value $batContent -Encoding ascii

$resetContent = @'
@echo off
chcp 65001 >nul
title Reset Du Lieu - Voca Basic
setlocal

echo Dang dong Voca Basic neu dang chay...
taskkill /F /IM "Voca Basic.exe" >nul 2>&1
taskkill /F /IM "python.exe" >nul 2>&1

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
Set-Content -LiteralPath (Join-Path $finalCoreDir 'Reset-Data-Ban-Trang.bat') -Value $resetContent -Encoding ascii

$coreSizeMB = [math]::Round(((Get-ChildItem -LiteralPath $finalCoreDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
Write-Host "=== Voca Basic Core App built successfully ===" -ForegroundColor Green
Write-Host "Location: $finalCoreDir"
Write-Host "Size: $coreSizeMB MB"
