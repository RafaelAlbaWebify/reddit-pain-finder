from pathlib import Path

from painfinder.candidate_audit import CandidateAuditRow
from painfinder.candidate_audit_review import (
    AuditReviewDecision,
    CandidateAuditReviewRow,
)
from painfinder.candidate_final_validation import (
    build_candidate_final_validation,
    write_candidate_final_validation,
)


def _audit(source_id: str, error_type: str) -> CandidateAuditRow:
    return CandidateAuditRow(
        source_external_id=source_id,
        error_type=error_type,
        expected_pain=error_type == "false_negative",
        expected_categories=(),
        subreddit="smallbusiness",
        source_type="post",
        title="",
        body="example",
        canonical_url=f"https://reddit.com/{source_id}",
        detector_ids=(),
        signal_types=(),
        signal_reasons=(),
        latest_decision=None,
        latest_failure_stage=None,
    )


def test_final_validation_passes_on_recovery_without_new_false_positives(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    baseline_gap = CandidateAuditReviewRow(
        audit=_audit("gap-recovered", "false_negative"),
        review_decision=AuditReviewDecision.DETECTOR_GAP,
        rationale="real detector gap",
    )
    baseline_fp = CandidateAuditReviewRow(
        audit=_audit("known-fp", "false_positive"),
        review_decision=AuditReviewDecision.ACCEPTABLE_FALSE_POSITIVE,
        rationale="known false positive",
    )

    def current_audit(*_args: object, **_kwargs: object) -> tuple[CandidateAuditRow, ...]:
        return (_audit("known-fp", "false_positive"),)

    monkeypatch.setattr(
        "painfinder.candidate_final_validation.build_candidate_error_audit",
        current_audit,
    )
    validation = build_candidate_final_validation([], {}, (baseline_gap, baseline_fp))

    assert validation.passed
    assert validation.recovered_detector_gap_ids == ("gap-recovered",)
    assert validation.new_false_positive_ids == ()

    json_output = tmp_path / "validation.json"
    markdown_output = tmp_path / "validation.md"
    write_candidate_final_validation(
        validation,
        json_output=json_output,
        markdown_output=markdown_output,
    )
    assert '"passed": true' in json_output.read_text(encoding="utf-8")
    assert "**Status:** PASS" in markdown_output.read_text(encoding="utf-8")


def test_final_validation_fails_when_a_new_false_positive_appears(
    monkeypatch: object,
) -> None:
    baseline_gap = CandidateAuditReviewRow(
        audit=_audit("gap-recovered", "false_negative"),
        review_decision=AuditReviewDecision.DETECTOR_GAP,
        rationale="real detector gap",
    )

    def current_audit(*_args: object, **_kwargs: object) -> tuple[CandidateAuditRow, ...]:
        return (_audit("new-fp", "false_positive"),)

    monkeypatch.setattr(
        "painfinder.candidate_final_validation.build_candidate_error_audit",
        current_audit,
    )
    validation = build_candidate_final_validation([], {}, (baseline_gap,))

    assert not validation.passed
    assert validation.new_false_positive_ids == ("new-fp",)
