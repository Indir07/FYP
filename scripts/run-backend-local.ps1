param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "backend")

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Python venv not found at backend/.venv. Create it first." -ForegroundColor Yellow
  exit 1
}

# --host 0.0.0.0: works with http://localhost:8000 and avoids some Windows IPv4/IPv6 quirks
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port $Port
