from __future__ import annotations

import csv
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.domain import SourceItem, SourceType
from painfinder.storage import SQLiteResearchRepository


class SamplingError(RuntimeError):
    pass


@dataclass(frozen=True)
class SamplingCandidate:
    run_id: str
    item: SourceItem
    packet_id: str


@dataclass(frozen=True)
class SamplingResult:
    run_ids: tuple[str, ...]
    available_count: int
    selected_count: int
    excluded_exact_duplicates: int
    excluded_near_duplicates: int
    communities: tuple[str, ...]
    source_types: tuple[str, ...]
    selected_ids: tuple[str, ...]
    selected_items: tuple[dict[str, str], ...]


def prepare_blind_review_packets(
    repository: SQLiteResearchRepository,
    run_ids: str | list[str] | tuple[str, ...],
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

    normalized_run_ids = _normalize_run_ids(run_ids)
    candidates = _load_candidates(repository, normalized_run_ids)
    unique_items, exact_count, near_count = _deduplicate(
        candidates,
        threshold=near_duplicate_threshold,
    )
    selected = _balanced_sample(unique_items, sample_size)
    if not selected:
        raise SamplingError("No reviewable source items remain after deduplication")

    _write_packet(reviewer_a_output, selected)
    _write_packet(reviewer_b_output, selected)

    result = SamplingResult(
        run_ids=normalized_run_ids,
        available_count=len(candidates),
        selected_count=len(selected),
        excluded_exact_duplicates=exact_count,
        excluded_near_duplicates=near_count,
        communities=tuple(
            sorted({candidate.item.subreddit or "(none)" for candidate in selected})
        ),
        source_types=tuple(
            sorted({candidate.item.source_type.value for candidate in selected})
        ),
        selected_ids=tuple(candidate.packet_id for candidate in selected),
        selected_items=tuple(
            {
                "packet_id": candidate.packet_id,
                "run_id": candidate.run_id,
                "external_id": candidate.item.external_id,
            }
            for candidate in selected
        ),
    )
    _write_manifest(manifest_output, sample_size, near_duplicate_threshold, result)
    return result


def _normalize_run_ids(run_ids: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    values = [run_ids] if isinstance(run_ids, str) else list(run_ids)
    normalized: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in normalized:
            normalized.append(clean)
    if not normalized:
        raise SamplingError("At least one run_id is required")
    return tuple(normalized)


def _load_candidates(
    repository: SQLiteResearchRepository,
    run_ids: tuple[str, ...],
) -> list[SamplingCandidate]:
    runs = []
    for run_id in run_ids:
        run = repository.get_run(run_id)
        if run is None:
            raise SamplingError(f"Unknown run: {run_id}")
        if run.status != "completed":
            raise SamplingError(f"Run is not completed: {run_id} ({run.status})")
        runs.append(run)

    multi_run = len(runs) > 1
    candidates: list[SamplingCandidate] = []
    for run in runs:
        for item in repository.list_source_items(run.run_id):
            packet_id = (
                _multi_run_packet_id(run.run_id, item.external_id)
                if multi_run
                else item.external_id
            )
            candidates.append(
                SamplingCandidate(
                    run_id=run.run_id,
                    item=item,
                    packet_id=packet_id,
                )
            )
    return candidates


def _multi_run_packet_id(run_id: str, external_id: str) -> str:
    identity = f"{run_id}\0{external_id}".encode("utf-8")
    return f"sample-{sha256(identity).hexdigest()[:20]}"


def _deduplicate(
    candidates: list[SamplingCandidate],
    *,
    threshold: float,
) -> tuple[list[SamplingCandidate], int, int]:
    accepted: list[SamplingCandidate] = []
    seen_hashes: set[str] = set()
    token_sets: list[set[str]] = []
    exact_count = 0
    near_count = 0

    for candidate in sorted(
        candidates,
        key=lambda value: (value.run_id, value.item.external_id),
    ):
        item = candidate.item
        if item.content_hash in seen_hashes:
            exact_count += 1
            continue
        tokens = _tokens(item)
        if any(_jaccard(tokens, existing) >= threshold for existing in token_sets):
            near_count += 1
            continue
        seen_hashes.add(item.content_hash)
        token_sets.append(tokens)
        accepted.append(candidate)
    return accepted, exact_count, near_count


def _balanced_sample(
    candidates: list[SamplingCandidate],
    sample_size: int,
) -> list[SamplingCandidate]:
    buckets: dict[tuple[str, str, SourceType], deque[SamplingCandidate]] = defaultdict(
        deque
    )
    for candidate in sorted(
        candidates,
        key=lambda value: (value.run_id, value.item.external_id),
    ):
        item = candidate.item
        buckets[(candidate.run_id, item.subreddit or "", item.source_type)].append(
            candidate
        )

    selected: list[SamplingCandidate] = []
    keys = deque(
        sorted(
            buckets,
            key=lambda key: (key[0], key[1], key[2].value),
        )
    )
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


def _write_packet(path: Path, candidates: list[SamplingCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for candidate in candidates:
            item = candidate.item
            writer.writerow(
                {
                    "external_id": candidate.packet_id,
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
    requested_size: int,
    threshold: float,
    result: SamplingResult,
) -> None:
    payload = {
        "run_ids": result.run_ids,
        "requested_sample_size": requested_size,
        "near_duplicate_threshold": threshold,
        "available_count": result.available_count,
        "selected_count": result.selected_count,
        "excluded_exact_duplicates": result.excluded_exact_duplicates,
        "excluded_near_duplicates": result.excluded_near_duplicates,
        "communities": result.communities,
        "source_types": result.source_types,
        "selected_ids": result.selected_ids,
        "selected_items": result.selected_items,
    }
    if len(result.run_ids) == 1:
        payload["run_id"] = result.run_ids[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")