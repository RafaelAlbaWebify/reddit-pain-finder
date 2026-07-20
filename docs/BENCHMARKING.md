# Detector and clustering benchmarking

The benchmark evaluates deterministic pain detection and topic clustering against a manually reviewed JSONL corpus.

## Corpus format

Each line contains:

- `item`: a normal `SourceItem` object;
- `expected_pain`: boolean;
- `expected_categories`: reviewed pain categories;
- `expected_cluster`: reviewed topic identifier or `null`.

Do not include usernames or unnecessary personal information in benchmark fixtures.

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

Benchmark metrics do not measure market size, commercial demand, willingness to pay, or implementation feasibility.
