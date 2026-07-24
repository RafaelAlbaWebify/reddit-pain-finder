from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from painfinder.domain import SourceItem

_CHUNK_SIZE = 500


@dataclass(frozen=True)
class CrossRunDeduplicationResult:
    items: tuple[SourceItem, ...]
    excluded_external_ids: int
    excluded_content_hashes: int


def filter_cross_run_duplicates(
    database_path: Path,
    items: list[SourceItem],
) -> CrossRunDeduplicationResult:
    """Return only items not already stored in any previous research run."""
    if not database_path.exists() or not items:
        return CrossRunDeduplicationResult(tuple(items), 0, 0)

    external_ids = {item.external_id for item in items}
    content_hashes = {item.content_hash for item in items}

    with sqlite3.connect(database_path) as connection:
        known_external_ids = _existing_values(
            connection,
            column="external_id",
            values=external_ids,
        )
        known_content_hashes = _existing_values(
            connection,
            column="content_hash",
            values=content_hashes,
        )

    retained: list[SourceItem] = []
    excluded_external_ids = 0
    excluded_content_hashes = 0

    for item in items:
        if item.external_id in known_external_ids:
            excluded_external_ids += 1
            continue
        if item.content_hash in known_content_hashes:
            excluded_content_hashes += 1
            continue
        retained.append(item)
        known_external_ids.add(item.external_id)
        known_content_hashes.add(item.content_hash)

    return CrossRunDeduplicationResult(
        items=tuple(retained),
        excluded_external_ids=excluded_external_ids,
        excluded_content_hashes=excluded_content_hashes,
    )


def _existing_values(
    connection: sqlite3.Connection,
    *,
    column: str,
    values: set[str],
) -> set[str]:
    if column not in {"external_id", "content_hash"}:
        raise ValueError(f"Unsupported source-item lookup column: {column}")

    existing: set[str] = set()
    ordered = sorted(values)
    for index in range(0, len(ordered), _CHUNK_SIZE):
        chunk = ordered[index : index + _CHUNK_SIZE]
        placeholders = ",".join("?" for _ in chunk)
        rows = connection.execute(
            f"SELECT DISTINCT {column} FROM source_items "
            f"WHERE {column} IN ({placeholders})",
            chunk,
        ).fetchall()
        existing.update(str(row[0]) for row in rows)
    return existing
