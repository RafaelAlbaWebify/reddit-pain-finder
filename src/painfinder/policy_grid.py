from __future__ import annotations

import json
from itertools import product
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


class PolicyGridRow(BaseModel):
    pain_threshold: float
    evidence_threshold: float
    accepted_count: int
    review_count: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    accepted_false_positive_ids: tuple[str, ...]
    pareto_efficient: bool = False


class PolicyGridReport(BaseModel):
    case_count: int
    replayable_count: int
    skipped_count: int
    rows: tuple[PolicyGridRow, ...]
    pareto_rows: tuple[PolicyGridRow, ...]


def analyze_policy_grid(
    cases: list[BenchmarkCase],
    records: dict[str, CalibrationRecord],
    *,
    pain_thresholds: tuple[float, ...] = (0.5, 0.6, 0.7, 0.75, 0.8),
    evidence_thresholds: tuple[float, ...] = (0.5, 0.6, 0.7, 0.75, 0.8),
) -> PolicyGridReport:
    replayable = [
        (case, records.get(case.item.external_id))
        for case in cases
        if records.get(case.item.external_id) is not None
        and records[case.item.external_id].assessment is not None
        and records[case.item.external_id].verification is not None
    ]
    provisional: list[PolicyGridRow] = []
    for pain_threshold, evidence_threshold in product(
        pain_thresholds,
        evidence_thresholds,
    ):
        accepted = 0
        review = 0
        true_positive = 0
        false_positive = 0
        false_negative = 0
        false_ids: list[str] = []
        policy = PainPolicy(
            minimum_pain_confidence=pain_threshold,
            minimum_assessor_evidence_confidence=evidence_threshold,
            minimum_verification_confidence=pain_threshold,
            minimum_verifier_evidence_confidence=evidence_threshold,
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
                    false_ids.append(case.item.external_id)
            else:
                review += 1
                if case.expected_pain:
                    false_negative += 1
        provisional.append(
            PolicyGridRow(
                pain_threshold=pain_threshold,
                evidence_threshold=evidence_threshold,
                accepted_count=accepted,
                review_count=review,
                true_positive=true_positive,
                false_positive=false_positive,
                false_negative=false_negative,
                precision=_ratio(true_positive, true_positive + false_positive),
                recall=_ratio(true_positive, true_positive + false_negative),
                accepted_false_positive_ids=tuple(sorted(false_ids)),
            )
        )

    rows = tuple(_mark_pareto(provisional))
    pareto_rows = tuple(row for row in rows if row.pareto_efficient)
    return PolicyGridReport(
        case_count=len(cases),
        replayable_count=len(replayable),
        skipped_count=len(cases) - len(replayable),
        rows=rows,
        pareto_rows=pareto_rows,
    )


def write_policy_grid_report(
    report: PolicyGridReport,
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


def _mark_pareto(rows: list[PolicyGridRow]) -> list[PolicyGridRow]:
    marked: list[PolicyGridRow] = []
    for row in rows:
        dominated = any(
            other is not row
            and other.false_positive <= row.false_positive
            and other.true_positive >= row.true_positive
            and (
                other.false_positive < row.false_positive
                or other.true_positive > row.true_positive
            )
            for other in rows
        )
        marked.append(row.model_copy(update={"pareto_efficient": not dominated}))
    return marked


def _markdown(report: PolicyGridReport) -> str:
    rows = "\n".join(
        f"| {row.pain_threshold:.2f} | {row.evidence_threshold:.2f} | "
        f"{row.accepted_count} | {row.true_positive} | {row.false_positive} | "
        f"{row.precision:.4f} | {row.recall:.4f} |"
        for row in report.pareto_rows
    )
    return f"""# Compound policy grid

Cases: {report.case_count}  
Replayable assessor/verifier records: {report.replayable_count}  
Skipped records: {report.skipped_count}

## Pareto-efficient configurations

| Pain threshold | Evidence threshold | Accept | TP | FP | Precision | Recall |
|---:|---:|---:|---:|---:|---:|---:|
{rows}

This report is descriptive. It does not change production policy defaults.
"""


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
