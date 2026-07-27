import pytest

from painfinder.candidate_audit import CandidateAuditRow
from painfinder.candidate_audit_review import (
    AuditReviewDecision,
    build_review_template,
    summarize_review_rows,
    validate_review_rows,
)


def _audit_row(external_id: str) -> CandidateAuditRow:
    return CandidateAuditRow(
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


def test_review_template_starts_pending() -> None:
    rows = build_review_template((_audit_row("one"), _audit_row("two")))

    summary = summarize_review_rows(rows)

    assert summary.row_count == 2
    assert summary.completed_count == 0
    assert summary.pending_count == 2


def test_completed_review_requires_rationale() -> None:
    audit_rows = (_audit_row("one"),)
    review_rows = build_review_template(audit_rows)
    review_rows = (
        review_rows[0].model_copy(
            update={"review_decision": AuditReviewDecision.DETECTOR_GAP}
        ),
    )

    with pytest.raises(ValueError, match="requires rationale"):
        validate_review_rows(audit_rows, review_rows)


def test_summary_surfaces_actionable_ids() -> None:
    audit_rows = (_audit_row("one"), _audit_row("two"))
    template = build_review_template(audit_rows)
    review_rows = (
        template[0].model_copy(
            update={
                "review_decision": AuditReviewDecision.DETECTOR_GAP,
                "rationale": "Direct reliability pain is present.",
            }
        ),
        template[1].model_copy(
            update={
                "review_decision": AuditReviewDecision.QUESTIONABLE_LABEL,
                "rationale": "The text is general advice rather than pain.",
            }
        ),
    )

    validate_review_rows(audit_rows, review_rows)
    summary = summarize_review_rows(review_rows)

    assert summary.pending_count == 0
    assert summary.detector_gap_ids == ("one",)
    assert summary.questionable_label_ids == ("two",)
