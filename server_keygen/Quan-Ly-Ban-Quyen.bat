@echo off
chcp 65001 >nul
title VOCA BASIC - QUAN LY BAN QUYEN FIREBASE CLOUD

cd /d "%~dp0"

echo =====================================================================
echo       VOCA BASIC - QUAN LY BAN QUYEN VA TAO KEY CLOUD FIRESTORE
echo =====================================================================
echo.

:: Tim Python tu .venv312 hoac moi truong he thong
set "PY_BIN="
if exist "..\.venv312\Scripts\python.exe" (
    set "PY_BIN=..\.venv312\Scripts\python.exe"
) else if exist ".venv312\Scripts\python.exe" (
    set "PY_BIN=.venv312\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_BIN=python"
    )
)

if "%PY_BIN%"=="" (
    echo [LOI] Khong tim thay Python!
    echo Vui long cai dat Python 3.10+ hoac chay tren moi truong co Python.
    echo.
    pause
    exit /b 1
)

:: Kiem tra file serviceAccountKey.json
if not exist "serviceAccountKey.json" (
    echo =====================================================================
    echo [CANH BAO] CHUA CO FILE serviceAccountKey.json
    echo =====================================================================
    echo De ket noi den Firebase Cloud cua ban (vocaltts), ban can:
    echo 1. Truy cap Firebase Console: https://console.firebase.google.com
    echo 2. Chon project vocaltts -> Project Settings -> Service accounts
    echo 3. Bam 'Generate new private key' de tai file JSON
    echo 4. Doi ten file thanh 'serviceAccountKey.json' va dat vao thu muc:
    echo    %~dp0
    echo =====================================================================
    echo.
    echo Nhap Enter de tiep tuc kiem tra (neu vua copy vao)...
    pause >nul
)

:: Chay keygen.py
"%PY_BIN%" keygen.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Chuong trinh ket thuc voi ma loi %ERRORLEVEL%.
)

pause
