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
    throw "GitHub CLI 'gh' was not found. Install it and run: gh auth login"
}

gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated. Run: gh auth login"
}

if (-not $Owner) {
    $Owner = (gh api user --jq .login).Trim()
}
$FullName = "$Owner/$RepoName"

if (-not (Test-Path ".git")) {
    git init -b main
}
git add .
git commit -m "chore: establish verified vertical slice zero"

$existing = gh repo view $FullName --json nameWithOwner 2>$null
if ($LASTEXITCODE -eq 0) {
    throw "Repository $FullName already exists. This script will not overwrite it."
}

gh repo create $FullName "--$Visibility" --source=. --remote=origin --push `
    --description "Local-first Reddit customer-pain discovery workbench"

Write-Host "PASS: created and pushed https://github.com/$FullName" -ForegroundColor Green
Write-Host "Next: inspect the CI run before beginning live Reddit collection."
