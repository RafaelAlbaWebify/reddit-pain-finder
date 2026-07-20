# Stacked MVP merge runbook

This runbook governs the verified MVP stack. It exists to prevent accidental out-of-order merges or oversized diffs while GitHub Actions issue #3 remains unresolved.

## Verified evidence

Two complete Windows verification runs passed on `feat/release-readiness`:

1. the full offline MVP gate;
2. the same gate with the bounded official Hacker News smoke enabled.

Both ended with:

```text
PASS: complete MVP verification succeeded.
```

The verified stack head is `3f56a77411ad25cdbcd8f96ee0a97043ef036cb5`.

## Temporary merge authority

GitHub Actions currently fails before any workflow step starts and records no usable step log. Until issue #3 is resolved, local verification may be used only as an explicitly accepted temporary merge authority.

Do not merge any PR merely because this runbook exists. The decision to proceed without remote CI must be recorded explicitly in the PR conversation or issue #3.

## Merge order

Merge exactly in this order:

1. PR #2 — `fix/live-evidence-privacy` into `main`
2. PR #9 — `feat/sqlite-storage` into `main`
3. PR #10 — `feat/analyst-review` into `main`
4. PR #11 — `feat/benchmark-calibration` into `main`
5. PR #12 — `feat/hacker-news-adapter` into `main`
6. PR #13 — `feat/release-readiness` into `main`

## Per-PR procedure

For each PR:

1. Confirm the previous PR is merged.
2. Retarget the current PR base to `main`.
3. Confirm GitHub reports the PR as mergeable.
4. Inspect changed files and verify the diff contains only that slice.
5. Confirm no unresolved review threads exist.
6. Mark the PR ready for review.
7. Record that the full stack passed both Windows verification runs.
8. Merge using the repository's chosen merge method.
9. Confirm `main` advanced to the expected merge commit.
10. Retarget the next PR to `main` before marking it ready.

## Slice expectations

### PR #2

Privacy-safe browser evidence packaging and transport-independent imported discovery.

### PR #9

SQLite persistence, run export and restore.

### PR #10

Analyst decisions, replay and reviewed reporting.

### PR #11

Reviewed-corpus benchmark evaluation.

### PR #12

Official bounded Hacker News adapter.

### PR #13

Run inspection, release hardening, complete verification harness and release documentation.

## Stop conditions

Stop the merge sequence immediately when:

- a PR is not mergeable;
- retargeting introduces unrelated files;
- a branch head changes unexpectedly;
- an unresolved review thread appears;
- a merge conflict is reported;
- a required verification artifact cannot be traced to the verified stack;
- `main` does not advance to the expected commit.

Do not resolve conflicts by force-pushing or rebuilding completed work without first comparing the exact branch and merged history.

## After PR #13

1. Run the complete verification harness from merged `main`.
2. Run it again with `-IncludeHackerNewsSmoke`.
3. Update the merged completion baseline.
4. Resolve or retain issue #3 based on actual Actions evidence.
5. Keep issue #5 open until a real schema migration is implemented.
6. Keep issue #7 open until the reviewed corpus is expanded and used for before/after calibration.
7. Tag the prerelease only after merged-main verification passes.
