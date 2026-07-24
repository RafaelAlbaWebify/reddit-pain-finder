[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$Subreddits,
    [string]$RunNamePrefix = "scheduled-reddit",
    [string]$Sort = "new",
    [int]$MaxThreads = 25,
    [int]$MaxComments = 8,
    [string]$Database = "data/research.db",
    [string]$OutputRoot = "output/scheduled"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoPath
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RunDirectory = Join-Path $OutputRoot $Timestamp
New-Item $RunDirectory -ItemType Directory -Force | Out-Null

& ".\.venv\Scripts\python.exe" -m painfinder live-store `
    --subreddits $Subreddits `
    --name "$RunNamePrefix-$Timestamp" `
    --sort $Sort `
    --max-threads $MaxThreads `
    --max-comments $MaxComments `
    --database $Database `
    --artifacts-dir (Join-Path $RunDirectory "browser-evidence") `
    --output (Join-Path $RunDirectory "opportunities.html") `
    --json-output (Join-Path $RunDirectory "collection-result.json")

if ($LASTEXITCODE -ne 0) {
    throw "Scheduled Reddit collection failed with exit code $LASTEXITCODE"
}
