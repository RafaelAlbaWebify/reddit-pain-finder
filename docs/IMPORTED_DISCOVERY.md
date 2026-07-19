# Imported evidence discovery

The discovery pipeline can operate without live Reddit access.

## Supported input formats

- JSON Lines (`.jsonl`)
- CSV (`.csv`)

Required fields:

- `external_id`
- `body`
- `canonical_url`

Optional fields:

- `source_type` (`post` or `comment`, default `post`)
- `title`
- `subreddit`

## Command

```powershell
.\.venv\Scripts\python.exe -m painfinder discover `
  --input tests\fixtures\imported_evidence.jsonl `
  --output output\opportunities.html
```

## Processing stages

1. validate imported records;
2. deduplicate by external ID and normalized content hash;
3. detect deterministic pain signals;
4. group candidates using pain category and recurring topic terms;
5. rank clusters by evidence count, community independence and confidence;
6. generate a standalone HTML report.

The score is a prioritization aid. It is not evidence of market size or willingness to pay.
