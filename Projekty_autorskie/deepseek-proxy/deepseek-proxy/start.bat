@echo off
cd /d "%~dp0"
echo Starting DeepSeek V4-Pro Proxy on http://localhost:4570
echo.
echo IDE config: http://localhost:4570/v1  |  API Key: anything
echo Model: deepseek-v4-pro
echo.
echo First time? Run:
echo   pip install -r requirements.txt
echo   python -m playwright install firefox
echo.
python server.py
if errorlevel 1 pause
