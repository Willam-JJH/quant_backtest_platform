@echo off
chcp 65001 >nul
title Backtest Platform Launcher
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv Python not found: venv\Scripts\python.exe
    echo Please create the venv and install dependencies first.
    echo See backend\requirements.txt for details.
    echo.
    pause
    exit /b 1
)

REM Clean up leftover ngrok process from a previously force-closed window
taskkill /IM ngrok.exe /F >nul 2>&1

"venv\Scripts\python.exe" start.py %*
pause
