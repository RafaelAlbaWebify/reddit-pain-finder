param(
    [string]$ProjectPath = "$HOME\Downloads\reddit-pain-finder",
    [string]$RunFolder = "artifacts\live-smoke"
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectPath

$Source = Join-Path $ProjectPath $RunFolder
if (-not (Test-Path $Source)) {
    throw "Live artifact folder not found: $Source"
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Destination = "$HOME\Downloads\reddit-pain-finder-live-artifacts-$Stamp.zip"
$Staging = Join-Path $env:TEMP "reddit-pain-finder-live-artifacts-$Stamp"

if (Test-Path $Staging) {
    Remove-Item $Staging -Recurse -Force
}
New-Item -ItemType Directory -Force $Staging | Out-Null

$Allowed = @(
    "live-report.html",
    "collection-result.json",
    "screenshots",
    "traces"
)

$Copied = @()
foreach ($Relative in $Allowed) {
    $Item = Join-Path $Source $Relative
    if (Test-Path $Item) {
        Copy-Item $Item $Staging -Recurse -Force
        $Copied += $Relative
    }
}

$Manifest = [ordered]@{
    created_at = (Get-Date).ToString("o")
    source_folder = $Source
    included = $Copied
    excluded_sensitive = @(
        "browser-profile",
        "cookies",
        "login data",
        "local storage",
        "session storage"
    )
    files = @(
        Get-ChildItem $Staging -Recurse -File |
            ForEach-Object {
                [ordered]@{
                    relative_path = $_.FullName.Substring($Staging.Length + 1)
                    size_bytes = $_.Length
                    modified_at = $_.LastWriteTime.ToString("o")
                }
            }
    )
}

$Manifest |
    ConvertTo-Json -Depth 6 |
    Set-Content -Path (Join-Path $Staging "artifact-manifest.json") -Encoding UTF8

Compress-Archive -Path "$Staging\*" -DestinationPath $Destination -Force
Remove-Item $Staging -Recurse -Force

Write-Host "PASS: privacy-safe live evidence packaged." -ForegroundColor Green
Write-Host "ZIP: $Destination"
Write-Host "Browser profile and cookies were excluded."
