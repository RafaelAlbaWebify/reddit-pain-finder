# Benchmark corpus review protocol

Use this protocol to expand the benchmark with manually reviewed public-discussion evidence. The objective is to measure detector and clustering behavior, not to manufacture favorable metrics.

## Evidence selection

- Use public, lawfully obtained discussion evidence already collected or imported by the project.
- Sample across multiple communities, workflows and writing styles.
- Include clear pain, ambiguous cases and neutral operational discussion.
- Preserve the canonical source URL and a stable external ID.
- Remove usernames and unnecessary personal information.
- Do not duplicate near-identical excerpts merely to increase case count.

## Independent review

Each item should be reviewed without looking at the detector output.

Record:

- `expected_pain`: whether the text contains an actionable workflow pain;
- `expected_categories`: all supported categories clearly evidenced by the text;
- `expected_cluster`: a concise topic identifier shared only by items describing the same underlying workflow problem;
- `rationale`: a short explanation of the decision;
- `review_status`: `unreviewed` or `resolved`.

Do not label a case as pain solely because the product could theoretically help it. Label only what the source text supports.

## Category guidance

Use only categories supported by `PainCategory`. An expected category should describe evidence present in the text, not a guessed root cause.

When an item is neutral:

- set `expected_pain` to `false`;
- leave `expected_categories` empty;
- leave `expected_cluster` empty.

## Cluster guidance

Cluster IDs are reviewed topic identities, not detector keys.

- Use the same ID for evidence about the same workflow pain across communities.
- Use different IDs for merely related domains with different operational problems.
- Do not include category names solely to force or prevent a match.
- Exclude neutral items from reviewed cluster relationships.

## Automation-assisted review workflow

Human reviewers remain responsible only for semantic labels and dispute resolution. The project automates the surrounding evidence controls.

1. Export the same unlabeled worksheet for two independent reviewers.
2. Reviewers label copies without detector output.
3. Compare the worksheets:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark compare-reviews `
  --left output\reviewer-a.csv `
  --right output\reviewer-b.csv `
  --disagreements-output output\review-disagreements.csv `
  --json-output output\review-agreement.json
```

The command rejects changed source evidence or mismatched evidence IDs, records agreement rate, and produces a dispute queue. It does not resolve labels.

4. Resolve disputes in a separate worksheet and import the resolved corpus.
5. Audit corpus prerequisites before using metrics for calibration:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark audit-corpus `
  --corpus output\reviewed-benchmark-corpus.jsonl `
  --json-output output\benchmark-corpus-audit.json
```

6. Run and preserve the baseline benchmark.
7. After any detector or clustering change, rerun the same corpus and compare results:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark compare-results `
  --before output\benchmark-before.json `
  --after output\benchmark-after.json `
  --output output\benchmark-comparison.json
```

The comparison records exact metric and error-count deltas without declaring a change successful automatically.

## Minimum corpus quality before calibration

Before using metrics to tune rules, the reviewed corpus should contain:

- multiple independent communities;
- multiple workflow categories;
- positive and negative examples;
- more than one reviewed cluster with at least two items;
- examples expected to expose false positives, false negatives, fragmentation and over-merging;
- no unresolved labels.

There is intentionally no target precision or recall threshold yet. Thresholds must be chosen from representative evidence and product risk, not from the small behavior-proving fixture.

## Audit expectations

For each corpus revision, record:

- review date;
- reviewer identity or stable reviewer label;
- evidence source and collection method;
- number of included, excluded and disputed rows;
- benchmark results before and after any rule change;
- explanation for label or cluster changes.
