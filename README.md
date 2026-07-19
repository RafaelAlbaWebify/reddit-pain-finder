# Reddit Pain Finder

Local-first opportunity-discovery workbench for identifying evidence-backed customer pain hypotheses from bounded Reddit research sessions.

## Current status

This repository contains **Vertical Slice 0**:

- explicit domain models;
- bounded collection policy;
- Reddit-like HTML fixture extraction;
- deterministic pain-candidate detection;
- evidence report generation;
- unit and integration tests;
- GitHub Actions CI;
- a disabled-by-default Playwright live adapter boundary.

It does **not** yet claim to collect live Reddit successfully. Live collection is the next slice and must be proven against the current Reddit UI without bypassing access controls.

## Safety boundaries

- Read-only collection.
- No posting, commenting, voting, messaging, or account changes.
- No CAPTCHA solving, proxy rotation, fingerprint spoofing, or block evasion.
- Single-browser context and bounded collection budgets.
- Live Reddit access disabled unless explicitly enabled.
- Source URLs and extraction failures remain visible in reports.
- Usernames are not required for pain analysis.

## Architecture

```text
research definition
    -> bounded collection policy
    -> Reddit adapter
    -> normalized source items
    -> pain candidate detection
    -> evidence report
```

The collector and analyzer are separate. A UI change should not require rewriting the domain or reporting layers.

## Requirements

- Python 3.12+
- `uv` recommended
- PowerShell 7 recommended on Windows

## Install and verify

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
.\scripts\verify.ps1
```

## Run the fixture demo

```powershell
.\.venv\Scripts\python.exe -m painfinder demo `
  --input tests\fixtures\reddit_thread.html `
  --output output\fixture-report.html
```

## Live mode

Live mode is intentionally unavailable in this slice. `LiveRedditCollector` raises a clear error until the next vertical slice defines and proves:

1. stable page identification;
2. bounded search navigation;
3. thread extraction;
4. block/CAPTCHA stop behavior;
5. trace and screenshot evidence;
6. a successful three-thread smoke run.

## Next vertical slice

**Slice 1 — Bounded live Reddit discovery**

- headed Chromium persistent context;
- one configured seed community;
- new/rising/search sampling;
- maximum three threads and ten comments per thread;
- stop on block, CAPTCHA, login wall, or selector mismatch;
- Playwright trace on failure;
- HTML evidence report;
- no autonomous opportunity scoring yet.
