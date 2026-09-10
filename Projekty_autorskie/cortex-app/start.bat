@echo off
setlocal
cd /d "%~dp0"

rem === Cortex uruchamiany samodzielnie ===
rem Proxy DeepSeek (deepseek-proxy-clean/server.py) uruchamiasz OSOBNO.
rem Cortex jedynie pyta o jego status na http://localhost:4570.

echo Uruchamiam Cortex...
npm run dev