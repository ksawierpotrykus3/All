@echo off
cd /d "%~dp0"
echo ============================================================
echo   USEME CORE ENGINE
echo ============================================================
.venv\Scripts\python.exe -u engine.py %*
pause
