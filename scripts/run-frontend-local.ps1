param(
  [int]$Port = 5173
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")

if (-not (Test-Path ".\node_modules")) {
  Write-Host "node_modules not found. Run: npm install" -ForegroundColor Yellow
  exit 1
}

& npm run dev -- --host --port $Port
