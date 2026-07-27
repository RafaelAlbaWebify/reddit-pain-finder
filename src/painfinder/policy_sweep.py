from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationRecord
from painfinder.pain_policy import (
    FinalPolicyDecision,
    PainPolicy,
    PainPolicyInput,
    apply_pain_policy,
)


class PolicySweepRow(BaseModel):
    threshold: float
    accepted_count: int
    review_count: int
    rejected_count: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float


class PolicySweepReport(BaseModel):
    case_count: int
    replayable_count: int
    skipped_count: int
    rows: tuple[PolicySweepRow, ...]


def analyze_policy_thresholds(
    cases: list[BenchmarkCase],
    records: dict[str, CalibrationRecord],
    *,
    thresholds: tuple[float, ...] = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9),
) -> PolicySweepReport:
    rows: list[PolicySweepRow] = []
    replayable = [
        (case, records.get(case.item.external_id))
        for case in cases
        if records.get(case.item.external_id) is not None
        and records[case.item.external_id].assessment is not None
        and records[case.item.external_id].verification is not None
    ]

    for threshold in thresholds:
        accepted = 0
        review = 0
        rejected = 0
        true_positive = 0
        false_positive = 0
        false_negative = 0
        policy = PainPolicy(
            minimum_pain_confidence=threshold,
            minimum_assessor_evidence_confidence=threshold,
            minimum_verification_confidence=threshold,
            minimum_verifier_evidence_confidence=threshold,
        )
        for case, record in replayable:
            assert record is not None
            assert record.assessment is not None
            assert record.verification is not None
            outcome = apply_pain_policy(
                PainPolicyInput(
                    assessment=record.assessment,
                    verification=record.verification,
                ),
                policy=policy,
            )
            if outcome.decision is FinalPolicyDecision.ACCEPT:
                accepted += 1
                if case.expected_pain:
                    true_positive += 1
                else:
                    false_positive += 1
            elif outcome.decision is FinalPolicyDecision.REVIEW:
                review += 1
                if case.expected_pain:
                    false_negative += 1
            else:
                rejected += 1
                if case.expected_pain:
                    false_negative += 1

        rows.append(
            PolicySweepRow(
                threshold=threshold,
                accepted_count=accepted,
                review_count=review,
                rejected_count=rejected,
                true_positive=true_positive,
                false_positive=false_positive,
                false_negative=false_negative,
                precision=_ratio(true_positive, true_positive + false_positive),
                recall=_ratio(true_positive, true_positive + false_negative),
            )
        )

    return PolicySweepReport(
        case_count=len(cases),
        replayable_count=len(replayable),
        skipped_count=len(cases) - len(replayable),
        rows=tuple(rows),
    )


def write_policy_sweep_report(
    report: PolicySweepReport,
    *,
    json_output: Path,
    markdown_output: Path,
) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(report), encoding="utf-8")


def _markdown(report: PolicySweepReport) -> str:
    rows = "\n".join(
        f"| {row.threshold:.2f} | {row.accepted_count} | {row.review_count} | "
        f"{row.rejected_count} | {row.precision:.4f} | {row.recall:.4f} |"
        for row in report.rows
    )
    return f"""# Policy threshold sweep

Cases: {report.case_count}  
Replayable assessor/verifier records: {report.replayable_count}  
Skipped records: {report.skipped_count}

| Threshold | Accept | Review | Reject | Accept precision | Accept recall |
|---:|---:|---:|---:|---:|---:|
{rows}

This report is descriptive. It does not change the default policy or recommend a threshold automatically.
"""


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
