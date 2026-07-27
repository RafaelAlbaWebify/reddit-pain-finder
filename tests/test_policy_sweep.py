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
from painfinder.policy_sweep import analyze_policy_thresholds

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


def _record(external_id: str, confidence: float) -> CalibrationRecord:
    assessment = PainAssessment(
        source_external_id=external_id,
        verdict=AssessmentVerdict.PAIN,
        pain_confidence=confidence,
        evidence_confidence=confidence,
        categories=(PainCategory.RELIABILITY,),
        problem_statement="The team is blocked.",
        rationale="Supported.",
        cited_signal_types=(SignalType.EXPLICIT_PROBLEM,),
        cited_evidence=(SPAN,),
    )
    verification = PainVerification(
        source_external_id=external_id,
        verdict=VerificationVerdict.CONFIRM,
        verification_confidence=confidence,
        evidence_confidence=confidence,
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


def test_policy_sweep_replays_records_across_thresholds() -> None:
    cases = [_case("positive", True), _case("negative", False)]
    records = {
        "positive": _record("positive", 0.7),
        "negative": _record("negative", 0.7),
    }

    report = analyze_policy_thresholds(cases, records, thresholds=(0.6, 0.8))

    assert report.replayable_count == 2
    assert report.skipped_count == 0
    assert report.rows[0].accepted_count == 2
    assert report.rows[0].true_positive == 1
    assert report.rows[0].false_positive == 1
    assert report.rows[0].precision == 0.5
    assert report.rows[0].recall == 1.0
    assert report.rows[1].accepted_count == 0
    assert report.rows[1].review_count == 2


def test_policy_sweep_counts_unreplayable_records() -> None:
    cases = [_case("missing", True)]

    report = analyze_policy_thresholds(cases, {}, thresholds=(0.8,))

    assert report.replayable_count == 0
    assert report.skipped_count == 1
    assert report.rows[0].accepted_count == 0
