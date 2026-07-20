from __future__ import annotations

import csv
from pathlib import Path

from painfinder.storage import SQLiteResearchRepository

REVIEW_COLUMNS = (
    "external_id",
    "source_type",
    "title",
    "body",
    "community",
    "canonical_url",
    "expected_pain",
    "expected_categories",
    "expected_cluster",
    "review_status",
    "reviewer",
    "reviewed_at",
    "rationale",
)


def write_review_worksheet(
    repository: SQLiteResearchRepository,
    run_id: str,
    output: Path,
) -> int:
    run = repository.get_run(run_id)
    if run is None:
        raise KeyError(f"Unknown run: {run_id}")

    items = repository.list_source_items(run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "external_id": item.external_id,
                    "source_type": item.source_type.value,
                    "title": item.title,
                    "body": item.body,
                    "community": item.subreddit or "",
                    "canonical_url": str(item.canonical_url),
                    "expected_pain": "",
                    "expected_categories": "",
                    "expected_cluster": "",
                    "review_status": "unreviewed",
                    "reviewer": "",
                    "reviewed_at": "",
                    "rationale": "",
                }
            )
    return len(items)
