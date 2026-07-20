# Draft MVP release notes

These notes describe the complete open implementation stack. They must not be published as a final release until the verification checklist passes on the merged `main` commit.

## Product

Reddit Pain Finder is a local-first opportunity-discovery workbench. It ingests bounded public-discussion evidence or user-supplied JSONL/CSV, detects pain language, groups recurring topics, prioritizes candidates for analyst review, and preserves links back to source evidence.

## Included capabilities

### Evidence acquisition

- bounded, headed, read-only Reddit collector;
- explicit stop behavior for network blocks, CAPTCHA, login walls, rate limits, selector mismatch and runtime exhaustion;
- official read-only Hacker News Firebase API adapter;
- exact host/path restrictions and request, story, comment and runtime budgets;
- JSONL and CSV evidence import.

### Analysis

- normalized `SourceItem` contract;
- external-ID and content-hash deduplication;
- deterministic pain-signal rules;
- topic-first candidate clustering;
- review-priority scoring with explicit non-market caveats;
- reviewed-corpus precision, recall and pairwise cluster evaluation.

### Persistence and review

- local SQLite research runs;
- persisted source items, pain signals, clusters and decisions;
- idempotent evidence storage;
- run listing and detail inspection;
- portable run export and restore;
- audit timestamp retention during restore;
- accept, reject, annotate, merge and split decisions;
- strict append-only decision replay;
- stale-score warnings after analyst merge or split.

### Reporting and diagnostics

- source-linked opportunity reports;
- reviewed opportunity reports;
- machine-readable collection summaries;
- privacy-safe Reddit support packages excluding browser profiles and cookies;
- one-command MVP verification with timestamped evidence manifest.

## Safety and privacy

- no posting, voting, messaging or account changes;
- no CAPTCHA solving, proxy rotation, fingerprint spoofing or block evasion;
- concurrency one for live source adapters;
- browser profiles and cookies excluded from support packages;
- local databases and generated evidence ignored by Git;
- scores do not claim market size, willingness to pay or commercial viability.

## Known limitations

- Reddit returned a genuine HTTP 403 network-security block on the tested connection;
- the benchmark corpus is intentionally small and proves evaluator behavior, not production accuracy;
- merge/split operations retain pre-review machine scores and flag them for recalculation;
- GitHub Actions currently fails before recording any workflow step or log blob under issue #3;
- the complete stacked implementation still requires one successful local verification run;
- one bounded Hacker News smoke run must be retained before release;
- SQLite schema version 1 is enforced, but a real migration path will only be proven when schema version 2 exists.

## Required release evidence

- `scripts/verify-mvp.ps1` passes on the final merged commit;
- coverage is at least 85%;
- a second run with `-IncludeHackerNewsSmoke` passes or records a correctly classified transport stop;
- the timestamped verification manifest is attached to the release record;
- the final merged commit and exact tool versions are recorded;
- implemented and verified completion percentages are synchronized.
