from __future__ import annotations

import csv
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.domain import SourceItem, SourceType
from painfinder.storage import SQLiteResearchRepository


class SamplingError(RuntimeError):
    pass


@dataclass(frozen=True)
class SamplingResult:
    available_count: int
    selected_count: int
    excluded_exact_duplicates: int
    excluded_near_duplicates: int
    communities: tuple[str, ...]
    source_types: tuple[str, ...]
    selected_ids: tuple[str, ...]


def prepare_blind_review_packets(
    repository: SQLiteResearchRepository,
    run_id: str,
    *,
    sample_size: int,
    reviewer_a_output: Path,
    reviewer_b_output: Path,
    manifest_output: Path,
    near_duplicate_threshold: float = 0.9,
) -> SamplingResult:
    if sample_size < 1:
        raise SamplingError("sample_size must be at least 1")
    if not 0.5 <= near_duplicate_threshold <= 1.0:
        raise SamplingError("near_duplicate_threshold must be between 0.5 and 1.0")
    if repository.get_run(run_id) is None:
        raise SamplingError(f"Unknown run: {run_id}")

    items = repository.list_source_items(run_id)
    unique_items, exact_count, near_count = _deduplicate(
        items,
        threshold=near_duplicate_threshold,
    )
    selected = _balanced_sample(unique_items, sample_size)
    if not selected:
        raise SamplingError("No reviewable source items remain after deduplication")

    _write_packet(reviewer_a_output, selected)
    _write_packet(reviewer_b_output, selected)

    result = SamplingResult(
        available_count=len(items),
        selected_count=len(selected),
        excluded_exact_duplicates=exact_count,
        excluded_near_duplicates=near_count,
        communities=tuple(sorted({item.subreddit or "(none)" for item in selected})),
        source_types=tuple(sorted({item.source_type.value for item in selected})),
        selected_ids=tuple(item.external_id for item in selected),
    )
    _write_manifest(manifest_output, run_id, sample_size, near_duplicate_threshold, result)
    return result


def _deduplicate(
    items: list[SourceItem],
    *,
    threshold: float,
) -> tuple[list[SourceItem], int, int]:
    accepted: list[SourceItem] = []
    seen_hashes: set[str] = set()
    token_sets: list[set[str]] = []
    exact_count = 0
    near_count = 0

    for item in sorted(items, key=lambda value: value.external_id):
        if item.content_hash in seen_hashes:
            exact_count += 1
            continue
        tokens = _tokens(item)
        if any(_jaccard(tokens, existing) >= threshold for existing in token_sets):
            near_count += 1
            continue
        seen_hashes.add(item.content_hash)
        token_sets.append(tokens)
        accepted.append(item)
    return accepted, exact_count, near_count


def _balanced_sample(items: list[SourceItem], sample_size: int) -> list[SourceItem]:
    buckets: dict[tuple[str, SourceType], deque[SourceItem]] = defaultdict(deque)
    for item in sorted(items, key=lambda value: value.external_id):
        buckets[(item.subreddit or "", item.source_type)].append(item)

    selected: list[SourceItem] = []
    keys = deque(sorted(buckets, key=lambda key: (key[0], key[1].value)))
    while keys and len(selected) < sample_size:
        key = keys.popleft()
        bucket = buckets[key]
        selected.append(bucket.popleft())
        if bucket:
            keys.append(key)
    return selected


def _tokens(item: SourceItem) -> set[str]:
    text = f"{item.title} {item.body}".lower()
    return set(re.findall(r"[a-z0-9]+", text))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _write_packet(path: Path, items: list[SourceItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
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


def _write_manifest(
    path: Path,
    run_id: str,
    requested_size: int,
    threshold: float,
    result: SamplingResult,
) -> None:
    payload = {
        "run_id": run_id,
        "requested_sample_size": requested_size,
        "near_duplicate_threshold": threshold,
        "available_count": result.available_count,
        "selected_count": result.selected_count,
        "excluded_exact_duplicates": result.excluded_exact_duplicates,
        "excluded_near_duplicates": result.excluded_near_duplicates,
        "communities": result.communities,
        "source_types": result.source_types,
        "selected_ids": result.selected_ids,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
