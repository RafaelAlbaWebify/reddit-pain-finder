# Analyst review workflow

Machine-generated opportunity clusters remain immutable. Analyst actions are stored as append-only decisions and replayed to create a reviewed view.

## Supported actions

- accept or reject a cluster;
- annotate buyer, workflow, consequence, workaround, solution hypothesis, confidence, uncertainty, or another named field;
- merge one reviewed cluster into another;
- split selected source evidence into a new reviewed cluster;
- regenerate a reviewed HTML report.

## Status decision

```powershell
.\.venv\Scripts\python.exe -m painfinder review status `
  --run-id <RUN_ID> `
  --cluster-key <CLUSTER_KEY> `
  --status accepted `
  --database data\research.db
```

## Annotation

```powershell
.\.venv\Scripts\python.exe -m painfinder review annotate `
  --run-id <RUN_ID> `
  --cluster-key <CLUSTER_KEY> `
  --field buyer `
  --value "Bookkeeping agency" `
  --database data\research.db
```

## Merge

```powershell
.\.venv\Scripts\python.exe -m painfinder review merge `
  --run-id <RUN_ID> `
  --target-key <TARGET_CLUSTER> `
  --source-key <SOURCE_CLUSTER> `
  --database data\research.db
```

## Split

```powershell
.\.venv\Scripts\python.exe -m painfinder review split `
  --run-id <RUN_ID> `
  --cluster-key <ORIGINAL_CLUSTER> `
  --new-key invoice-onboarding `
  --source-ids post-1,comment-7 `
  --label "Invoice onboarding" `
  --database data\research.db
```

A split must leave at least one evidence item in the original cluster.

## Reviewed report

```powershell
.\.venv\Scripts\python.exe -m painfinder review report `
  --run-id <RUN_ID> `
  --database data\research.db `
  --output output\reviewed-opportunities.html
```

The report distinguishes machine-generated evidence from analyst status and annotations. Accepting a cluster does not prove market demand or willingness to pay.
