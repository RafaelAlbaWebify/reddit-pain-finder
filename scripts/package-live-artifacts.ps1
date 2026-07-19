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

$Required = @(
    "live-report.html",
    "traces\collection-trace.zip"
)

$Missing = @()
foreach ($Relative in $Required) {
    if (-not (Test-Path (Join-Path $Source $Relative))) {
        $Missing += $Relative
    }
}

$Manifest = [ordered]@{
    created_at = (Get-Date).ToString("o")
    project_path = $ProjectPath
    source_folder = $Source
    missing_required_files = $Missing
    files = @(
        Get-ChildItem $Source -Recurse -File |
            ForEach-Object {
                [ordered]@{
                    relative_path = $_.FullName.Substring($Source.Length + 1)
                    size_bytes = $_.Length
                    modified_at = $_.LastWriteTime.ToString("o")
                }
            }
    )
}

$ManifestPath = Join-Path $Source "artifact-manifest.json"
$Manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $ManifestPath -Encoding UTF8

Compress-Archive -Path "$Source\*" -DestinationPath $Destination -Force

Write-Host "PASS: live evidence packaged." -ForegroundColor Green
Write-Host "ZIP: $Destination"

if ($Missing.Count -gt 0) {
    Write-Warning ("Missing expected files: " + ($Missing -join ", "))
}
