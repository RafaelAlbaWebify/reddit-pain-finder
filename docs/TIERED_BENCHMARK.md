# Tiered benchmark reporting

The project keeps AI-only review outcomes separate from explicitly human-approved evidence.

Generate the combined report with:

```powershell
.\.venv\Scripts\python.exe -m painfinder.benchmark_tiers `
  --provisional-csv output\provisional-review.csv `
  --gold-corpus output\human-approved-gold-corpus.jsonl `
  --json-output output\tiered-benchmark.json `
  --html-output output\tiered-benchmark.html
```

The report always contains two independently evaluated sections:

- `provisional`: unanimous, high-confidence AI consensus that passed escalation controls but has not been approved by a person;
- `gold`: rows explicitly approved by a person and promoted through the human-approval workflow.

The JSON records an immutable provenance label for each tier:

- `ai_unanimous_not_human_approved`;
- `explicitly_human_approved`.

## Interpretation rules

Provisional metrics are exploratory. They may be used to inspect behavior, discover likely errors and prioritize human review. They must not be described as human-reviewed ground truth.

Gold metrics are the only metrics eligible for evidence-based detector or clustering calibration. Their strength still depends on corpus size, sampling quality, reviewer care and coverage across communities and workflows.

Do not compare the two tiers as though they contain the same population. The provisional file excludes disagreements, low-confidence decisions, audit samples and detector conflicts, so it is intentionally a filtered subset.

The command rejects malformed provisional labels or malformed gold JSONL before writing either output report.
