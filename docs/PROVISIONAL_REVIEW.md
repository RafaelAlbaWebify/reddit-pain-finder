# Provisional AI review and human approval

This workflow reduces manual review while preserving a strict boundary between AI-generated labels and human-approved benchmark evidence.

## Reviewer input

Run three isolated reviewer passes over the same blind packet. Each reviewer must receive only the evidence packet and the review protocol. Do not show detector output or another reviewer's decisions.

Each reviewer writes JSONL with one object per evidence item:

```json
{"external_id":"sample-id","expected_pain":true,"expected_categories":["manual_work"],"expected_cluster":"invoice-entry","confidence":0.93,"rationale":"The source describes repeated manual invoice entry."}
```

Required fields:

- `external_id`
- `expected_pain`
- `expected_categories`
- `expected_cluster`
- `confidence`
- `rationale`

The command requires exactly three reviewer files and rejects missing, extra or duplicate evidence IDs.

## Build provisional results

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark build-provisional-review `
  --blind-packet output\reviewer-a.csv `
  --reviewer-output output\ai-review-1.jsonl `
  --reviewer-output output\ai-review-2.jsonl `
  --reviewer-output output\ai-review-3.jsonl `
  --provisional-output output\provisional-review.csv `
  --approval-queue-output output\human-approval-queue.csv `
  --summary-output output\provisional-review-summary.json `
  --minimum-confidence 0.8 `
  --audit-percent 10
```

Only unanimous, sufficiently confident rows outside the deterministic audit sample remain in the provisional file. The approval queue receives:

- every 2-1 majority;
- every three-way dispute;
- low-confidence consensus;
- the deterministic audit sample.

AI consensus remains provisional and must not be described as human-reviewed ground truth.

## Human approval

A person reviews the approval queue and completes these columns for every row:

- `human_decision`: `approve` or `exclude`;
- `human_reviewer`: a stable person identifier;
- `human_reviewed_at`: an ISO 8601 timestamp with timezone;
- `human_rationale`: the person's reason for approving or excluding the row.

The person may correct the proposed pain label, categories or cluster before approval.

Promote approved rows with:

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark promote-human-approvals `
  --approval-queue output\human-approval-queue.csv `
  --resolved-worksheet-output output\human-approved-review.csv `
  --gold-corpus-output output\human-approved-gold-corpus.jsonl
```

The promotion command rejects AI-only rows, missing human metadata, invalid timestamps, invalid semantic labels and queues with no approved rows. It writes through temporary files and replaces final outputs only after complete validation.

## Metric separation

Run provisional and gold benchmarks separately. Never combine or present provisional AI labels as equivalent to human-approved labels.
