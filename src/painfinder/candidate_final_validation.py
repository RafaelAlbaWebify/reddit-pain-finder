from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationRecord
from painfinder.candidate_audit import build_candidate_error_audit
from painfinder.candidate_audit_review import (
    AuditReviewDecision,
    CandidateAuditReviewRow,
)


class CandidateFinalValidation(BaseModel):
    case_count: int
    baseline_error_count: int
    current_error_count: int
    baseline_detector_gap_count: int
    recovered_detector_gap_ids: tuple[str, ...]
    remaining_detector_gap_ids: tuple[str, ...]
    baseline_false_positive_ids: tuple[str, ...]
    current_false_positive_ids: tuple[str, ...]
    removed_false_positive_ids: tuple[str, ...]
    new_false_positive_ids: tuple[str, ...]
    questionable_label_ids: tuple[str, ...]
    passed: bool


def build_candidate_final_validation(
    cases: list[BenchmarkCase],
    records: dict[str, CalibrationRecord],
    review_rows: tuple[CandidateAuditReviewRow, ...],
) -> CandidateFinalValidation:
    current_audit = build_candidate_error_audit(cases, records)
    current_false_negative_ids = {
        row.source_external_id
        for row in current_audit
        if row.error_type == "false_negative"
    }
    current_false_positive_ids = {
        row.source_external_id
        for row in current_audit
        if row.error_type == "false_positive"
    }

    detector_gap_ids = {
        row.audit.source_external_id
        for row in review_rows
        if row.review_decision is AuditReviewDecision.DETECTOR_GAP
    }
    baseline_false_positive_ids = {
        row.audit.source_external_id
        for row in review_rows
        if row.audit.error_type == "false_positive"
    }
    questionable_label_ids = {
        row.audit.source_external_id
        for row in review_rows
        if row.review_decision is AuditReviewDecision.QUESTIONABLE_LABEL
    }

    recovered = detector_gap_ids - current_false_negative_ids
    remaining = detector_gap_ids & current_false_negative_ids
    removed_false_positives = baseline_false_positive_ids - current_false_positive_ids
    new_false_positives = current_false_positive_ids - baseline_false_positive_ids

    return CandidateFinalValidation(
        case_count=len(cases),
        baseline_error_count=len(review_rows),
        current_error_count=len(current_audit),
        baseline_detector_gap_count=len(detector_gap_ids),
        recovered_detector_gap_ids=tuple(sorted(recovered)),
        remaining_detector_gap_ids=tuple(sorted(remaining)),
        baseline_false_positive_ids=tuple(sorted(baseline_false_positive_ids)),
        current_false_positive_ids=tuple(sorted(current_false_positive_ids)),
        removed_false_positive_ids=tuple(sorted(removed_false_positives)),
        new_false_positive_ids=tuple(sorted(new_false_positives)),
        questionable_label_ids=tuple(sorted(questionable_label_ids)),
        passed=bool(recovered) and not new_false_positives,
    )


def write_candidate_final_validation(
    validation: CandidateFinalValidation,
    *,
    json_output: Path,
    markdown_output: Path,
) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(validation.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(validation), encoding="utf-8")


def _markdown(validation: CandidateFinalValidation) -> str:
    status = "PASS" if validation.passed else "FAIL"
    recovered = ", ".join(validation.recovered_detector_gap_ids) or "none"
    remaining = ", ".join(validation.remaining_detector_gap_ids) or "none"
    new_false_positives = ", ".join(validation.new_false_positive_ids) or "none"
    return (
        "# Final candidate validation\n\n"
        f"**Status:** {status}\n\n"
        f"- Cases: {validation.case_count}\n"
        f"- Baseline errors: {validation.baseline_error_count}\n"
        f"- Current errors: {validation.current_error_count}\n"
        f"- Recovered detector gaps: {len(validation.recovered_detector_gap_ids)}\n"
        f"- Remaining detector gaps: {len(validation.remaining_detector_gap_ids)}\n"
        f"- New false positives: {len(validation.new_false_positive_ids)}\n\n"
        f"## Recovered detector gaps\n\n{recovered}\n\n"
        f"## Remaining detector gaps\n\n{remaining}\n\n"
        f"## New false positives\n\n{new_false_positives}\n"
    )
