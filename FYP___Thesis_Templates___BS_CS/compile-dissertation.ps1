# Build dissertation.pdf — XeLaTeX + Biber (run in PowerShell from this folder)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$miktexBin = Join-Path $env:LOCALAPPDATA "Programs\MiKTeX\miktex\bin\x64"
$xelatex = Join-Path $miktexBin "xelatex.exe"
$biber   = Join-Path $miktexBin "biber.exe"

if (-not (Test-Path $xelatex)) {
    Write-Host "Install MiKTeX first: winget install MiKTeX.MiKTeX" -ForegroundColor Red
    exit 1
}

$env:Path = "$miktexBin;$env:Path"
# First-time builds: let MiKTeX install missing packages (GUI may appear if policy blocks this)
& (Join-Path $miktexBin "initexmf.exe") --set-config-value=[MPM]AutoInstall=1 2>$null

$argsXe = @("-interaction=nonstopmode", "dissertation.tex")

Write-Host "xelatex (1/4)..." -ForegroundColor Cyan
& $xelatex @argsXe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "biber..." -ForegroundColor Cyan
& $biber "dissertation"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "xelatex (2/4)..." -ForegroundColor Cyan
& $xelatex @argsXe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "xelatex (3/4)..." -ForegroundColor Cyan
& $xelatex @argsXe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$pdf = Join-Path $PSScriptRoot "dissertation.pdf"
if (Test-Path $pdf) { Write-Host "Built: $pdf" -ForegroundColor Green }
else { Write-Host "PDF missing" -ForegroundColor Red; exit 1 }
