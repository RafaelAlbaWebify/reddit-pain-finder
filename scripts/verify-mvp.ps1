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

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$EvidenceRoot = Join-Path $ProjectPath "artifacts\verification\$Stamp"
$Database = Join-Path $EvidenceRoot "research.db"
$RestoredDatabase = Join-Path $EvidenceRoot "restored.db"
$StoreResult = Join-Path $EvidenceRoot "discover-store.json"
$ReviewWorksheet = Join-Path $EvidenceRoot "benchmark-review-worksheet.csv"
$ResolvedReviewWorksheet = Join-Path $EvidenceRoot "benchmark-review-resolved.csv"
$ImportedBenchmarkCorpus = Join-Path $EvidenceRoot "benchmark-review-imported.jsonl"
$RedditFixture = Join-Path $ProjectPath "tests\fixtures\reddit_thread.html"
$Fixture = Join-Path $ProjectPath "tests\fixtures\imported_evidence.jsonl"
$BenchmarkCorpus = Join-Path $ProjectPath "tests\fixtures\benchmark_corpus.jsonl"
New-Item -ItemType Directory -Force $EvidenceRoot | Out-Null

foreach ($RequiredInput in @($RedditFixture, $Fixture, $BenchmarkCorpus)) {
    if (-not (Test-Path $RequiredInput)) {
        throw "Verification input missing: $RequiredInput"
    }
}

function Invoke-CheckedNative {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    $PreviousPreference = $ErrorActionPreference
    try {
        # Native tools may write normal progress or warnings to stderr. Capture that
        # output and use the process exit code as the source of truth.
        $ErrorActionPreference = "Continue"
        $Output = & $Command 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }

    if ($ExitCode -ne 0) {
        $Output | ForEach-Object { Write-Host $_ }
        throw "$Step failed with exit code $ExitCode"
    }

    return $Output
}

Write-Host "[1/12] Ruff" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Ruff" -Command {
    & $Python -m ruff check .
}

Write-Host "[2/12] Mypy" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Mypy" -Command {
    & $Python -m mypy
}

Write-Host "[3/12] Pytest and coverage" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Pytest" -Command {
    & $Python -m pytest `
        --cov=painfinder `
        --cov-report=term-missing `
        --cov-report="xml:$EvidenceRoot\coverage.xml" `
        --cov-fail-under=85
}

Write-Host "[4/12] Fixture report" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Fixture demo" -Command {
    & $Python -m painfinder demo `
        --input $RedditFixture `
        --output "$EvidenceRoot\fixture-report.html"
}

Write-Host "[5/12] Imported discovery" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Imported discovery" -Command {
    & $Python -m painfinder discover `
        --input $Fixture `
        --output "$EvidenceRoot\opportunities.html"
}

Write-Host "[6/12] Persisted discovery" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Persisted discovery" -Command {
    & $Python -m painfinder discover-store `
        --input $Fixture `
        --name "MVP verification $Stamp" `
        --database $Database `
        --output "$EvidenceRoot\stored-opportunities.html" `
        --json-output $StoreResult
} | Tee-Object -FilePath "$EvidenceRoot\discover-store.log"

if (-not (Test-Path $StoreResult)) {
    throw "Persisted discovery did not write structured result: $StoreResult"
}
$StorePayload = Get-Content $StoreResult -Raw | ConvertFrom-Json
$RunId = [string]$StorePayload.run_id
if (-not $RunId) {
    throw "Persisted discovery result did not contain a run ID."
}
if ($StorePayload.status -ne "completed") {
    throw "Persisted discovery result was not completed: $($StorePayload.status)"
}
if ([int]$StorePayload.clusters -lt 1) {
    throw "Persisted discovery produced no clusters to review."
}

Write-Host "[7/12] Run inspection" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Run list" -Command {
    & $Python -m painfinder runs list --database $Database
} | Tee-Object -FilePath "$EvidenceRoot\runs-list.txt"
Invoke-CheckedNative -Step "Run show" -Command {
    & $Python -m painfinder runs show --run-id $RunId --database $Database
} | Tee-Object -FilePath "$EvidenceRoot\run-show.txt"

Write-Host "[8/12] Export, review and restore" -ForegroundColor Cyan
$InitialPackage = Join-Path $EvidenceRoot "run-before-review.zip"
Invoke-CheckedNative -Step "Initial export" -Command {
    & $Python -m painfinder export-run `
        --run-id $RunId `
        --database $Database `
        --output $InitialPackage
}

$ExpandedPackage = Join-Path $EvidenceRoot "expanded-run"
Expand-Archive -Path $InitialPackage -DestinationPath $ExpandedPackage -Force
$RunPayload = Get-Content "$ExpandedPackage\run.json" -Raw | ConvertFrom-Json
$ClusterKey = $RunPayload.clusters[0].key
if (-not $ClusterKey) {
    throw "Persisted discovery produced no cluster to review."
}

Invoke-CheckedNative -Step "Review status" -Command {
    & $Python -m painfinder review status `
        --run-id $RunId `
        --cluster-key $ClusterKey `
        --status accepted `
        --database $Database
}
Invoke-CheckedNative -Step "Review annotation" -Command {
    & $Python -m painfinder review annotate `
        --run-id $RunId `
        --cluster-key $ClusterKey `
        --field buyer `
        --value "Verification buyer" `
        --database $Database
}
Invoke-CheckedNative -Step "Reviewed report" -Command {
    & $Python -m painfinder review report `
        --run-id $RunId `
        --database $Database `
        --output "$EvidenceRoot\reviewed-opportunities.html"
}

$ReviewedPackage = Join-Path $EvidenceRoot "run-reviewed.zip"
Invoke-CheckedNative -Step "Reviewed export" -Command {
    & $Python -m painfinder export-run `
        --run-id $RunId `
        --database $Database `
        --output $ReviewedPackage
}
Invoke-CheckedNative -Step "Run restore" -Command {
    & $Python -m painfinder restore-run `
        --package $ReviewedPackage `
        --database $RestoredDatabase
} | Tee-Object -FilePath "$EvidenceRoot\restore-run.txt"

Write-Host "[9/12] Benchmark review worksheet and import" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Benchmark review worksheet" -Command {
    & $Python -m painfinder benchmark prepare-review `
        --run-id $RunId `
        --database $Database `
        --output $ReviewWorksheet
}

$ReviewRows = @(Import-Csv $ReviewWorksheet)
if ($ReviewRows.Count -lt 1) {
    throw "Benchmark review worksheet contains no evidence rows."
}
$ReviewedAt = (Get-Date).ToUniversalTime().ToString("o")
for ($Index = 0; $Index -lt $ReviewRows.Count; $Index++) {
    $Row = $ReviewRows[$Index]
    $Row.review_status = "resolved"
    $Row.reviewer = "verification-harness"
    $Row.reviewed_at = $ReviewedAt
    $Row.rationale = "Deterministic verification label for review-import integration."
    if ($Index -eq 0) {
        $Row.expected_pain = "true"
        $Row.expected_categories = "manual_work"
        $Row.expected_cluster = "verification-workflow"
    }
    else {
        $Row.expected_pain = "false"
        $Row.expected_categories = ""
        $Row.expected_cluster = ""
    }
}
$ReviewRows | Export-Csv $ResolvedReviewWorksheet -NoTypeInformation -Encoding UTF8

Invoke-CheckedNative -Step "Benchmark review import" -Command {
    & $Python -m painfinder benchmark import-review `
        --worksheet $ResolvedReviewWorksheet `
        --output $ImportedBenchmarkCorpus
}
Invoke-CheckedNative -Step "Imported benchmark evaluation" -Command {
    & $Python -m painfinder benchmark run `
        --corpus $ImportedBenchmarkCorpus `
        --json-output "$EvidenceRoot\benchmark-review-imported.json" `
        --html-output "$EvidenceRoot\benchmark-review-imported.html"
}

Write-Host "[10/12] Benchmark evaluation" -ForegroundColor Cyan
Invoke-CheckedNative -Step "Benchmark" -Command {
    & $Python -m painfinder benchmark run `
        --corpus $BenchmarkCorpus `
        --json-output "$EvidenceRoot\benchmark.json" `
        --html-output "$EvidenceRoot\benchmark.html"
}

Write-Host "[11/12] Optional official-source smoke" -ForegroundColor Cyan
$HackerNewsStatus = "not_requested"
if ($IncludeHackerNewsSmoke) {
    Invoke-CheckedNative -Step "Hacker News smoke" -Command {
        & $Python -m painfinder hacker-news smoke `
            --feed askstories `
            --max-threads 2 `
            --max-comments 2 `
            --artifacts-dir "$EvidenceRoot\hacker-news"
    }
    $HackerNewsStatus = "completed"
}

Write-Host "[12/12] Verification manifest" -ForegroundColor Cyan
$CommitOutput = Invoke-CheckedNative -Step "Git commit lookup" -Command {
    & git rev-parse HEAD
}
$Commit = ($CommitOutput | Select-Object -First 1).ToString().Trim()
$Manifest = [ordered]@{
    verified_at = (Get-Date).ToString("o")
    commit = $Commit
    run_id = $RunId
    cluster_key = $ClusterKey
    hacker_news_smoke = $HackerNewsStatus
    database = $Database
    restored_database = $RestoredDatabase
    required_files = @(
        "coverage.xml",
        "fixture-report.html",
        "opportunities.html",
        "discover-store.json",
        "stored-opportunities.html",
        "reviewed-opportunities.html",
        "run-reviewed.zip",
        "benchmark-review-worksheet.csv",
        "benchmark-review-resolved.csv",
        "benchmark-review-imported.jsonl",
        "benchmark-review-imported.json",
        "benchmark-review-imported.html",
        "benchmark.json",
        "benchmark.html"
    )
}
$Manifest | ConvertTo-Json -Depth 5 |
    Set-Content -Path "$EvidenceRoot\verification-manifest.json" -Encoding UTF8

foreach ($Relative in $Manifest.required_files) {
    if (-not (Test-Path (Join-Path $EvidenceRoot $Relative))) {
        throw "Verification output missing: $Relative"
    }
}

Write-Host "PASS: complete MVP verification succeeded." -ForegroundColor Green
Write-Host "Evidence: $EvidenceRoot"
