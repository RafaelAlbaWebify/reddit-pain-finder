from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from painfinder.candidate_audit_review import (
    AuditReviewDecision,
    CandidateAuditReviewRow,
    load_review_rows,
    write_review_rows,
)

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

_DECISION_ALIASES = {
    "d": AuditReviewDecision.DETECTOR_GAP,
    "q": AuditReviewDecision.QUESTIONABLE_LABEL,
    "f": AuditReviewDecision.ACCEPTABLE_FALSE_POSITIVE,
    "o": AuditReviewDecision.OUT_OF_SCOPE,
    "s": AuditReviewDecision.PENDING,
}


def review_pending_rows(
    worksheet: Path,
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> tuple[CandidateAuditReviewRow, ...]:
    rows = list(load_review_rows(worksheet))
    pending_indices = [
        index
        for index, row in enumerate(rows)
        if row.review_decision is AuditReviewDecision.PENDING
    ]

    for position, index in enumerate(pending_indices, start=1):
        row = rows[index]
        audit = row.audit
        output_fn("")
        output_fn(f"[{position}/{len(pending_indices)}] {audit.source_external_id}")
        output_fn(f"Error: {audit.error_type}")
        output_fn(f"Expected pain: {audit.expected_pain}")
        output_fn(f"Expected categories: {', '.join(audit.expected_categories) or '<none>'}")
        output_fn(f"Source: {audit.source_type} in r/{audit.subreddit}")
        if audit.title:
            output_fn(f"Title: {audit.title}")
        output_fn("Body:")
        output_fn(audit.body)
        output_fn(f"URL: {audit.canonical_url}")
        output_fn(f"Detector IDs: {', '.join(audit.detector_ids) or '<none>'}")
        output_fn("")
        output_fn("d=detector gap, q=questionable label, f=acceptable false positive")
        output_fn("o=out of scope, s=skip, x=save and exit")

        choice = _read_choice(input_fn)
        if choice == "x":
            write_review_rows(tuple(rows), worksheet)
            return tuple(rows)
        if choice == "s":
            continue

        decision = _DECISION_ALIASES[choice]
        rationale = _read_non_empty(input_fn, "Rationale: ")
        detector_family = ""
        if decision is AuditReviewDecision.DETECTOR_GAP:
            detector_family = input_fn("Proposed detector family (optional): ").strip()

        rows[index] = row.model_copy(
            update={
                "review_decision": decision,
                "rationale": rationale,
                "proposed_detector_family": detector_family,
            }
        )
        write_review_rows(tuple(rows), worksheet)

    return tuple(rows)


def _read_choice(input_fn: InputFn) -> str:
    while True:
        choice = input_fn("Decision: ").strip().lower()
        if choice in {*_DECISION_ALIASES, "x"}:
            return choice


def _read_non_empty(input_fn: InputFn, prompt: str) -> str:
    while True:
        value = input_fn(prompt).strip()
        if value:
            return value
