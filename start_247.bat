@echo off
title Grok Trading Brain - 24/7 Engine
cd /d "%~dp0"
set PYTHONPATH=%~dp0

echo ===================================================
echo   Grok Trading Brain 24/7 Autonomous Trading Engine
echo   - Mode: REAL
echo   - Delta Exchange India: CONNECTED
echo   - Coinbase Advanced: CONNECTED
echo ===================================================

:loop
echo [%date% %time%] Starting Engine...
"%~dp0venv\Scripts\python.exe" -m app.main
echo [%date% %time%] Engine stopped or crashed. Auto-restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
