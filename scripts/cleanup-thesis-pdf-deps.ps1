<#
  Removes Python packages that were only needed for the deleted thesis/Markdown→PDF
  tooling (markdown, xhtml2pdf and common transitive deps). Safe to run if those
  packages are not used elsewhere in your project.

  Optional: clears npm cache (npx md-to-pdf may have downloaded Puppeteer there).

  Usage (from repo root):
    .\scripts\cleanup-thesis-pdf-deps.ps1
    .\scripts\cleanup-thesis-pdf-deps.ps1 -CleanNpmCache
#>
param(
  [switch]$CleanNpmCache
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$VenvPip = Join-Path $Root "backend\.venv\Scripts\pip.exe"

if (-not (Test-Path $VenvPip)) {
  Write-Host "No pip at backend\.venv — skip Python uninstall (create venv or uninstall manually)." -ForegroundColor Yellow
} else {
  $pkgs = @(
    "xhtml2pdf",
    "markdown",
    "pyHanko",
    "pyhanko-certvalidator",
    "pypdf",
    "svglib",
    "html5lib",
    "reportlab",
    "arabic-reshaper",
    "oss2",
    "python-bidi"
  )
  foreach ($p in $pkgs) {
    Write-Host "pip uninstall -y $p"
    & $VenvPip uninstall -y $p 2>&1 | Out-Null
  }
  Write-Host "Done Python uninstall attempts (ignore 'not installed' messages)." -ForegroundColor Green
}

if ($CleanNpmCache) {
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "npm cache clean --force"
    npm cache clean --force
  } else {
    Write-Host "npm not found; skip npm cache." -ForegroundColor Yellow
  }
}
