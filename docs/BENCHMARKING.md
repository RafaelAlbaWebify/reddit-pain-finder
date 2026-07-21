# Detector and clustering benchmarking

The benchmark evaluates deterministic pain detection and topic clustering against a manually reviewed JSONL corpus.

## Corpus format

Each line contains:

- `item`: a normal `SourceItem` object;
- `expected_pain`: boolean;
- `expected_categories`: reviewed pain categories;
- `expected_cluster`: reviewed topic identifier or `null`.

Do not include usernames or unnecessary personal information in benchmark fixtures.

Use [`BENCHMARK_REVIEW_PROTOCOL.md`](BENCHMARK_REVIEW_PROTOCOL.md) before expanding the corpus. Complete labels without looking at detector output, and convert only resolved reviewed rows into JSONL.

## Prepare a review worksheet from a stored run

Export persisted evidence into an unlabeled CSV worksheet:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark prepare-review `
  --run-id <RUN_ID> `
  --database data\research.db `
  --output output\benchmark-review-worksheet.csv
```

The command preserves evidence identity, title, body, community and canonical URL. It deliberately leaves pain, category and cluster labels blank and sets `review_status` to `unreviewed`.

The static [`../examples/benchmark-review-worksheet.csv`](../examples/benchmark-review-worksheet.csv) remains a format example.

## Import a resolved worksheet

After independent review and disagreement resolution, convert the completed worksheet into benchmark JSONL:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark import-review `
  --worksheet output\benchmark-review-worksheet.csv `
  --output output\reviewed-benchmark-corpus.jsonl
```

The importer validates the complete worksheet before writing output. Every row must be marked `resolved` and include an explicit pain label, reviewer, timezone-aware review timestamp and rationale. Positive pain cases require at least one valid category and a cluster identifier. Negative cases must not define categories or a cluster. Duplicate evidence IDs, malformed source records and inconsistent labels are rejected.

The importer never creates labels or tunes detector rules.

## Automated calibration controls

The project automates all objective evidence controls around human review:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark audit-corpus `
  --corpus output\reviewed-benchmark-corpus.jsonl `
  --json-output output\benchmark-corpus-audit.json

.\.venv\Scripts\python.exe -m painfinder benchmark compare-reviews `
  --left output\reviewer-a.csv `
  --right output\reviewer-b.csv `
  --disagreements-output output\review-disagreements.csv `
  --json-output output\review-agreement.json

.\.venv\Scripts\python.exe -m painfinder benchmark compare-results `
  --before output\benchmark-before.json `
  --after output\benchmark-after.json `
  --output output\benchmark-comparison.json
```

`audit-corpus` enforces the minimum structural prerequisites for calibration. `compare-reviews` rejects source-evidence changes and produces a disagreement queue without resolving labels. `compare-results` records exact metric and error-count deltas without declaring a winner automatically.

## Safe mechanical repair and verification

For formatter, import-order and other Ruff-safe mechanical problems, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\auto-repair-and-verify.ps1
```

Add `-IncludeHackerNewsSmoke` for the official-source mode.

The repair workflow:

- requires a clean tracked branch;
- refuses detached HEAD, missing remote branches and unpushed commits;
- applies only Ruff formatting and safe fixes;
- rejects any changed non-Python file;
- runs the complete verification before committing repairs;
- commits and pushes only verified mechanical changes;
- synchronizes the pushed branch and verifies it again.

The authoritative verification remains read-only. A locally repaired but uncommitted tree is never accepted as proof of a remote PR head.

## Run the benchmark

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark run `
  --corpus tests\fixtures\benchmark_corpus.jsonl `
  --json-output output\benchmark-results.json `
  --html-output output\benchmark-results.html
```

## Metrics

- pain-detection precision and recall;
- expected-category recall;
- pairwise cluster precision and recall;
- false-positive and false-negative source IDs;
- fragmented expected evidence pairs;
- over-merged evidence pairs.

The included fixture is deliberately small and proves evaluator behavior only. It is not a representative market corpus. Detector or clustering changes must eventually be compared on a larger reviewed corpus with multiple communities and workflows.

Do not choose target thresholds from the included fixture. Establish thresholds only after the reviewed corpus meets the minimum quality conditions in the review protocol and the cost of false positives, false negatives, fragmentation and over-merging has been explicitly considered.

Benchmark metrics do not measure market size, commercial demand, willingness to pay, or implementation feasibility.
