# PR #2 verification checklist

Run from a clean checkout of `fix/live-evidence-privacy`.

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\install.ps1
.\scripts\verify.ps1

.\.venv\Scripts\python.exe -m painfinder demo `
  --input tests\fixtures\reddit_thread.html `
  --output output\fixture-report.html

.\.venv\Scripts\python.exe -m painfinder discover `
  --input tests\fixtures\imported_evidence.jsonl `
  --output output\opportunities.html
```

## Required evidence

- Ruff passes.
- Strict mypy passes.
- Full pytest suite passes.
- Coverage is at least 85%.
- Fixture report is generated and labeled as fixture evidence.
- Opportunity report is generated.
- Opportunity report contains canonical source links.
- Malformed import exits non-zero with a concise message and no traceback.
- Privacy-safe artifact packaging excludes `browser-profile`.

## Merge gate

Do not mark PR #2 ready or merge it until the required evidence is recorded in the PR conversation. GitHub Actions issue #3 may remain open only if the complete local gate passes and the infrastructure limitation is explicitly documented.
