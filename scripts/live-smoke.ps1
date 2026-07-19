param(
    [string[]]$Subreddits = @("smallbusiness"),
    [ValidateSet("new", "hot", "rising")]
    [string]$Sort = "new",
    [int]$MaxThreads = 3,
    [int]$MaxComments = 10
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment missing. Run .\scripts\install.ps1 first."
}

$joined = $Subreddits -join ","
& $python -m painfinder live-smoke `
    --subreddits $joined `
    --sort $Sort `
    --max-threads $MaxThreads `
    --max-comments $MaxComments `
    --artifacts-dir "artifacts\live-smoke"

if ($LASTEXITCODE -ne 0) {
    throw "Live smoke command failed. Return artifacts\live-smoke."
}
