@echo off
title Jio Datsugoku
cd /d "%~dp0"

echo ========================================================
echo       Starting Jio Datsugoku (STB Jailbreak Suite)
echo ========================================================
echo.

if exist "JioDatsugoku.exe" (
    start "" "JioDatsugoku.exe"
    exit /b 0
)

if exist "JioSTBToolbox.exe" (
    start "" "JioSTBToolbox.exe"
    exit /b 0
)

if exist "dist\JioDatsugoku.exe" (
    start "" "dist\JioDatsugoku.exe"
    exit /b 0
)

python jio_toolbox_gui.py
