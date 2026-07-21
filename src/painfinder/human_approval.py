from __future__ import annotations

import csv
from pathlib import Path

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.benchmark_review_import import ReviewWorksheetError, import_review_worksheet


class HumanApprovalError(RuntimeError):
    pass


APPROVAL_COLUMNS = (
    *REVIEW_COLUMNS,
    "agreement",
    "mean_confidence",
    "escalation_reasons",
    "reviewer_decisions",
    "human_decision",
    "human_reviewer",
    "human_reviewed_at",
    "human_rationale",
)


def promote_human_approvals(
    approval_queue: Path,
    *,
    resolved_worksheet_output: Path,
    gold_corpus_output: Path,
) -> tuple[int, int]:
    approved_rows, excluded_count = _load_approved_rows(approval_queue)
    resolved_worksheet_output.parent.mkdir(parents=True, exist_ok=True)
    gold_corpus_output.parent.mkdir(parents=True, exist_ok=True)
    temporary_worksheet = resolved_worksheet_output.with_suffix(
        resolved_worksheet_output.suffix + ".tmp"
    )
    temporary_corpus = gold_corpus_output.with_suffix(gold_corpus_output.suffix + ".tmp")

    temporary_worksheet.unlink(missing_ok=True)
    temporary_corpus.unlink(missing_ok=True)
    with temporary_worksheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(approved_rows)

    try:
        approved_count = import_review_worksheet(
            temporary_worksheet,
            temporary_corpus,
        )
    except ReviewWorksheetError as error:
        temporary_worksheet.unlink(missing_ok=True)
        temporary_corpus.unlink(missing_ok=True)
        raise HumanApprovalError(str(error)) from error

    temporary_worksheet.replace(resolved_worksheet_output)
    temporary_corpus.replace(gold_corpus_output)
    return approved_count, excluded_count


def _load_approved_rows(path: Path) -> tuple[list[dict[str, str]], int]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as error:
        raise HumanApprovalError(f"Could not read approval queue: {error}") from error

    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != APPROVAL_COLUMNS:
            raise HumanApprovalError("Approval queue has unexpected columns")
        rows = list(reader)

    approved: list[dict[str, str]] = []
    excluded_count = 0
    seen_ids: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        external_id = (row.get("external_id") or "").strip()
        if not external_id or external_id in seen_ids:
            raise HumanApprovalError(
                f"Invalid approval queue line {line_number}: IDs must be non-empty and unique"
            )
        seen_ids.add(external_id)

        decision = (row.get("human_decision") or "").strip().lower()
        if decision not in {"approve", "exclude"}:
            raise HumanApprovalError(
                f"Invalid approval queue line {line_number}: "
                "human_decision must be approve or exclude"
            )
        reviewer = (row.get("human_reviewer") or "").strip()
        reviewed_at = (row.get("human_reviewed_at") or "").strip()
        rationale = (row.get("human_rationale") or "").strip()
        if not reviewer or not reviewed_at or not rationale:
            raise HumanApprovalError(
                f"Invalid approval queue line {line_number}: "
                "human reviewer, timestamp and rationale are required"
            )

        if decision == "exclude":
            excluded_count += 1
            continue

        standard = {column: (row.get(column) or "") for column in REVIEW_COLUMNS}
        standard["review_status"] = "resolved"
        standard["reviewer"] = reviewer
        standard["reviewed_at"] = reviewed_at
        standard["rationale"] = rationale
        approved.append(standard)

    if not approved:
        raise HumanApprovalError("No human-approved rows are available for gold promotion")
    return approved, excluded_count
