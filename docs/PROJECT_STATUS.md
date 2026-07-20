# Project status

## Completion estimate

**62% complete toward the defined local-first MVP.**

This is a weighted engineering estimate, not a claim that 62% of all possible product work is finished. The denominator is the current MVP scope: safely ingest discussion evidence, detect recurring pain, cluster and rank opportunities, preserve traceability, support analyst review, and run repeatably.

| Workstream | Weight | Status | Earned |
|---|---:|---|---:|
| Project foundation, domain model, CLI, tests | 15% | Implemented and previously verified locally | 15% |
| Bounded browser collection and stop controls | 15% | Implemented; Reddit transport correctly stops on HTTP 403 | 12% |
| Privacy-safe evidence and run diagnostics | 10% | Implemented; local re-verification pending for latest branch | 8% |
| JSONL/CSV import and deduplication | 15% | Implemented with validation and edge-case tests | 13% |
| Pain detection, topic clustering and scoring | 20% | Deterministic first version implemented; needs real-corpus calibration | 10% |
| Traceable HTML reports | 10% | Implemented with source links and score caveats | 4% |
| Durable storage and analyst decisions | 10% | Not implemented | 0% |
| Repeatable CI and release readiness | 5% | Blocked by pre-step GitHub Actions failure | 0% |
| **Total** | **100%** |  | **62%** |

## What currently works

- verified project foundation with strict typing, linting and tests;
- bounded, read-only Playwright collection policy;
- explicit stop behavior for blocks, CAPTCHA, rate limits, login walls and selector mismatches;
- screenshot, trace and machine-readable run evidence;
- privacy-safe support bundles that exclude browser profiles and cookies;
- JSONL and CSV evidence import;
- validation, normalization and deduplication;
- deterministic pain-signal detection;
- topic-first opportunity clustering;
- prioritization scoring with explicit limitations;
- canonical source links in opportunity reports.

## Remaining MVP work

1. Re-run the latest PR branch locally: Ruff, strict mypy, pytest with at least 85% coverage, fixture demo and imported-discovery demo.
2. Resolve GitHub Actions issue #3 and obtain successful push, pull-request and manual runs.
3. Add durable storage for research runs, imported evidence, clusters and analyst decisions.
4. Add analyst actions: accept, reject, merge, split and annotate clusters.
5. Calibrate clustering and scoring against a larger, manually reviewed corpus.
6. Add a second lawful discussion-source adapter or approved Reddit access path.

## Interpretation

The project is beyond scaffolding and has a usable offline discovery pipeline, but it is not yet a complete autonomous research product. The largest remaining gaps are durable analyst workflow, real-corpus calibration, repeatable CI, and reliable lawful source acquisition.
