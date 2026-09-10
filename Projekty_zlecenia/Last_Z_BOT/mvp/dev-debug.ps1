# Last Z Bot MVP - FULL DEBUG MODE
# Launch from PowerShell: .\mvp\dev-debug.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
Set-Location -LiteralPath $projectRoot

$Env:PYTHONUNBUFFERED = 1
$Env:LASTZ_DEV_MODE = "1"
$Env:LASTZ_BUILD_MODE = "dev"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "       Last Z Bot MVP - FULL DEBUG MODE         " -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  LOG file    : mvp/logs/lastz_bot.log" -ForegroundColor DarkGray
Write-Host "  LogLevel    : DEBUG" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

try {
    # Use Start-Process with -Wait to properly wait for GUI app
    $proc = Start-Process -FilePath "python" -ArgumentList "-m", "mvp.main", "--debug", "--dev" -Wait -NoNewWindow -PassThru
    Write-Host "Process exited with code: $($proc.ExitCode)" -ForegroundColor DarkGray
} catch {
    Write-Host "  CRASH: $_" -ForegroundColor Red
} finally {
    Write-Host ""
    Write-Host "== Bot stopped. Log saved in mvp/logs/ ==" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to close"
}