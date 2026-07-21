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
- `rationale`: a short explanation kept in the worksheet, not in benchmark JSONL;
- `review_status`: `unreviewed` while incomplete and `resolved` only after the reviewer has finished the row.

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

1. Use `benchmark prepare-review` to export a blind worksheet from a stored run.
2. Make two independent copies and assign stable reviewer labels.
3. Complete labels without running or inspecting detector output.
4. Use `benchmark compare-reviews` to verify that source evidence stayed unchanged and produce the disagreement queue.
5. Human reviewers adjudicate only disputed rows and create one resolved worksheet.
6. Use `benchmark import-review` to validate the resolved worksheet and create JSONL.
7. Use `benchmark audit-corpus` to enforce the minimum structural prerequisites.
8. Run the benchmark and preserve JSON and HTML outputs.
9. For every detector or clustering change, run the same corpus before and after and use `benchmark compare-results` to preserve neutral deltas.

The tools automate validation, comparison and evidence production. They do not create labels, resolve disagreements or choose detector changes.

## Minimum corpus quality before calibration

Before using metrics to tune rules, the reviewed corpus should contain:

- multiple independent communities;
- multiple workflow categories;
- positive and negative examples;
- more than one reviewed cluster with at least two items;
- examples expected to expose false positives, false negatives, fragmentation and over-merging;
- no unresolved labels;
- unique external IDs and unchanged source evidence across reviewers.

`benchmark audit-corpus` enforces the objective structural subset of these requirements. Human reviewers must still judge whether the evidence is genuinely diverse and representative enough for the intended product decisions.

There is intentionally no target precision or recall threshold yet. Thresholds must be chosen from representative evidence and product risk, not from the small behavior-proving fixtures.

## Audit expectations

For each corpus revision, record:

- review date;
- reviewer identity or stable reviewer label;
- evidence source and collection method;
- number of included, excluded and disputed rows;
- agreement summary and disagreement IDs;
- corpus audit JSON;
- benchmark results before and after any rule change;
- machine-readable result comparison;
- explanation for label, cluster or detector-rule changes.
