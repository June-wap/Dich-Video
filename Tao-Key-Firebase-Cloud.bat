@echo off
chcp 65001 >nul
title VOCA BASIC - TAO KEY & QUAN LY BAN QUYEN CLOUD

cd /d "%~dp0server_keygen"

call "Quan-Ly-Ban-Quyen.bat" %*
