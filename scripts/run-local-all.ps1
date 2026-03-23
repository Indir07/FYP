$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "scripts\run-backend-local.ps1")
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "scripts\run-frontend-local.ps1")

Write-Host "Started backend and frontend in separate terminals." -ForegroundColor Green

