@echo off
chcp 65001 >nul
title Tạo Phím Tắt Voca-Keygen Ra Desktop
cd /d "%~dp0"

echo Đang tạo phím tắt ra màn hình Desktop...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Voca Keygen.lnk')); $s.TargetPath = '%~dp0Voca-Keygen.exe'; $s.WorkingDirectory = '%~dp0'; if (Test-Path '%~dp0release\icon.ico') { $s.IconLocation = '%~dp0release\icon.ico' }; $s.Save()"

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  DA TAO PHIM TAT 'Voca Keygen' NGOAI DESKTOP THANH CONG!
    echo ========================================================
) else (
    echo Co loi khi tao phim tat.
)
pause
