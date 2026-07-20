# Project status

## Completion estimates

- **95% implemented and locally verified toward the defined local-first MVP on the open PR stack.**
- **62% remains the last fully verified-and-merged baseline.**

These percentages use the same weighted MVP denominator: safely ingest discussion evidence, detect recurring pain, cluster and rank opportunities, preserve traceability, support analyst review, persist runs, and operate repeatably.

Implementation credit means code, tests and documentation exist in an open branch. Local verification means the complete Windows release-readiness harness passed, including the bounded official Hacker News smoke. It does not mean the work has been merged or that GitHub Actions is healthy.

| Workstream | Weight | Open-stack status | Earned |
|---|---:|---|---:|
| Project foundation, domain model, CLI, tests | 15% | Implemented and locally verified | 15% |
| Lawful bounded source collection and stop controls | 15% | Reddit stop controls and official Hacker News adapter locally verified | 15% |
| Privacy-safe evidence and run diagnostics | 10% | Implemented and locally verified with browser-state exclusion | 10% |
| JSONL/CSV import and deduplication | 15% | Implemented and locally verified with validation and edge-case tests | 15% |
| Pain detection, topic clustering and scoring | 20% | Implemented with verified evaluator and review protocol; larger reviewed corpus still needed | 18% |
| Traceable machine and reviewed HTML reports | 10% | Implemented and locally verified with source links, review state and caveats | 10% |
| Durable storage and analyst decisions | 10% | Implemented and locally verified with tested schema v1 to v2 migration | 10% |
| Repeatable CI and release readiness | 5% | Complete local gates passed; GitHub Actions runner still blocked | 2% |
| **Total implemented** | **100%** |  | **95%** |

## Implemented and locally verified on the open stack

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
- benchmark review protocol and annotation worksheet for representative corpus expansion;
- one-command MVP verification with timestamped evidence output;
- complete offline Windows verification;
- complete Windows verification with the bounded official Hacker News smoke enabled.

## Remaining MVP and release work

1. Resolve GitHub Actions issue #3 and obtain successful push, pull-request and manual runs.
2. Merge the stacked PRs in order using `docs/MERGE_RUNBOOK.md`.
3. Rerun both complete verification modes from merged `main` and retain the evidence.
4. Populate and independently review a representative benchmark corpus using `docs/BENCHMARK_REVIEW_PROTOCOL.md`.
5. Record before/after benchmark evidence before any detector or clustering-rule tuning.
6. Update the verified-and-merged baseline and publish the prerelease only after the final `main` gate passes.

## Interpretation

The defined MVP implementation is locally verified. The remaining five percent is release-critical rather than feature breadth: GitHub Actions recovery, ordered integration into `main`, final merged-commit evidence and representative benchmark depth.
