@echo off
chcp 65001 >nul
title Voca Basic - Trình Tạo License Key Bản Quyền
cd /d "%~dp0"

if exist "Voca-Keygen.exe" (
    start "" "Voca-Keygen.exe"
    exit
)

if exist "tools\keygen\dist\Voca-Keygen.exe" (
    start "" "tools\keygen\dist\Voca-Keygen.exe"
    exit
)

if exist ".venv312\Scripts\pythonw.exe" (
    start "" ".venv312\Scripts\pythonw.exe" "tools\keygen\app_keygen.py"
    exit
)

if exist ".venv312\Scripts\python.exe" (
    start "" ".venv312\Scripts\python.exe" "tools\keygen\app_keygen.py"
    exit
)

echo Không tìm thấy file chạy Voca-Keygen! Vui lòng kiểm tra lại.
pause
