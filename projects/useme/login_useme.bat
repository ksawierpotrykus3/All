@echo off
cd /d "%~dp0"
echo ============================================================
echo   USEME LOGIN HELPER (Konto 1 lub Konto 2)
echo ============================================================
if "%1"=="" (
    .venv\Scripts\python.exe login_useme.py konto1
) else (
    .venv\Scripts\python.exe login_useme.py %1
)
pause
