$ErrorActionPreference = "Stop"

$root = "D:\CryptoVolt"

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$root\scripts\run-backend-local.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$root\scripts\run-frontend-local.ps1"

Write-Host "Started backend and frontend in separate terminals." -ForegroundColor Green
