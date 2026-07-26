from __future__ import annotations

import json
import os
from collections import Counter
from enum import StrEnum
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, Field, model_validator

from painfinder.benchmark import BenchmarkCase
from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import PainCategory
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


class CalibrationStage(StrEnum):
    ASSESSOR = "assessor"
    VERIFIER = "verifier"
    POLICY = "policy"


class CalibrationFailure(BaseModel):
    stage: CalibrationStage
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)


class CalibrationRecord(BaseModel):
    source_external_id: str = Field(min_length=1)
    subreddit: str | None = None
    expected_pain: bool
    expected_categories: tuple[PainCategory, ...] = ()
    candidate_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    decision: FinalPolicyDecision | None = None
    assessment: PainAssessment | None = None
    verification: PainVerification | None = None
    policy_outcome: PolicyOutcome | None = None
    failure: CalibrationFailure | None = None

    @model_validator(mode="after")
    def validate_terminal_state(self) -> CalibrationRecord:
        if self.failure is None and self.decision is None:
            raise ValueError("successful record requires a decision")
        if self.failure is not None and self.decision is not None:
            raise ValueError("failed record cannot contain a decision")
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
    attempted_count: int
    resumed_count: int
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
    run_elapsed_ms: int = Field(ge=0)
    completed_duration_ms: int = Field(ge=0)
    decision_counts: dict[str, int]
    assessor_verdict_counts: dict[str, int]
    verifier_verdict_counts: dict[str, int]
    policy_reason_counts: dict[str, int]
    expected_category_counts: dict[str, int]
    assessed_category_counts: dict[str, int]
    subreddit_counts: dict[str, int]
    failure_stage_counts: dict[str, int]
    error_ids: tuple[str, ...]


def run_calibration(
    cases: list[BenchmarkCase],
    assessor: PainAssessor,
    verifier: PainVerifier,
    *,
    output_path: Path,
    policy: PainPolicy | None = None,
) -> CalibrationMetrics:
    run_started = perf_counter()
    latest = load_latest_records(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    attempted_count = 0
    resumed_count = 0

    for case in sorted(cases, key=lambda value: value.item.external_id):
        existing = latest.get(case.item.external_id)
        if existing is not None and existing.failure is None:
            resumed_count += 1
            continue

        attempted_count += 1
        record = _run_case(case, assessor, verifier, policy=policy)
        _append_record_atomically(output_path, record)
        latest[case.item.external_id] = record

    run_elapsed_ms = round((perf_counter() - run_started) * 1000)
    return evaluate_calibration(
        cases,
        latest,
        attempted_count=attempted_count,
        resumed_count=resumed_count,
        run_elapsed_ms=run_elapsed_ms,
    )


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
    *,
    attempted_count: int = 0,
    resumed_count: int = 0,
    run_elapsed_ms: int = 0,
) -> CalibrationMetrics:
    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0
    decision_counts: Counter[str] = Counter()
    assessor_counts: Counter[str] = Counter()
    verifier_counts: Counter[str] = Counter()
    policy_reason_counts: Counter[str] = Counter()
    expected_category_counts: Counter[str] = Counter()
    assessed_category_counts: Counter[str] = Counter()
    subreddit_counts: Counter[str] = Counter()
    failure_stage_counts: Counter[str] = Counter()
    error_ids: list[str] = []
    completed_duration_ms = 0

    for case in cases:
        subreddit_counts[case.item.subreddit or "<none>"] += 1
        expected_category_counts.update(
            category.value for category in case.expected_categories
        )
        record = records.get(case.item.external_id)
        if record is None:
            error_ids.append(case.item.external_id)
            failure_stage_counts["missing_record"] += 1
            decision_counts["error"] += 1
            continue
        if record.failure is not None:
            error_ids.append(case.item.external_id)
            failure_stage_counts[record.failure.stage.value] += 1
            decision_counts["error"] += 1
            continue

        completed_duration_ms += record.duration_ms
        assert record.decision is not None
        decision_counts[record.decision.value] += 1
        if record.assessment is not None:
            assessor_counts[record.assessment.verdict.value] += 1
            assessed_category_counts.update(
                category.value for category in record.assessment.categories
            )
        else:
            assessor_counts["not_run"] += 1
        if record.verification is not None:
            verifier_counts[record.verification.verdict.value] += 1
        else:
            verifier_counts["not_run"] += 1
        if record.policy_outcome is not None:
            policy_reason_counts.update(
                reason.value for reason in record.policy_outcome.reasons
            )
        else:
            policy_reason_counts["candidate_miss"] += 1

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
    return CalibrationMetrics(
        case_count=len(cases),
        completed_count=completed_count,
        error_count=len(error_ids),
        attempted_count=attempted_count,
        resumed_count=resumed_count,
        accepted_count=decision_counts[FinalPolicyDecision.ACCEPT.value],
        rejected_count=decision_counts[FinalPolicyDecision.REJECT.value],
        review_count=decision_counts[FinalPolicyDecision.REVIEW.value],
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        precision=_ratio(true_positive, true_positive + false_positive),
        recall=_ratio(true_positive, true_positive + false_negative),
        accuracy=_ratio(true_positive + true_negative, completed_count),
        run_elapsed_ms=run_elapsed_ms,
        completed_duration_ms=completed_duration_ms,
        decision_counts=dict(sorted(decision_counts.items())),
        assessor_verdict_counts=dict(sorted(assessor_counts.items())),
        verifier_verdict_counts=dict(sorted(verifier_counts.items())),
        policy_reason_counts=dict(sorted(policy_reason_counts.items())),
        expected_category_counts=dict(sorted(expected_category_counts.items())),
        assessed_category_counts=dict(sorted(assessed_category_counts.items())),
        subreddit_counts=dict(sorted(subreddit_counts.items())),
        failure_stage_counts=dict(sorted(failure_stage_counts.items())),
        error_ids=tuple(sorted(error_ids)),
    )


def write_calibration_metrics(metrics: CalibrationMetrics, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(metrics.model_dump(mode="json"), indent=2) + "\n"
    _replace_text_atomically(path, payload)


def _run_case(
    case: BenchmarkCase,
    assessor: PainAssessor,
    verifier: PainVerifier,
    *,
    policy: PainPolicy | None,
) -> CalibrationRecord:
    started = perf_counter()
    signals = generate_candidate_signals([case.item])
    if not signals:
        return CalibrationRecord(
            source_external_id=case.item.external_id,
            subreddit=case.item.subreddit,
            expected_pain=case.expected_pain,
            expected_categories=case.expected_categories,
            candidate_count=0,
            duration_ms=_elapsed_ms(started),
            decision=FinalPolicyDecision.REJECT,
        )

    assessment_request = PainAssessmentRequest(
        item=case.item,
        candidate_signals=tuple(signals),
    )
    try:
        assessment = assessor.assess(assessment_request)
    except Exception as error:
        return _failed_record(
            case, len(signals), started, CalibrationStage.ASSESSOR, error
        )

    try:
        verification = verifier.verify(
            PainVerificationRequest(
                assessment_request=assessment_request,
                assessment=assessment,
            )
        )
    except Exception as error:
        return _failed_record(
            case, len(signals), started, CalibrationStage.VERIFIER, error
        )

    try:
        outcome = apply_pain_policy(
            PainPolicyInput(
                assessment=assessment,
                verification=verification,
            ),
            policy=policy,
        )
    except Exception as error:
        return _failed_record(
            case, len(signals), started, CalibrationStage.POLICY, error
        )

    return CalibrationRecord(
        source_external_id=case.item.external_id,
        subreddit=case.item.subreddit,
        expected_pain=case.expected_pain,
        expected_categories=case.expected_categories,
        candidate_count=len(signals),
        duration_ms=_elapsed_ms(started),
        decision=outcome.decision,
        assessment=assessment,
        verification=verification,
        policy_outcome=outcome,
    )


def _failed_record(
    case: BenchmarkCase,
    candidate_count: int,
    started: float,
    stage: CalibrationStage,
    error: Exception,
) -> CalibrationRecord:
    return CalibrationRecord(
        source_external_id=case.item.external_id,
        subreddit=case.item.subreddit,
        expected_pain=case.expected_pain,
        expected_categories=case.expected_categories,
        candidate_count=candidate_count,
        duration_ms=_elapsed_ms(started),
        failure=CalibrationFailure(
            stage=stage,
            error_type=type(error).__name__,
            message=str(error) or type(error).__name__,
        ),
    )


def _append_record_atomically(path: Path, record: CalibrationRecord) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    _replace_text_atomically(path, existing + record.model_dump_json() + "\n")


def _replace_text_atomically(path: Path, content: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
