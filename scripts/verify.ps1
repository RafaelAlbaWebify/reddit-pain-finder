$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment missing. Run .\scripts\install.ps1 first."
}

& $python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw "ruff failed" }

& $python -m mypy
if ($LASTEXITCODE -ne 0) { throw "mypy failed" }

& $python -m pytest --cov=painfinder --cov-report=term-missing --cov-fail-under=85
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

New-Item -ItemType Directory -Force output | Out-Null
& $python -m painfinder demo `
    --input tests\fixtures\reddit_thread.html `
    --output output\fixture-report.html
if ($LASTEXITCODE -ne 0) { throw "fixture demo failed" }

Write-Host "PASS: lint, type checks, tests, coverage and fixture report succeeded." -ForegroundColor Green
