$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment missing. Run .\scripts\install.ps1 first."
}

& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    throw "Chromium installation failed."
}

Write-Host "PASS: Playwright Chromium installed." -ForegroundColor Green
