from __future__ import annotations

import json
from collections import Counter
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from painfinder.candidate_audit import CandidateAuditRow


class AuditReviewDecision(StrEnum):
    PENDING = "pending"
    DETECTOR_GAP = "detector_gap"
    QUESTIONABLE_LABEL = "questionable_label"
    ACCEPTABLE_FALSE_POSITIVE = "acceptable_false_positive"
    OUT_OF_SCOPE = "out_of_scope"


class CandidateAuditReviewRow(BaseModel):
    audit: CandidateAuditRow
    review_decision: AuditReviewDecision = AuditReviewDecision.PENDING
    rationale: str = ""
    proposed_detector_family: str = ""


class CandidateAuditReviewSummary(BaseModel):
    row_count: int
    completed_count: int
    pending_count: int
    decision_counts: dict[str, int]
    detector_gap_ids: tuple[str, ...]
    questionable_label_ids: tuple[str, ...]


def load_audit_rows(path: Path) -> tuple[CandidateAuditRow, ...]:
    return tuple(
        CandidateAuditRow.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def load_review_rows(path: Path) -> tuple[CandidateAuditReviewRow, ...]:
    return tuple(
        CandidateAuditReviewRow.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def build_review_template(
    audit_rows: tuple[CandidateAuditRow, ...],
) -> tuple[CandidateAuditReviewRow, ...]:
    return tuple(CandidateAuditReviewRow(audit=row) for row in audit_rows)


def validate_review_rows(
    audit_rows: tuple[CandidateAuditRow, ...],
    review_rows: tuple[CandidateAuditReviewRow, ...],
) -> None:
    expected_ids = [row.source_external_id for row in audit_rows]
    reviewed_ids = [row.audit.source_external_id for row in review_rows]
    if reviewed_ids != expected_ids:
        raise ValueError(
            "review rows must contain every audit row exactly once and in order"
        )

    for row in review_rows:
        completed = row.review_decision is not AuditReviewDecision.PENDING
        if completed and not row.rationale.strip():
            raise ValueError(
                f"completed review requires rationale: {row.audit.source_external_id}"
            )


def summarize_review_rows(
    review_rows: tuple[CandidateAuditReviewRow, ...],
) -> CandidateAuditReviewSummary:
    counts = Counter(row.review_decision.value for row in review_rows)
    pending = counts[AuditReviewDecision.PENDING.value]
    return CandidateAuditReviewSummary(
        row_count=len(review_rows),
        completed_count=len(review_rows) - pending,
        pending_count=pending,
        decision_counts=dict(sorted(counts.items())),
        detector_gap_ids=tuple(
            row.audit.source_external_id
            for row in review_rows
            if row.review_decision is AuditReviewDecision.DETECTOR_GAP
        ),
        questionable_label_ids=tuple(
            row.audit.source_external_id
            for row in review_rows
            if row.review_decision is AuditReviewDecision.QUESTIONABLE_LABEL
        ),
    )


def write_review_rows(rows: tuple[CandidateAuditReviewRow, ...], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(row.model_dump_json() + "\n" for row in rows),
        encoding="utf-8",
    )


def write_review_summary(summary: CandidateAuditReviewSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
