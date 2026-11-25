# HelpVisual AI - start the backend and the frontend, then open the app.
$root = $PSScriptRoot
if (-not (Test-Path "$root\backend\.venv")) {
    Write-Host "Run setup first: double-click setup.cmd" -ForegroundColor Red
    exit 1
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"
Write-Host "Starting... the app opens in your browser in a few seconds." -ForegroundColor Cyan
Start-Sleep -Seconds 8
Start-Process "http://localhost:5173"
