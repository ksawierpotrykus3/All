# Automatic install script for the Interception driver (kernel driver)
# Run in PowerShell as Administrator

$ErrorActionPreference = "Stop"

Write-Host "=== Interception driver installer ===" -ForegroundColor Cyan

$zipUrl = "https://github.com/oblitum/Interception/releases/download/v1.0.1/Interception.zip"
$zipFile = Join-Path $PSScriptRoot "Interception.zip"
$extractDir = Join-Path $PSScriptRoot "Interception_installer"

if (-not (Test-Path $extractDir)) {
    Write-Host "[1/3] Downloading the Interception installer from GitHub..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
    
    Write-Host "[2/3] Extracting the archive..." -ForegroundColor Yellow
    Expand-Archive -Path $zipFile -DestinationPath $extractDir -Force
    Remove-Item $zipFile -ErrorAction SilentlyContinue
}

$installerExe = Join-Path $extractDir "Interception\command line installer\install-interception.exe"

if (Test-Path $installerExe) {
    Write-Host "[3/3] Running the driver installer with Administrator privileges..." -ForegroundColor Yellow
    Start-Process -FilePath $installerExe -ArgumentList "/install" -Verb RunAs -Wait
    Write-Host "`n[SUCCESS] The Interception driver has been installed on Windows!" -ForegroundColor Green
    Write-Host "[IMPORTANT] A computer restart is required for the system to load the kernel driver." -ForegroundColor Magenta
} else {
    Write-Host "[ERROR] install-interception.exe not found at $installerExe" -ForegroundColor Red
}