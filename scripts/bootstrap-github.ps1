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
$RemoteUrl = "https://github.com/$FullName.git"

if (-not (Test-Path ".git")) {
    git init -b main
    if ($LASTEXITCODE -ne 0) {
        throw "git init failed."
    }
}

git add .
if ($LASTEXITCODE -ne 0) {
    throw "git add failed."
}

git rev-parse --verify HEAD *> $null
$HasCommit = ($LASTEXITCODE -eq 0)

$Changes = git status --porcelain
if (-not $HasCommit) {
    git commit -m "chore: establish verified project baseline"
    if ($LASTEXITCODE -ne 0) {
        throw "Initial git commit failed."
    }
}
elseif ($Changes) {
    git commit -m "chore: update verified project baseline"
    if ($LASTEXITCODE -ne 0) {
        throw "Git commit failed."
    }
}
else {
    Write-Host "INFO: local repository already has a clean commit."
}

$RemoteNames = git remote
$HasOrigin = $RemoteNames -contains "origin"

if ($HasOrigin) {
    $CurrentOrigin = (git remote get-url origin).Trim()
    if ($CurrentOrigin -ne $RemoteUrl) {
        throw "origin points to '$CurrentOrigin', expected '$RemoteUrl'."
    }

    git push -u origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS: pushed main to https://github.com/$FullName" -ForegroundColor Green
        exit 0
    }

    throw "origin exists but push failed."
}

$CreateOutput = & gh repo create $FullName "--$Visibility" --source=. --remote=origin --push `
    --description "Local-first Reddit customer-pain discovery workbench" 2>&1
$CreateExit = $LASTEXITCODE

if ($CreateExit -ne 0) {
    $Text = ($CreateOutput | Out-String).Trim()

    if ($Text -match "Name already exists on this account" -or
        $Text -match "already exists") {
        git remote add origin $RemoteUrl
        if ($LASTEXITCODE -ne 0) {
            throw "Repository exists, but adding origin failed."
        }

        git push -u origin main
        if ($LASTEXITCODE -ne 0) {
            throw "Repository exists, but push failed."
        }

        Write-Host "PASS: connected and pushed to https://github.com/$FullName" -ForegroundColor Green
        exit 0
    }

    throw "GitHub repository creation failed: $Text"
}

Write-Host "PASS: created and pushed https://github.com/$FullName" -ForegroundColor Green
Write-Host "Next: inspect the GitHub Actions CI run."
