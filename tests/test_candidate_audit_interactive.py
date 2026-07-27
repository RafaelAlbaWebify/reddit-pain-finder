from pathlib import Path

from painfinder.candidate_audit import CandidateAuditRow
from painfinder.candidate_audit_interactive import review_pending_rows
from painfinder.candidate_audit_review import (
    AuditReviewDecision,
    CandidateAuditReviewRow,
    load_review_rows,
    write_review_rows,
)


def _review_row(external_id: str) -> CandidateAuditReviewRow:
    return CandidateAuditReviewRow(
        audit=CandidateAuditRow(
            source_external_id=external_id,
            error_type="false_negative",
            expected_pain=True,
            expected_categories=("reliability",),
            subreddit="SaaS",
            source_type="comment",
            title="",
            body="A recurring failure blocks the workflow.",
            canonical_url="https://www.reddit.com/r/SaaS/comments/example/",
            detector_ids=(),
            signal_types=(),
            signal_reasons=(),
            latest_decision="reject",
            latest_failure_stage=None,
        )
    )


def test_interactive_reviewer_saves_completed_row(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.jsonl"
    write_review_rows((_review_row("one"),), worksheet)
    answers = iter(["d", "Direct recurring reliability pain.", "reliability narrative"])

    rows = review_pending_rows(
        worksheet,
        input_fn=lambda _: next(answers),
        output_fn=lambda _: None,
    )

    assert rows[0].review_decision is AuditReviewDecision.DETECTOR_GAP
    assert rows[0].rationale == "Direct recurring reliability pain."
    assert rows[0].proposed_detector_family == "reliability narrative"
    assert load_review_rows(worksheet) == rows


def test_interactive_reviewer_can_save_and_exit(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.jsonl"
    write_review_rows((_review_row("one"), _review_row("two")), worksheet)
    answers = iter(["q", "Advice-only text was labeled as pain.", "x"])

    rows = review_pending_rows(
        worksheet,
        input_fn=lambda _: next(answers),
        output_fn=lambda _: None,
    )

    assert rows[0].review_decision is AuditReviewDecision.QUESTIONABLE_LABEL
    assert rows[1].review_decision is AuditReviewDecision.PENDING
    assert load_review_rows(worksheet) == rows
