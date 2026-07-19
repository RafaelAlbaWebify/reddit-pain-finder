# Reddit Pain Finder

Local-first opportunity-discovery workbench for identifying evidence-backed customer pain hypotheses from bounded discussion research.

## Current capabilities

- bounded, read-only Playwright Reddit smoke collection;
- explicit stop handling for blocks, CAPTCHA, rate limits, login walls and selector mismatches;
- screenshots and Playwright traces for browser evidence;
- privacy-safe support bundles that exclude browser profiles and cookies;
- JSONL and CSV evidence import;
- deduplication by external ID and normalized content hash;
- deterministic pain-signal detection;
- deterministic candidate clustering and opportunity scoring;
- standalone HTML evidence and opportunity reports;
- strict type checking, linting and automated tests.

## Current Reddit status

A local smoke run against `old.reddit.com` received a genuine HTTP 403 network-security block from Reddit infrastructure. The collector classified the page correctly and stopped without trying to bypass the restriction.

Development therefore continues through transport-independent evidence import while approved Reddit access is investigated.

## Safety boundaries

- Read-only collection.
- No posting, commenting, voting, messaging, or account changes.
- No CAPTCHA solving, proxy rotation, fingerprint spoofing, or block evasion.
- Single browser context and bounded collection budgets.
- Browser profiles and cookies are excluded from evidence packages.
- Source URLs and extraction failures remain visible.
- Scores prioritize analyst review and do not prove market demand.

## Requirements

- Python 3.12+
- PowerShell 7 recommended on Windows

## Install and verify

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
.\scripts\verify.ps1
```

## Imported discovery

Create a JSONL or CSV file using the templates under `examples/`, then run:

```powershell
.\.venv\Scripts\python.exe -m painfinder discover `
  --input examples\evidence-template.csv `
  --output output\opportunities.html
```

The generated report ranks candidate pain clusters by evidence count, community independence, and detector confidence.

## Fixture demo

```powershell
.\.venv\Scripts\python.exe -m painfinder demo `
  --input tests\fixtures\reddit_thread.html `
  --output output\fixture-report.html
```

## Bounded live smoke test

```powershell
.\scripts\install-browser.ps1
.\scripts\live-smoke.ps1 `
  -Subreddits smallbusiness `
  -Sort new `
  -MaxThreads 3 `
  -MaxComments 10
```

This opens a visible Chromium window and stops immediately when Reddit presents a block or access-control page.

## Architecture

```text
bounded browser or imported evidence
    -> validated source items
    -> deduplication
    -> pain-signal detection
    -> candidate clustering
    -> opportunity scoring
    -> evidence-backed HTML report
```

The browser transport, imported evidence, analysis, clustering, and reporting layers remain separate so access failures do not halt product development.
