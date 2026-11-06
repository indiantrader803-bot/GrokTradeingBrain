@echo off
cd /d "%~dp0"
echo Starting Grok Trading Brain (24/7 Mode)...
:loop
"%~dp0venv\Scripts\python.exe" -m app.main
echo Grok Trading Brain stopped or crashed. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
