param(
    [string]$RepoName = "reddit-pain-finder",
    [ValidateSet("private", "public")]
    [string]$Visibility = "private",
    [string]$Owner = ""
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git was not found."
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI 'gh' was not found."
}

& gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated."
}

if (-not $Owner) {
    $Owner = (& gh api user --jq .login).Trim()
}
$FullName = "$Owner/$RepoName"
$RemoteUrl = "https://github.com/$FullName.git"

if (-not (Test-Path ".git")) {
    & git init -b main
    if ($LASTEXITCODE -ne 0) { throw "git init failed." }
}

& git add .
if ($LASTEXITCODE -ne 0) { throw "git add failed." }

& git rev-parse --verify HEAD *> $null
$HasCommit = ($LASTEXITCODE -eq 0)
$Changes = & git status --porcelain

if (-not $HasCommit) {
    & git commit -m "chore: establish verified project baseline"
    if ($LASTEXITCODE -ne 0) { throw "Initial commit failed." }
}
elseif ($Changes) {
    & git commit -m "chore: update verified project baseline"
    if ($LASTEXITCODE -ne 0) { throw "Commit failed." }
}

$Origin = & git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    if ($Origin.Trim() -ne $RemoteUrl) {
        throw "origin points to '$Origin', expected '$RemoteUrl'."
    }
    & git push -u origin main
    if ($LASTEXITCODE -ne 0) { throw "Push failed." }
    Write-Host "PASS: pushed https://github.com/$FullName" -ForegroundColor Green
    exit 0
}

$OldPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & gh repo create $FullName "--$Visibility" --source=. --remote=origin --push `
        --description "Local-first Reddit customer-pain discovery workbench"
    $CreateExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $OldPreference
}

if ($CreateExit -ne 0) {
    throw "GitHub repository creation failed with exit code $CreateExit."
}

Write-Host "PASS: created and pushed https://github.com/$FullName" -ForegroundColor Green
