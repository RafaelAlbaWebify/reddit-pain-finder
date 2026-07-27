from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationRecord
from painfinder.candidate_detection import generate_candidate_signals


class CandidateAuditRow(BaseModel):
    source_external_id: str
    error_type: str
    expected_pain: bool
    expected_categories: tuple[str, ...]
    subreddit: str | None
    source_type: str
    title: str
    body: str
    canonical_url: str
    detector_ids: tuple[str, ...]
    signal_types: tuple[str, ...]
    signal_reasons: tuple[str, ...]
    latest_decision: str | None
    latest_failure_stage: str | None


def build_candidate_error_audit(
    cases: list[BenchmarkCase],
    records: dict[str, CalibrationRecord],
) -> tuple[CandidateAuditRow, ...]:
    signals = generate_candidate_signals([case.item for case in cases])
    signals_by_id: dict[str, list[object]] = {}
    for signal in signals:
        signals_by_id.setdefault(signal.source_external_id, []).append(signal)

    rows: list[CandidateAuditRow] = []
    for case in sorted(cases, key=lambda value: value.item.external_id):
        case_signals = signals_by_id.get(case.item.external_id, [])
        detected = bool(case_signals)
        if case.expected_pain and not detected:
            error_type = "false_negative"
        elif not case.expected_pain and detected:
            error_type = "false_positive"
        else:
            continue

        record = records.get(case.item.external_id)
        rows.append(
            CandidateAuditRow(
                source_external_id=case.item.external_id,
                error_type=error_type,
                expected_pain=case.expected_pain,
                expected_categories=tuple(
                    category.value for category in case.expected_categories
                ),
                subreddit=case.item.subreddit,
                source_type=case.item.source_type.value,
                title=case.item.title,
                body=case.item.body,
                canonical_url=case.item.canonical_url,
                detector_ids=tuple(
                    sorted({str(getattr(signal, "detector_id")) for signal in case_signals})
                ),
                signal_types=tuple(
                    sorted(
                        {
                            str(getattr(getattr(signal, "signal_type"), "value"))
                            for signal in case_signals
                        }
                    )
                ),
                signal_reasons=tuple(
                    sorted({str(getattr(signal, "reason")) for signal in case_signals})
                ),
                latest_decision=(
                    record.decision.value
                    if record is not None and record.decision is not None
                    else None
                ),
                latest_failure_stage=(
                    record.failure.stage.value
                    if record is not None and record.failure is not None
                    else None
                ),
            )
        )
    return tuple(rows)


def write_candidate_error_audit(
    rows: tuple[CandidateAuditRow, ...],
    *,
    jsonl_output: Path,
    markdown_output: Path,
) -> None:
    jsonl_output.parent.mkdir(parents=True, exist_ok=True)
    jsonl_output.write_text(
        "".join(row.model_dump_json() + "\n" for row in rows),
        encoding="utf-8",
    )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(rows), encoding="utf-8")


def _markdown(rows: tuple[CandidateAuditRow, ...]) -> str:
    sections = []
    for row in rows:
        payload = json.dumps(row.model_dump(mode="json"), indent=2, ensure_ascii=False)
        sections.append(
            f"## {row.error_type}: `{row.source_external_id}`\n\n"
            f"```json\n{payload}\n```"
        )
    return "# Candidate error audit\n\n" + ("\n\n".join(sections) or "No errors.\n")
