@echo off
title Last Z Bot Launcher
cd /d "%~dp0"
echo ================================================
echo           Last Z Bot - Uruchamianie GUI
echo ================================================
echo.
set "LASTZ_BUILD_MODE=dev"
echo Uruchamianie .venv\Scripts\python.exe -m mvp.main...
".venv\Scripts\python.exe" -m mvp.main
echo.
echo ================================================
echo Program zakonczyl dzialanie. Kod wyjscia: %ERRORLEVEL%
echo ================================================
pause
