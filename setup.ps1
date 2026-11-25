# HelpVisual AI - one-time setup on Windows.
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File setup.ps1   (or double-click setup.cmd)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Need($command, $hint) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        Write-Host "Missing: $command. $hint" -ForegroundColor Red
        exit 1
    }
}
Need "python" "Install Python 3.11 or newer from python.org and tick 'Add to PATH'."
Need "npm" "Install Node.js 20 or newer from nodejs.org."

Write-Host "1/3  Backend: creating the Python environment and installing packages..." -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "     Created backend\.env from the example." -ForegroundColor Yellow
}

Write-Host "2/3  Frontend: installing packages..." -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install --no-audit --no-fund

Write-Host "3/3  Done." -ForegroundColor Green
Write-Host ""
Write-Host "Next:"
Write-Host "  1. In Kaggle, import kaggle\helpvisual_ml_server.ipynb (GPU T4 x2, Internet on) and Run All."
Write-Host "  2. Paste the lines it prints into a PowerShell window in the backend folder (they update backend\.env)."
Write-Host "  3. Double-click start.cmd."
Set-Location $root
