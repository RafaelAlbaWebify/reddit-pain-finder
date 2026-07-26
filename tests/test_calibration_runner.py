from __future__ import annotations

import json
from pathlib import Path

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import (
    CalibrationRecord,
    CalibrationStage,
    load_latest_records,
    run_calibration,
    write_calibration_metrics,
)
from painfinder.domain import PainCategory, SourceItem, SourceType
from painfinder.pain_assessment import (
    AssessmentVerdict,
    PainAssessment,
    PainAssessmentRequest,
)
from painfinder.pain_policy import FinalPolicyDecision
from painfinder.pain_verification import (
    PainVerification,
    PainVerificationRequest,
    VerificationReason,
    VerificationVerdict,
)


def _case(external_id: str, body: str, expected_pain: bool) -> BenchmarkCase:
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
        expected_categories=(PainCategory.RELIABILITY,) if expected_pain else (),
        expected_cluster=None,
    )


class _Assessor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def assess(self, request: PainAssessmentRequest) -> PainAssessment:
        self.calls.append(request.item.external_id)
        signal = request.candidate_signals[0]
        return PainAssessment(
            source_external_id=request.item.external_id,
            verdict=AssessmentVerdict.PAIN,
            pain_confidence=0.9,
            evidence_confidence=0.9,
            categories=(PainCategory.RELIABILITY,),
            problem_statement="The team is overloaded.",
            rationale="The source reports operational overload.",
            cited_signal_types=(signal.signal_type,),
            cited_evidence=signal.evidence_spans,
        )


class _Verifier:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def verify(self, request: PainVerificationRequest) -> PainVerification:
        self.calls.append(request.assessment.source_external_id)
        return PainVerification(
            source_external_id=request.assessment.source_external_id,
            verdict=VerificationVerdict.CONFIRM,
            verification_confidence=0.9,
            evidence_confidence=0.9,
            reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
            confirmed_categories=request.assessment.categories,
            corrected_problem_statement=request.assessment.problem_statement,
            rationale="The candidate evidence supports the assessment.",
            cited_evidence=request.assessment.cited_evidence,
        )


def test_runner_records_candidate_misses_and_pipeline_outcomes(
    tmp_path: Path,
) -> None:
    cases = [
        _case("pain", "We are overwhelmed by the backlog.", True),
        _case("neutral", "Thanks for sharing.", False),
    ]
    assessor = _Assessor()
    verifier = _Verifier()
    output = tmp_path / "attempts.jsonl"

    metrics = run_calibration(
        cases,
        assessor,
        verifier,
        output_path=output,
    )
    records = load_latest_records(output)

    assert assessor.calls == ["pain"]
    assert verifier.calls == ["pain"]
    assert records["pain"].decision is FinalPolicyDecision.ACCEPT
    assert records["neutral"].decision is FinalPolicyDecision.REJECT
    assert records["neutral"].candidate_count == 0
    assert records["pain"].subreddit == "smallbusiness"
    assert metrics.true_positive == 1
    assert metrics.true_negative == 1
    assert metrics.accuracy == 1.0
    assert metrics.attempted_count == 2
    assert metrics.resumed_count == 0
    assert metrics.assessor_verdict_counts == {"not_run": 1, "pain": 1}
    assert metrics.verifier_verdict_counts == {"confirm": 1, "not_run": 1}
    assert metrics.policy_reason_counts == {
        "candidate_miss": 1,
        "verifier_confirmed": 1,
    }
    assert metrics.expected_category_counts == {"reliability": 1}
    assert metrics.assessed_category_counts == {"reliability": 1}
    assert metrics.subreddit_counts == {"smallbusiness": 2}
    assert not output.with_name(".attempts.jsonl.tmp").exists()


def test_runner_resumes_successful_records_without_model_calls(
    tmp_path: Path,
) -> None:
    cases = [_case("pain", "We are overwhelmed by the backlog.", True)]
    output = tmp_path / "attempts.jsonl"
    first_assessor = _Assessor()
    first_verifier = _Verifier()

    first = run_calibration(
        cases,
        first_assessor,
        first_verifier,
        output_path=output,
    )
    second_assessor = _Assessor()
    second_verifier = _Verifier()
    second = run_calibration(
        cases,
        second_assessor,
        second_verifier,
        output_path=output,
    )

    assert first_assessor.calls == ["pain"]
    assert second_assessor.calls == []
    assert second_verifier.calls == []
    assert first.attempted_count == 1
    assert second.attempted_count == 0
    assert second.resumed_count == 1
    assert len(output.read_text(encoding="utf-8").splitlines()) == 1


def test_runner_preserves_structured_error_and_retries_it(tmp_path: Path) -> None:
    cases = [_case("pain", "We are overwhelmed by the backlog.", True)]
    output = tmp_path / "attempts.jsonl"

    class FailingAssessor:
        def assess(self, request: PainAssessmentRequest) -> PainAssessment:
            raise RuntimeError("model unavailable")

    first = run_calibration(
        cases,
        FailingAssessor(),
        _Verifier(),
        output_path=output,
    )
    failed_record = load_latest_records(output)["pain"]
    second = run_calibration(
        cases,
        _Assessor(),
        _Verifier(),
        output_path=output,
    )
    records = load_latest_records(output)

    assert first.error_count == 1
    assert first.failure_stage_counts == {"assessor": 1}
    assert failed_record.failure is not None
    assert failed_record.failure.stage is CalibrationStage.ASSESSOR
    assert failed_record.failure.error_type == "RuntimeError"
    assert failed_record.failure.message == "model unavailable"
    assert second.error_count == 0
    assert records["pain"].decision is FinalPolicyDecision.ACCEPT
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_latest_record_wins_and_metrics_are_written_atomically(
    tmp_path: Path,
) -> None:
    output = tmp_path / "attempts.jsonl"
    completed = CalibrationRecord(
        source_external_id="one",
        subreddit="smallbusiness",
        expected_pain=True,
        expected_categories=(PainCategory.RELIABILITY,),
        candidate_count=0,
        duration_ms=3,
        decision=FinalPolicyDecision.REJECT,
    )
    output.write_text(completed.model_dump_json() + "\n", encoding="utf-8")

    records = load_latest_records(output)
    metrics_path = tmp_path / "metrics.json"
    metrics = run_calibration(
        [_case("one", "Thanks for sharing.", True)],
        _Assessor(),
        _Verifier(),
        output_path=output,
    )
    write_calibration_metrics(metrics, metrics_path)
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert records["one"].decision is FinalPolicyDecision.REJECT
    assert payload["false_negative"] == 1
    assert payload["decision_counts"] == {"reject": 1}
    assert payload["completed_duration_ms"] == 3
    assert not metrics_path.with_name(".metrics.json.tmp").exists()
