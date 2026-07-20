# Hacker News read-only adapter

This adapter uses the official Hacker News Firebase API documented by the Hacker News team at `github.com/HackerNews/API`.

## Safety boundary

- read-only GET requests;
- exact HTTPS host and `/v0/*.json` path allowlist;
- query strings and fragments rejected;
- one request at a time;
- explicit story, comment, total-request and runtime budgets;
- fixed delay between collected items;
- stop classification for budget exhaustion, runtime exhaustion, HTTP 403, HTTP 429, network errors and malformed responses;
- no login, posting, messaging, browser profile, proxy rotation or anti-bot evasion.

## Supported feeds

- `askstories`;
- `newstories`;
- `topstories`;
- `beststories`.

## Bounded smoke command

```powershell
.\.venv\Scripts\python.exe -m painfinder hacker-news smoke `
  --feed askstories `
  --max-threads 3 `
  --max-comments 5 `
  --artifacts-dir artifacts\hacker-news
```

The command writes:

- `collection-result.json` with transport evidence and stop reason;
- `source-items.jsonl` with normalized `SourceItem` records;
- `opportunities.html` using the same downstream analysis and reporting pipeline as imported or Reddit evidence.

The collector and CLI are covered separately: fake transports prove parser, budget and stop behavior without network access, while the bounded smoke command is reserved for an explicit live verification run.

The official API returning data proves transport access only. It does not prove that Hacker News is representative of a target customer market.
