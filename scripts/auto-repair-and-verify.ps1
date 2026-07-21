param(
    [switch]$IncludeHackerNewsSmoke
)

$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath

$Python = Join-Path $ProjectPath ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}
if (-not (Test-Path ".git")) {
    throw "Git repository not found at $ProjectPath"
}

$Branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Branch) {
    throw "A normal local branch must be selected; detached HEAD is not supported."
}

$Status = & git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect Git working-tree status."
}
if ($Status) {
    throw "Working tree is not clean. Commit, stash, or discard existing changes first."
}

& git fetch origin
if ($LASTEXITCODE -ne 0) {
    throw "Git fetch failed."
}

& git show-ref --verify --quiet "refs/remotes/origin/$Branch"
if ($LASTEXITCODE -ne 0) {
    throw "Remote branch origin/$Branch does not exist."
}

$Ahead = [int]((& git rev-list --count "origin/$Branch..$Branch").Trim())
$Behind = [int]((& git rev-list --count "$Branch..origin/$Branch").Trim())
if ($Ahead -gt 0) {
    throw "Local branch has $Ahead unpushed commit(s); automatic repair refuses to rewrite or hide them."
}
if ($Behind -gt 0) {
    & git reset --hard "origin/$Branch"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not synchronize $Branch with origin/$Branch."
    }
}

$Before = (& git rev-parse HEAD).Trim()
Write-Host "Repair branch: $Branch" -ForegroundColor Green
Write-Host "Starting commit: $Before" -ForegroundColor Green

& $Python -m ruff format .
if ($LASTEXITCODE -ne 0) {
    throw "Ruff formatter failed."
}
& $Python -m ruff check . --fix
if ($LASTEXITCODE -ne 0) {
    throw "Ruff safe-fix pass failed."
}

$ChangedFiles = @(& git diff --name-only)
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect automated changes."
}

if ($ChangedFiles.Count -gt 0) {
    $UnsafeFiles = @($ChangedFiles | Where-Object { $_ -notmatch '\.py$' })
    if ($UnsafeFiles.Count -gt 0) {
        Write-Host "Unexpected files changed by repair:" -ForegroundColor Yellow
        $UnsafeFiles | ForEach-Object { Write-Host $_ }
        & git reset --hard $Before | Out-Null
        throw "Automatic repair may only modify Python files. All changes were discarded."
    }

    Write-Host "Mechanical repairs applied:" -ForegroundColor Cyan
    $ChangedFiles | ForEach-Object { Write-Host $_ }

    & $Python -m ruff check .
    if ($LASTEXITCODE -ne 0) {
        & git reset --hard $Before | Out-Null
        throw "Ruff still fails after safe repair. All changes were discarded."
    }

    $LocalVerification = Join-Path $ProjectPath "scripts\verify-mvp.ps1"
    try {
        if ($IncludeHackerNewsSmoke) {
            & $LocalVerification -IncludeHackerNewsSmoke
        }
        else {
            & $LocalVerification
        }
    }
    catch {
        & git reset --hard $Before | Out-Null
        throw "Complete verification failed after mechanical repair. All changes were discarded. $($_.Exception.Message)"
    }

    & git add -- $ChangedFiles
    if ($LASTEXITCODE -ne 0) {
        & git reset --hard $Before | Out-Null
        throw "Could not stage mechanical repairs."
    }
    & git commit -m "style: apply automated Ruff repairs"
    if ($LASTEXITCODE -ne 0) {
        & git reset --hard $Before | Out-Null
        throw "Could not commit mechanical repairs."
    }
    & git push origin $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "Mechanical repair commit passed verification and was committed locally, but push failed."
    }
}
else {
    Write-Host "No mechanical Ruff repairs were needed." -ForegroundColor Green
}

$VerificationScript = Join-Path $ProjectPath "scripts\update-and-verify.ps1"
if ($IncludeHackerNewsSmoke) {
    & $VerificationScript -IncludeHackerNewsSmoke
}
else {
    & $VerificationScript
}
if (-not $?) {
    throw "Authoritative verification failed after synchronization."
}

$Final = (& git rev-parse HEAD).Trim()
Write-Host "PASS: repaired if needed and verified $Branch at $Final." -ForegroundColor Green
