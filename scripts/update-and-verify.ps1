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

$Branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Branch) {
    throw "Verification requires a named local branch, not detached HEAD."
}

Invoke-CheckedGit -Step "Git fetch" -Arguments @("fetch", "origin")
Invoke-CheckedGit -Step "Branch synchronization" -Arguments @(
    "switch",
    "-C",
    $Branch,
    "origin/$Branch"
)

$VerifiedBranch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $VerifiedBranch -ne $Branch) {
    throw "Expected $Branch after synchronization, found $VerifiedBranch"
}

$Commit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not resolve the verification commit."
}

Write-Host "Verification branch: $VerifiedBranch" -ForegroundColor Green
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

$EvidenceRoot = Get-ChildItem (Join-Path $ProjectPath "artifacts\verification") -Directory |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if ($null -eq $EvidenceRoot) {
    throw "Verification evidence directory was not created."
}

$CalibrationScript = Join-Path $ProjectPath "scripts\verify-calibration-controls.ps1"
$ControlCorpus = Join-Path $ProjectPath "tests\fixtures\benchmark_calibration_control.jsonl"
$Python = Join-Path $ProjectPath ".venv\Scripts\python.exe"
& $CalibrationScript `
    -Python $Python `
    -EvidenceRoot $EvidenceRoot.FullName `
    -ReviewWorksheet (Join-Path $EvidenceRoot.FullName "benchmark-review-worksheet.csv") `
    -BenchmarkJson (Join-Path $EvidenceRoot.FullName "benchmark.json") `
    -ControlCorpus $ControlCorpus

Write-Host "PASS: synchronized and verified $VerifiedBranch at $Commit." -ForegroundColor Green
