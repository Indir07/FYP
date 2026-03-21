param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Set-Location "D:\CryptoVolt\backend"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Python venv not found at backend/.venv. Create it first." -ForegroundColor Yellow
  exit 1
}

& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port $Port
