# Durable local storage

The storage layer uses Python's standard `sqlite3` module and keeps browser state out of the database.

## Database contents

- research runs;
- normalized source items;
- deterministic pain signals;
- opportunity clusters;
- append-only analyst decisions.

Source items are unique within a run by both external ID and normalized content hash.

## Persistent discovery

```powershell
.\.venv\Scripts\python.exe -m painfinder discover-store `
  --input examples\evidence-template.csv `
  --name "Initial SMB research" `
  --database data\research.db `
  --output output\opportunities.html
```

The command prints the generated run ID.

## Export one run

```powershell
.\.venv\Scripts\python.exe -m painfinder export-run `
  --run-id <RUN_ID> `
  --database data\research.db `
  --output output\research-run.zip
```

The ZIP contains a versioned `run.json` file with normalized evidence, signals, clusters and analyst decisions. It never contains cookies or browser profiles.

## Restore a package

```powershell
.\.venv\Scripts\python.exe -m painfinder restore-run `
  --package output\research-run.zip `
  --database data\restored-research.db
```

Restoration creates a new local run ID while preserving the run name, final status, evidence, derived findings and decision values.

## Schema policy

The database stores an explicit schema version. Unsupported versions fail closed instead of being opened with an incompatible model. The initial schema is version 1; future schema changes must add an explicit migration before increasing the supported version.
