from __future__ import annotations

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationRecord
from painfinder.domain import (
    EvidenceField,
    EvidenceSpan,
    PainCategory,
    SignalType,
    SourceItem,
    SourceType,
)
from painfinder.pain_assessment import AssessmentVerdict, PainAssessment
from painfinder.pain_policy import FinalPolicyDecision
from painfinder.pain_verification import (
    PainVerification,
    VerificationReason,
    VerificationVerdict,
)
from painfinder.policy_grid import analyze_policy_grid

SPAN = EvidenceSpan(field=EvidenceField.BODY, start=0, end=12, text="We are stuck")


def _case(external_id: str, expected_pain: bool) -> BenchmarkCase:
    return BenchmarkCase(
        item=SourceItem(
            external_id=external_id,
            source_type=SourceType.POST,
            title="",
            body="We are stuck",
            subreddit="smallbusiness",
            canonical_url=f"https://reddit.com/{external_id}",
        ),
        expected_pain=expected_pain,
        expected_categories=(PainCategory.RELIABILITY,) if expected_pain else (),
        expected_cluster=None,
    )


def _record(
    external_id: str,
    *,
    pain_confidence: float,
    evidence_confidence: float,
) -> CalibrationRecord:
    assessment = PainAssessment(
        source_external_id=external_id,
        verdict=AssessmentVerdict.PAIN,
        pain_confidence=pain_confidence,
        evidence_confidence=evidence_confidence,
        categories=(PainCategory.RELIABILITY,),
        problem_statement="The team is blocked.",
        rationale="Supported.",
        cited_signal_types=(SignalType.EXPLICIT_PROBLEM,),
        cited_evidence=(SPAN,),
    )
    verification = PainVerification(
        source_external_id=external_id,
        verdict=VerificationVerdict.CONFIRM,
        verification_confidence=pain_confidence,
        evidence_confidence=evidence_confidence,
        reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
        confirmed_categories=(PainCategory.RELIABILITY,),
        corrected_problem_statement="The team is blocked.",
        rationale="Supported.",
        cited_evidence=(SPAN,),
    )
    return CalibrationRecord(
        source_external_id=external_id,
        subreddit="smallbusiness",
        expected_pain=True,
        expected_categories=(PainCategory.RELIABILITY,),
        candidate_count=1,
        duration_ms=1,
        decision=FinalPolicyDecision.REVIEW,
        assessment=assessment,
        verification=verification,
    )


def test_grid_separates_pain_and_evidence_thresholds() -> None:
    cases = [_case("positive", True), _case("negative", False)]
    records = {
        "positive": _record(
            "positive",
            pain_confidence=0.8,
            evidence_confidence=0.6,
        ),
        "negative": _record(
            "negative",
            pain_confidence=0.6,
            evidence_confidence=0.8,
        ),
    }

    report = analyze_policy_grid(
        cases,
        records,
        pain_thresholds=(0.6, 0.8),
        evidence_thresholds=(0.6, 0.8),
    )

    assert report.replayable_count == 2
    by_threshold = {
        (row.pain_threshold, row.evidence_threshold): row for row in report.rows
    }
    assert by_threshold[(0.6, 0.6)].accepted_count == 2
    assert by_threshold[(0.8, 0.6)].true_positive == 1
    assert by_threshold[(0.8, 0.6)].false_positive == 0
    assert by_threshold[(0.6, 0.8)].true_positive == 0


def test_grid_marks_dominated_configurations() -> None:
    cases = [_case("positive", True), _case("negative", False)]
    records = {
        "positive": _record(
            "positive",
            pain_confidence=0.8,
            evidence_confidence=0.8,
        ),
        "negative": _record(
            "negative",
            pain_confidence=0.6,
            evidence_confidence=0.6,
        ),
    }

    report = analyze_policy_grid(
        cases,
        records,
        pain_thresholds=(0.6, 0.8),
        evidence_thresholds=(0.6,),
    )

    assert len(report.pareto_rows) == 1
    assert report.pareto_rows[0].pain_threshold == 0.8
    assert report.pareto_rows[0].true_positive == 1
    assert report.pareto_rows[0].false_positive == 0
