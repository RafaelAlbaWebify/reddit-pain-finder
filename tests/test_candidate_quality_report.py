from __future__ import annotations

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationRecord
from painfinder.candidate_quality_report import analyze_candidate_quality
from painfinder.domain import PainCategory, SourceItem, SourceType
from painfinder.pain_policy import FinalPolicyDecision


def _case(
    external_id: str,
    body: str,
    *,
    expected_pain: bool,
    categories: tuple[PainCategory, ...] = (),
) -> BenchmarkCase:
    return BenchmarkCase(
        item=SourceItem(
            external_id=external_id,
            source_type=SourceType.POST,
            title="",
            body=body,
            subreddit="smallbusiness",
            canonical_url=f"https://reddit.com/{external_id}",
        ),
        expected_pain=expected_pain,
        expected_categories=categories,
        expected_cluster=None,
    )


def _record(
    external_id: str,
    *,
    candidate_count: int,
    decision: FinalPolicyDecision,
) -> CalibrationRecord:
    return CalibrationRecord(
        source_external_id=external_id,
        subreddit="smallbusiness",
        expected_pain=True,
        expected_categories=(),
        candidate_count=candidate_count,
        duration_ms=1,
        decision=decision,
    )


def test_candidate_quality_report_separates_stage_errors() -> None:
    cases = [
        _case(
            "positive-detected",
            "I can't access the account and need a solution.",
            expected_pain=True,
            categories=(PainCategory.RELIABILITY,),
        ),
        _case(
            "positive-missed",
            "The approval process feels opaque and arbitrary.",
            expected_pain=True,
            categories=(PainCategory.COMPLEXITY,),
        ),
        _case(
            "negative-detected",
            "How do you organize a normal workday?",
            expected_pain=False,
        ),
        _case(
            "negative-missed",
            "We launched the product yesterday.",
            expected_pain=False,
        ),
    ]
    records = {
        "positive-detected": _record(
            "positive-detected",
            candidate_count=2,
            decision=FinalPolicyDecision.REVIEW,
        ),
        "positive-missed": _record(
            "positive-missed",
            candidate_count=0,
            decision=FinalPolicyDecision.REJECT,
        ),
        "negative-detected": _record(
            "negative-detected",
            candidate_count=1,
            decision=FinalPolicyDecision.REJECT,
        ),
        "negative-missed": _record(
            "negative-missed",
            candidate_count=0,
            decision=FinalPolicyDecision.REJECT,
        ),
    }

    report = analyze_candidate_quality(cases, records)

    assert report.candidate_true_positive == 1
    assert report.candidate_false_positive == 1
    assert report.candidate_true_negative == 1
    assert report.candidate_false_negative == 1
    assert report.candidate_precision == 0.5
    assert report.candidate_recall == 0.5
    assert report.candidate_miss_ids == ("positive-missed",)
    assert report.misses_by_expected_category == {"complexity": 1}
    assert report.final_review_count == 1
    assert report.final_reject_count == 3
    assert report.missing_record_count == 0


def test_candidate_quality_report_limits_examples() -> None:
    cases = [
        _case(
            "one",
            "An opaque process.",
            expected_pain=True,
            categories=(PainCategory.COMPLEXITY,),
        ),
        _case(
            "two",
            "An arbitrary process.",
            expected_pain=True,
            categories=(PainCategory.COMPLEXITY,),
        ),
    ]

    report = analyze_candidate_quality(cases, {}, example_limit=1)

    assert report.candidate_miss_count == 2
    assert len(report.candidate_miss_examples) == 1
    assert report.missing_record_count == 2
