param(
    [switch]$IncludeHackerNewsSmoke
)

$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath

function Invoke-CheckedGit {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $Output = & git @Arguments 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }

    $Output | ForEach-Object { Write-Host $_ }
    if ($ExitCode -ne 0) {
        throw "$Step failed with exit code $ExitCode"
    }
}

if (-not (Test-Path ".git")) {
    throw "Git repository not found at $ProjectPath"
}

$Status = & git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect Git working-tree status."
}
if ($Status) {
    Write-Host "Local changes detected:" -ForegroundColor Yellow
    $Status | ForEach-Object { Write-Host $_ }
    throw "Commit, stash, or discard local changes before verification."
}

Invoke-CheckedGit -Step "Git fetch" -Arguments @("fetch", "origin")
Invoke-CheckedGit -Step "Branch synchronization" -Arguments @(
    "switch",
    "-C",
    "feat/release-readiness",
    "origin/feat/release-readiness"
)

$Branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $Branch -ne "feat/release-readiness") {
    throw "Expected feat/release-readiness, found $Branch"
}

$Commit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not resolve the verification commit."
}

Write-Host "Verification branch: $Branch" -ForegroundColor Green
Write-Host "Verification commit: $Commit" -ForegroundColor Green

$VerificationScript = Join-Path $ProjectPath "scripts\verify-mvp.ps1"
if (-not (Test-Path $VerificationScript)) {
    throw "Verification script not found: $VerificationScript"
}

if ($IncludeHackerNewsSmoke) {
    & $VerificationScript -IncludeHackerNewsSmoke
}
else {
    & $VerificationScript
}
