from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from painfinder.benchmark import BenchmarkCase
from painfinder.candidate_detection import generate_candidate_signals
from painfinder.pain_assessment import (
    PainAssessment,
    PainAssessmentRequest,
    PainAssessor,
)
from painfinder.pain_policy import (
    FinalPolicyDecision,
    PainPolicy,
    PainPolicyInput,
    PolicyOutcome,
    apply_pain_policy,
)
from painfinder.pain_verification import (
    PainVerification,
    PainVerificationRequest,
    PainVerifier,
)


class CalibrationRecord(BaseModel):
    source_external_id: str = Field(min_length=1)
    expected_pain: bool
    candidate_count: int = Field(ge=0)
    decision: FinalPolicyDecision | None = None
    assessment: PainAssessment | None = None
    verification: PainVerification | None = None
    policy_outcome: PolicyOutcome | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_terminal_state(self) -> CalibrationRecord:
        if self.error is None and self.decision is None:
            raise ValueError("successful record requires a decision")
        if self.error is not None and self.decision is not None:
            raise ValueError("error record cannot contain a decision")
        if (
            self.policy_outcome is not None
            and self.decision is not self.policy_outcome.decision
        ):
            raise ValueError("record decision must match policy outcome")
        return self


class CalibrationMetrics(BaseModel):
    case_count: int
    completed_count: int
    error_count: int
    accepted_count: int
    rejected_count: int
    review_count: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    accuracy: float
    decision_counts: dict[str, int]
    error_ids: tuple[str, ...]


def run_calibration(
    cases: list[BenchmarkCase],
    assessor: PainAssessor,
    verifier: PainVerifier,
    *,
    output_path: Path,
    policy: PainPolicy | None = None,
) -> CalibrationMetrics:
    latest = load_latest_records(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for case in sorted(cases, key=lambda value: value.item.external_id):
        existing = latest.get(case.item.external_id)
        if existing is not None and existing.error is None:
            continue

        record = _run_case(case, assessor, verifier, policy=policy)
        with output_path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(record.model_dump_json() + "\n")
            handle.flush()
        latest[case.item.external_id] = record

    return evaluate_calibration(cases, latest)


def load_latest_records(path: Path) -> dict[str, CalibrationRecord]:
    if not path.exists():
        return {}

    records: dict[str, CalibrationRecord] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = CalibrationRecord.model_validate_json(line)
        except ValueError as error:
            raise ValueError(
                f"Invalid calibration record on line {line_number}: {error}"
            ) from error
        records[record.source_external_id] = record
    return records


def evaluate_calibration(
    cases: list[BenchmarkCase],
    records: dict[str, CalibrationRecord],
) -> CalibrationMetrics:
    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0
    decision_counts: Counter[str] = Counter()
    error_ids: list[str] = []

    for case in cases:
        record = records.get(case.item.external_id)
        if record is None or record.error is not None:
            error_ids.append(case.item.external_id)
            decision_counts["error"] += 1
            continue

        assert record.decision is not None
        decision_counts[record.decision.value] += 1
        predicted_pain = record.decision is FinalPolicyDecision.ACCEPT

        if case.expected_pain and predicted_pain:
            true_positive += 1
        elif case.expected_pain:
            false_negative += 1
        elif predicted_pain:
            false_positive += 1
        else:
            true_negative += 1

    completed_count = len(cases) - len(error_ids)
    accepted_count = decision_counts[FinalPolicyDecision.ACCEPT.value]
    rejected_count = decision_counts[FinalPolicyDecision.REJECT.value]
    review_count = decision_counts[FinalPolicyDecision.REVIEW.value]

    return CalibrationMetrics(
        case_count=len(cases),
        completed_count=completed_count,
        error_count=len(error_ids),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        review_count=review_count,
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        precision=_ratio(true_positive, true_positive + false_positive),
        recall=_ratio(true_positive, true_positive + false_negative),
        accuracy=_ratio(true_positive + true_negative, completed_count),
        decision_counts=dict(sorted(decision_counts.items())),
        error_ids=tuple(sorted(error_ids)),
    )


def write_calibration_metrics(metrics: CalibrationMetrics, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metrics.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )


def _run_case(
    case: BenchmarkCase,
    assessor: PainAssessor,
    verifier: PainVerifier,
    *,
    policy: PainPolicy | None,
) -> CalibrationRecord:
    signals = generate_candidate_signals([case.item])
    if not signals:
        return CalibrationRecord(
            source_external_id=case.item.external_id,
            expected_pain=case.expected_pain,
            candidate_count=0,
            decision=FinalPolicyDecision.REJECT,
        )

    try:
        assessment_request = PainAssessmentRequest(
            item=case.item,
            candidate_signals=tuple(signals),
        )
        assessment = assessor.assess(assessment_request)
        verification = verifier.verify(
            PainVerificationRequest(
                assessment_request=assessment_request,
                assessment=assessment,
            )
        )
        outcome = apply_pain_policy(
            PainPolicyInput(
                assessment=assessment,
                verification=verification,
            ),
            policy=policy,
        )
    except Exception as error:
        return CalibrationRecord(
            source_external_id=case.item.external_id,
            expected_pain=case.expected_pain,
            candidate_count=len(signals),
            error=f"{type(error).__name__}: {error}",
        )

    return CalibrationRecord(
        source_external_id=case.item.external_id,
        expected_pain=case.expected_pain,
        candidate_count=len(signals),
        decision=outcome.decision,
        assessment=assessment,
        verification=verification,
        policy_outcome=outcome,
    )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
