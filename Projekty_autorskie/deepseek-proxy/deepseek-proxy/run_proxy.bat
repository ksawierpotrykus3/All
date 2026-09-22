@echo off
cd /d "%~dp0"
title DeepSeek Proxy (modular)

:run
echo [%date% %time%] Starting DeepSeek Proxy (modular)...
python -u -m server.main
echo [%date% %time%] Server exited with code %errorlevel%. Restarting in 2s...
timeout /t 2 /nobreak >nul
goto run

