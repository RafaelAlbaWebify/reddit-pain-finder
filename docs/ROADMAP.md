# MVP roadmap

Status legend: implemented means code, tests and documentation exist on the open stack; verified means the complete gate has passed on the referenced commit.

## Milestone A — Privacy-safe imported discovery

**Implemented; full-stack re-verification pending.**

- privacy-safe evidence packaging;
- JSONL and CSV import;
- normalization and deduplication;
- pain detection, topic clustering and traceable reports;
- canonical evidence links and concise malformed-input errors.

Primary PR: #2.

## Milestone B — Durable research state

**Implemented; verification and migration expansion pending.**

- SQLite runs, evidence items, signals, clusters and decisions;
- schema version enforcement;
- idempotent evidence import;
- portable export and restore;
- package prevalidation and audit timestamp retention;
- stored-run listing and inspection.

Primary PR: #9, with restore hardening in the release-readiness stack.

Remaining: prove the complete gate and add a real schema migration when version 2 is introduced.

## Milestone C — Analyst review workflow

**Implemented; verification pending.**

- accept and reject;
- merge and split;
- named annotations;
- append-only audit trail;
- deterministic replay;
- reviewed reports with evidence links;
- explicit stale-score warnings for derived clusters;
- strict failure on corrupt or unsupported decisions.

Primary PR: #10, with replay hardening in the release-readiness stack.

## Milestone D — Calibration

**Initial evaluator implemented; corpus depth incomplete.**

- reviewed JSONL benchmark format;
- detector confusion matrix, precision and recall;
- expected-category measurement;
- pairwise cluster precision and recall;
- false-positive, false-negative, fragmentation and over-merge evidence;
- JSON and HTML benchmark output.

Primary PR: #11.

Remaining: expand the corpus across multiple communities and workflows before tuning rules or treating metrics as stable.

## Milestone E — Source acquisition

**Second source implemented; live evidence pending.**

- Reddit remains correctly classified as blocked on the tested network;
- official read-only Hacker News API adapter;
- exact HTTPS host/path allowlist;
- story, comment, request and runtime budgets;
- normalized `SourceItem` output;
- standard downstream analysis and reports;
- transport and CLI tests.

Primary PR: #12.

Remaining: record one bounded Hacker News smoke run and retain its machine-readable evidence.

## Milestone F — Release readiness

**Partially implemented; infrastructure blocked.**

- one-command full MVP verification harness;
- timestamped evidence manifest;
- run inspection commands;
- local database and generated-artifact ignore rules;
- full-stack verification and merge checklist;
- public status synchronized with implemented and verified percentages.

Remaining:

- run the complete harness on Windows and fix all findings;
- restore GitHub Actions execution under issue #3;
- merge the stacked PRs in order;
- update the verified completion baseline;
- produce versioned release notes and tag the MVP release.
