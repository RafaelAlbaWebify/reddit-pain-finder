param(
    [Parameter(Mandatory = $true)]
    [string]$Python,
    [Parameter(Mandatory = $true)]
    [string]$EvidenceRoot,
    [Parameter(Mandatory = $true)]
    [string]$ReviewWorksheet,
    [Parameter(Mandatory = $true)]
    [string]$BenchmarkJson,
    [Parameter(Mandatory = $true)]
    [string]$ControlCorpus
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$AuditJson = Join-Path $EvidenceRoot "benchmark-corpus-audit.json"
$ReviewerA = Join-Path $EvidenceRoot "benchmark-reviewer-a.csv"
$ReviewerB = Join-Path $EvidenceRoot "benchmark-reviewer-b.csv"
$Disagreements = Join-Path $EvidenceRoot "benchmark-review-disagreements.csv"
$AgreementJson = Join-Path $EvidenceRoot "benchmark-review-agreement.json"
$ComparisonJson = Join-Path $EvidenceRoot "benchmark-comparison.json"

Invoke-Checked -Step "Corpus audit" -Command {
    & $Python -m painfinder benchmark audit-corpus `
        --corpus $ControlCorpus `
        --json-output $AuditJson
}

Copy-Item $ReviewWorksheet $ReviewerA
Copy-Item $ReviewWorksheet $ReviewerB

$RowsA = @(Import-Csv $ReviewerA)
$RowsB = @(Import-Csv $ReviewerB)
if ($RowsA.Count -lt 1 -or $RowsB.Count -lt 1) {
    throw "Reviewer worksheet fixture contains no rows."
}

$ReviewedAt = (Get-Date).ToUniversalTime().ToString("o")
foreach ($Row in $RowsA) {
    $Row.expected_pain = "false"
    $Row.expected_categories = ""
    $Row.expected_cluster = ""
    $Row.review_status = "resolved"
    $Row.reviewer = "reviewer-a"
    $Row.reviewed_at = $ReviewedAt
    $Row.rationale = "Verification review A"
}
foreach ($Row in $RowsB) {
    $Row.expected_pain = "false"
    $Row.expected_categories = ""
    $Row.expected_cluster = ""
    $Row.review_status = "resolved"
    $Row.reviewer = "reviewer-b"
    $Row.reviewed_at = $ReviewedAt
    $Row.rationale = "Verification review B"
}
$RowsB[0].expected_pain = "true"
$RowsB[0].expected_categories = "manual_work"
$RowsB[0].expected_cluster = "verification-disagreement"

$RowsA | Export-Csv $ReviewerA -NoTypeInformation -Encoding UTF8
$RowsB | Export-Csv $ReviewerB -NoTypeInformation -Encoding UTF8

Invoke-Checked -Step "Reviewer comparison" -Command {
    & $Python -m painfinder benchmark compare-reviews `
        --left $ReviewerA `
        --right $ReviewerB `
        --disagreements-output $Disagreements `
        --json-output $AgreementJson
}

Invoke-Checked -Step "Benchmark comparison" -Command {
    & $Python -m painfinder benchmark compare-results `
        --before $BenchmarkJson `
        --after $BenchmarkJson `
        --output $ComparisonJson
}

$Agreement = Get-Content $AgreementJson -Raw | ConvertFrom-Json
if ([int]$Agreement.disagreement_count -ne 1) {
    throw "Expected exactly one synthetic reviewer disagreement."
}
$Comparison = Get-Content $ComparisonJson -Raw | ConvertFrom-Json
foreach ($Delta in $Comparison.metric_deltas.PSObject.Properties.Value) {
    if ([double]$Delta -ne 0) {
        throw "Expected zero metric deltas when comparing identical results."
    }
}
