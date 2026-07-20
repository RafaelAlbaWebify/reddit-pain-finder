# Project status

## Completion estimates

- **95% implemented, merged and verified toward the defined local-first MVP.**
- **95% is now the fully verified-and-merged baseline on `main`.**

These percentages use the same weighted MVP denominator: safely ingest discussion evidence, detect recurring pain, cluster and rank opportunities, preserve traceability, support analyst review, persist runs, and operate repeatably.

The merged `main` commit `39d6400f4e4a6a7cb79e83c70d7de1531055e34a` passed both authoritative Windows verification modes: the complete offline gate and the same gate with the bounded official Hacker News smoke enabled. GitHub Actions remains unavailable before step execution, so local verification was used as explicitly authorized temporary merge authority.

| Workstream | Weight | Merged status | Earned |
|---|---:|---|---:|
| Project foundation, domain model, CLI, tests | 15% | Merged and verified | 15% |
| Lawful bounded source collection and stop controls | 15% | Reddit stop controls and official Hacker News adapter merged and verified | 15% |
| Privacy-safe evidence and run diagnostics | 10% | Merged and verified with browser-state exclusion | 10% |
| JSONL/CSV import and deduplication | 15% | Merged and verified with validation and edge-case tests | 15% |
| Pain detection, topic clustering and scoring | 20% | Evaluator and review workflow merged; representative reviewed corpus still needed | 18% |
| Traceable machine and reviewed HTML reports | 10% | Merged and verified with source links, review state and caveats | 10% |
| Durable storage and analyst decisions | 10% | Merged and verified with tested schema v1 to v2 migration | 10% |
| Repeatable CI and release readiness | 5% | Both complete local `main` gates passed; GitHub Actions runner still blocked | 2% |
| **Total completed** | **100%** |  | **95%** |

## Implemented, merged and verified

- project foundation with strict typing, linting and tests;
- bounded, read-only Playwright Reddit collection with correct HTTP 403 stop evidence;
- official read-only Hacker News API adapter with exact host, request and runtime budgets;
- screenshot, trace and machine-readable collection evidence;
- privacy-safe support bundles excluding browser profiles and cookies;
- JSONL and CSV evidence import, validation, normalization and deduplication;
- deterministic pain-signal detection and topic-first opportunity clustering;
- initial prioritization scoring with explicit limitations;
- canonical source links in machine-generated reports;
- SQLite research runs, evidence, signals, clusters and decision storage;
- stored-run listing and inspection commands;
- portable run export and restore with prevalidation and audit timestamp retention;
- tested transactional schema v1 to v2 migration with run-scoped indexes;
- analyst accept, reject, annotate, merge and split actions;
- strict reviewed-decision replay and stale derived-score warnings;
- benchmark precision, recall, category and pairwise clustering metrics;
- benchmark review protocol, annotation worksheet and stored-run worksheet export;
- one-command MVP verification with timestamped evidence output;
- complete offline Windows verification from merged `main`;
- complete Windows verification from merged `main` with the bounded official Hacker News smoke enabled.

## Remaining MVP and release work

1. Resolve GitHub Actions issue #3 and obtain at least one successful run with recorded steps and logs.
2. Populate and independently review a representative benchmark corpus using `docs/BENCHMARK_REVIEW_PROTOCOL.md`.
3. Record before/after benchmark evidence before any detector or clustering-rule tuning.
4. Publish the prerelease only when the chosen release policy accepts the current local-verification exception or GitHub Actions is restored.

## Interpretation

The product implementation and integration work are complete for the defined 95% MVP baseline. The remaining five percent is evidence and release governance: restore remote CI execution and deepen the reviewed benchmark corpus before treating detector metrics as calibration evidence.
