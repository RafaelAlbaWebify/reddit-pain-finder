# Full-stack MVP verification checklist

Run from a clean checkout of the latest stacked branch, currently `feat/release-readiness`.

## Automated local gate

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\install.ps1
.\scripts\verify-mvp.ps1
```

The script must pass all of the following in one invocation:

- Ruff;
- strict mypy;
- full pytest suite;
- coverage at least 85%;
- Reddit fixture report;
- imported discovery report;
- persisted discovery into SQLite;
- stored-run list and detail inspection;
- run export;
- analyst accept and annotation decisions;
- reviewed report;
- reviewed run export and restore;
- benchmark JSON and HTML output;
- timestamped verification manifest.

## Bounded live official-source gate

After the offline gate passes:

```powershell
.\scripts\verify-mvp.ps1 -IncludeHackerNewsSmoke
```

Required live evidence:

- `collection-result.json` records the feed, counts, stop reason and request evidence;
- `source-items.jsonl` contains only normalized source records;
- `opportunities.html` is generated even when zero clusters are detected;
- the run respects story, comment, request and runtime budgets;
- HTTP 403, HTTP 429, network or malformed responses are reported rather than retried without bounds.

## Manual privacy checks

- no `browser-profile` directory appears in any support package;
- no cookies, tokens, passwords or browser preferences appear in committed files;
- local databases remain ignored by Git;
- generated reports, coverage files and verification artifacts remain ignored by Git;
- canonical evidence links remain visible in machine and reviewed reports.

## GitHub Actions gate

Issue #3 remains unresolved until all three triggers execute recorded steps successfully:

- push;
- pull request;
- manual `workflow_dispatch`.

A job with zero steps and no log blob is an infrastructure failure, not an application test result.

## Ordered merge gate

Merge only after the complete local gate is attached to the PR conversation. Current order:

1. PR #2 — privacy-safe evidence and imported discovery;
2. PR #9 — durable SQLite storage;
3. PR #10 — analyst review workflow;
4. PR #11 — benchmark calibration;
5. PR #12 — official Hacker News adapter;
6. release-readiness PR — run inspection, verification harness and static hardening.

After each merge, rebase or retarget the next PR and confirm its diff contains only its intended scope.

## Release gate

Do not tag an MVP release until:

- the final merged `main` commit passes the full local gate;
- one bounded Hacker News smoke run is recorded;
- the benchmark limitations are documented;
- the verified completion percentage is updated from the actual merged commit;
- known infrastructure limitations are included in the release notes.
