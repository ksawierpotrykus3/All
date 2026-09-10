# CORTEX Release Build Script
# Usage: .\scripts\build-release.ps1
# Buduje release z wyborem sciezki instalacji (NSIS oneClick: false)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# Auto-detect Python from PATH
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $PythonExe) {
    Write-Error "Python not found in PATH. Install Python and add it to PATH."
    exit 1
}
$PythonPath = Split-Path -Parent $PythonExe

# Add Python to PATH and set node-gyp env vars
$env:PATH = "$PythonPath;$PythonPath\Scripts;$env:PATH"
$env:PYTHON = $PythonExe
$env:npm_config_python = $PythonExe

Write-Host "[CORTEX] Python: $env:PYTHON" -ForegroundColor Cyan
Write-Host "[CORTEX] Building release..." -ForegroundColor Cyan

Set-Location $ProjectRoot
npm run electron:build

Write-Host "[CORTEX] Done!" -ForegroundColor Green
