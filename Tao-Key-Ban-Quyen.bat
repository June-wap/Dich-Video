@echo off
chcp 65001 >nul
title Voca Basic - Bo Tao Ma Ban Quyen (Keygen)
cd /d "%~dp0"

set "PY_EXE="
if exist "F:\Voca-CP8-Build\cp86\staged-runtime\runtime-main\python.exe" (
    set "PY_EXE=F:\Voca-CP8-Build\cp86\staged-runtime\runtime-main\python.exe"
) else if exist "%LOCALAPPDATA%\Voca Basic\runtime-main\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Voca Basic\runtime-main\python.exe"
) else if exist "..\runtime-main\python.exe" (
    set "PY_EXE=..\runtime-main\python.exe"
) else (
    set "PY_EXE=python"
)

"%PY_EXE%" "scripts\generate_license.py"

echo.
pause
