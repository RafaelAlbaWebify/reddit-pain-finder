param(
    [Parameter(Mandatory=$true)]
    [string]$ZipPath,
    [string]$Destination = "$HOME\Downloads\reddit-pain-finder"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ZipPath)) {
    throw "ZIP not found: $ZipPath"
}
if (Test-Path $Destination) {
    throw "Destination already exists: $Destination"
}

Expand-Archive -Path $ZipPath -DestinationPath (Split-Path -Parent $Destination)
Set-Location $Destination

Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\install.ps1
.\scripts\verify.ps1

Write-Host "PASS: project expanded, installed and verified at $Destination" -ForegroundColor Green
Write-Host "To create the GitHub repository, run:"
Write-Host ".\scripts\bootstrap-github.ps1 -Visibility private"
