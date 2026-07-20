# Project status

## Completion estimates

- **93% implemented toward the defined local-first MVP on the open PR stack.**
- **62% remains the last verified-and-merged baseline.**

These percentages use the same weighted MVP denominator: safely ingest discussion evidence, detect recurring pain, cluster and rank opportunities, preserve traceability, support analyst review, persist runs, and operate repeatably.

Implementation credit means code, tests and documentation exist in an open branch. It does not mean the work has passed the complete verification gate or been merged.

| Workstream | Weight | Open-stack status | Earned |
|---|---:|---|---:|
| Project foundation, domain model, CLI, tests | 15% | Implemented and previously verified locally | 15% |
| Lawful bounded source collection and stop controls | 15% | Reddit stop controls plus official Hacker News API adapter implemented | 15% |
| Privacy-safe evidence and run diagnostics | 10% | Implemented with browser-state exclusion | 10% |
| JSONL/CSV import and deduplication | 15% | Implemented with validation and edge-case tests | 15% |
| Pain detection, topic clustering and scoring | 20% | Implemented with initial benchmark evaluator; larger corpus still needed | 18% |
| Traceable machine and reviewed HTML reports | 10% | Implemented with source links, review state and caveats | 10% |
| Durable storage and analyst decisions | 10% | SQLite runs, export/restore and append-only review overlay implemented | 10% |
| Repeatable CI and release readiness | 5% | Blocked by pre-step GitHub Actions failure | 0% |
| **Total implemented** | **100%** |  | **93%** |

## Implemented on the open stack

- verified project foundation with strict typing, linting and tests from the earlier baseline;
- bounded, read-only Playwright Reddit collection with correct HTTP 403 stop evidence;
- official read-only Hacker News API adapter with exact host and request budgets;
- screenshot, trace and machine-readable collection evidence;
- privacy-safe support bundles excluding browser profiles and cookies;
- JSONL and CSV evidence import, validation, normalization and deduplication;
- deterministic pain-signal detection and topic-first opportunity clustering;
- initial prioritization scoring with explicit limitations;
- canonical source links in machine-generated reports;
- SQLite research runs, evidence, signals, clusters and decision storage;
- portable run export and restore;
- analyst accept, reject, annotate, merge and split actions;
- reviewed reports with append-only audit replay;
- benchmark precision, recall, category and pairwise clustering metrics.

## Remaining MVP work

1. Run the complete stacked branch locally: Ruff, strict mypy, full pytest with at least 85% coverage, fixture demo, imported discovery, persistent discovery, review report and benchmark demo.
2. Resolve GitHub Actions issue #3 and obtain successful push, pull-request and manual runs.
3. Correct any failures discovered by the complete verification pass.
4. Expand the benchmark beyond its small behavior-proving fixture before using metrics to tune rules.
5. Merge the stacked PRs in order and update the verified completion baseline.

## Interpretation

The product implementation is close to the defined MVP, but release readiness is not. The remaining seven percent is disproportionately important because it contains complete integration proof, CI recovery, benchmark expansion and ordered merge/release work.
