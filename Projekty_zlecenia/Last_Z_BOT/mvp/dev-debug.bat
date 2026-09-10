@echo off
echo ================================================
echo        Last Z Bot MVP - FULL DEBUG MODE
echo ================================================
echo.
echo  LOG file    : mvp/logs/lastz_bot.log
echo  LogLevel    : DEBUG
echo.
echo  Press Ctrl+C to stop
echo.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run: uv sync --extra dev
    pause
    exit /b 1
)
rem DEV build: skip remote license validation (requires backend_url/license_key)
set "LASTZ_BUILD_MODE=dev"
".venv\Scripts\python.exe" -m mvp.main --debug
echo.
echo == Bot stopped. Log saved in mvp/logs/ ==
echo.
pause
