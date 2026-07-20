# Reddit Pain Finder

Local-first opportunity-discovery workbench for identifying evidence-backed customer pain hypotheses from bounded public-discussion research.

## Project status

- **95% implemented toward the defined MVP on the open PR stack.**
- **62% remains the last fully verified-and-merged baseline.**

The distinction is deliberate: implementation exists in review branches, while release readiness still requires the complete verification harness, one bounded official-source smoke run, working GitHub Actions, and ordered merges.

See:

- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for the weighted completion model;
- [`docs/ROADMAP.md`](docs/ROADMAP.md) for remaining milestones;
- [`docs/VERIFICATION_CHECKLIST.md`](docs/VERIFICATION_CHECKLIST.md) for the quality gate;
- [`docs/STORAGE.md`](docs/STORAGE.md) for persistent runs and packages;
- [`docs/ANALYST_REVIEW.md`](docs/ANALYST_REVIEW.md) for review decisions;
- [`docs/BENCHMARKING.md`](docs/BENCHMARKING.md) for evaluator limits;
- [`docs/HACKER_NEWS_ADAPTER.md`](docs/HACKER_NEWS_ADAPTER.md) for the official second source.

## Current capabilities

- bounded, read-only Playwright Reddit smoke collection;
- explicit stop handling for blocks, CAPTCHA, rate limits, login walls, runtime limits and selector mismatches;
- official read-only Hacker News API collection with exact host and request budgets;
- screenshots, traces and machine-readable collection evidence;
- privacy-safe support packages excluding browser profiles and cookies;
- JSONL and CSV evidence import with validation, normalization and deduplication;
- deterministic pain-signal detection;
- topic-first opportunity clustering and prioritization scoring;
- canonical source links in machine-generated reports;
- SQLite-backed research runs, signals, clusters and analyst decisions;
- portable run export and restore;
- stored-run listing and inspection commands;
- analyst accept, reject, annotate, merge and split actions;
- reviewed reports with append-only audit replay and stale-score warnings;
- reviewed-corpus detector and clustering benchmarks;
- one-command local MVP verification with timestamped evidence.

## Current Reddit status

A local smoke run against `old.reddit.com` received a genuine HTTP 403 network-security block from Reddit infrastructure. The collector classified the page correctly and stopped without attempting to bypass the restriction.

Development therefore proceeds through transport-independent imports and the official Hacker News API while approved Reddit access is investigated.

## Safety boundaries

- Read-only collection.
- No posting, commenting, voting, messaging or account changes.
- No CAPTCHA solving, proxy rotation, fingerprint spoofing or block evasion.
- Concurrency one and explicit request, thread, comment and runtime budgets.
- Browser profiles and cookies are excluded from support packages.
- Source URLs and transport failures remain visible.
- Scores prioritize analyst review and do not prove market demand.

## Requirements

- Python 3.12+
- PowerShell 7 recommended on Windows

## Install

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
```

## Complete verification

From an existing clean checkout, synchronize the exact release-readiness branch and run every offline gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update-and-verify.ps1
```

The synchronization wrapper refuses to continue when local changes are present, fetches `origin`, resets the local `feat/release-readiness` branch to the exact remote commit, and then runs `verify-mvp.ps1`.

Include one bounded call to the official Hacker News API:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update-and-verify.ps1 `
  -IncludeHackerNewsSmoke
```

To run the quality and integration gate without changing branches:

```powershell
.\scripts\verify-mvp.ps1
```

The verification script writes a timestamped evidence package under `artifacts\verification\` and stops at the first failed gate.

## Imported discovery

```powershell
.\.venv\Scripts\python.exe -m painfinder discover `
  --input examples\evidence-template.csv `
  --output output\opportunities.html
```

## Persistent discovery

```powershell
.\.venv\Scripts\python.exe -m painfinder discover-store `
  --input examples\evidence-template.csv `
  --name "Invoice research" `
  --database data\research.db `
  --output output\opportunities.html
```

Inspect stored runs:

```powershell
.\.venv\Scripts\python.exe -m painfinder runs list `
  --database data\research.db

.\.venv\Scripts\python.exe -m painfinder runs show `
  --run-id <RUN_ID> `
  --database data\research.db
```

## Analyst review

```powershell
.\.venv\Scripts\python.exe -m painfinder review status `
  --run-id <RUN_ID> `
  --cluster-key <CLUSTER_KEY> `
  --status accepted `
  --database data\research.db

.\.venv\Scripts\python.exe -m painfinder review report `
  --run-id <RUN_ID> `
  --database data\research.db `
  --output output\reviewed-opportunities.html
```

## Benchmark evaluation

```powershell
.\.venv\Scripts\python.exe -m painfinder benchmark run `
  --corpus tests\fixtures\benchmark_corpus.jsonl `
  --json-output output\benchmark.json `
  --html-output output\benchmark.html
```

## Official Hacker News smoke test

```powershell
.\.venv\Scripts\python.exe -m painfinder hacker-news smoke `
  --feed askstories `
  --max-threads 3 `
  --max-comments 5 `
  --artifacts-dir artifacts\hacker-news
```

## Reddit fixture and bounded smoke

```powershell
.\.venv\Scripts\python.exe -m painfinder demo `
  --input tests\fixtures\reddit_thread.html `
  --output output\fixture-report.html

.\scripts\install-browser.ps1
.\scripts\live-smoke.ps1 `
  -Subreddits smallbusiness `
  -Sort new `
  -MaxThreads 3 `
  -MaxComments 10
```

## Architecture

```text
bounded source adapter or imported evidence
    -> validated SourceItem records
    -> deduplication
    -> pain-signal detection
    -> topic-first clustering
    -> prioritization scoring
    -> persistent run state
    -> analyst review overlay
    -> traceable machine and reviewed reports
    -> benchmark and verification evidence
```

Transport, normalization, analysis, persistence, review and reporting remain separate so one source failure does not halt the rest of the product.
