@echo off
title AETHER QUANT DESK - 24/7 Windows Server Runner
color 0B
echo ========================================================
echo   AETHER QUANT DESK - 24/7 WINDOWS EC2 LAUNCHER
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from python.org and check "Add to PATH".
    pause
    exit /b
)

echo [2/3] Installing lightweight dependencies...
pip install -r requirements.txt --quiet --disable-pip-version-check

echo [3/3] Starting AETHER 24/7 Trading Desk...
echo.
echo ========================================================
echo  Dashboard running at: http://localhost:8000
echo  External URL:        http://13.233.118.122:8000
echo ========================================================
echo.

python -m app.main

pause
