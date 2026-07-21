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

After independent review and disagreement resolution, validate the entire worksheet and convert it to benchmark JSONL:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark import-review `
  --worksheet output\benchmark-review-resolved.csv `
  --output output\reviewed-benchmark-corpus.jsonl
```

The importer requires every row to be resolved and audit-complete. Positive cases require categories and a cluster; negative cases must not define either. It never creates labels or tunes detector rules.

## Audit corpus prerequisites

Check whether a reviewed corpus meets the protocol's minimum objective conditions before using it for calibration:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark audit-corpus `
  --corpus output\reviewed-benchmark-corpus.jsonl `
  --json-output output\benchmark-corpus-audit.json
```

The command fails when IDs are duplicated or the corpus lacks multiple communities, categories, positive and negative examples, or at least two multi-item reviewed clusters. Passing this gate proves only the documented structural prerequisites; it does not by itself establish representativeness.

## Compare independent reviews

Compare two reviewers' worksheets without resolving their labels automatically:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark compare-reviews `
  --left output\reviewer-a.csv `
  --right output\reviewer-b.csv `
  --disagreements-output output\review-disagreements.csv `
  --json-output output\review-agreement.json
```

The comparison rejects changed source evidence or different evidence IDs, records agreement rate, and emits only disputed labels for human adjudication.

## Run the benchmark

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark run `
  --corpus tests\fixtures\benchmark_corpus.jsonl `
  --json-output output\benchmark-results.json `
  --html-output output\benchmark-results.html
```

## Compare before and after results

Record exact metric and error-count deltas for a detector or clustering change:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark compare-results `
  --before output\benchmark-before.json `
  --after output\benchmark-after.json `
  --output output\benchmark-comparison.json
```

The command does not declare a winner. Review the deltas together with false positives, false negatives, fragmentation and over-merging.

## Complete verification wrapper

`update-and-verify.ps1` verifies the branch that is currently selected. It fetches `origin`, refuses detached HEAD, refuses a missing remote branch, and refuses to reset a branch containing unpushed commits. It synchronizes that same branch and runs the complete MVP gate plus the calibration-control integration verifier.

The wrapper does not switch to a hard-coded release branch.

## Metrics

- pain-detection precision and recall;
- expected-category recall;
- pairwise cluster precision and recall;
- false-positive and false-negative source IDs;
- fragmented expected evidence pairs;
- over-merged evidence pairs.

The included fixtures are deliberately small and prove evaluator and control behavior only. They are not representative market corpora. Detector or clustering changes must eventually be compared on a larger reviewed corpus with multiple communities and workflows.

Do not choose target thresholds from the included fixtures. Establish thresholds only after the reviewed corpus meets the minimum quality conditions in the review protocol and the cost of false positives, false negatives, fragmentation and over-merging has been explicitly considered.

Benchmark metrics do not measure market size, commercial demand, willingness to pay, or implementation feasibility.
