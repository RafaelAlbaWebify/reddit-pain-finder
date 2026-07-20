from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.domain import PainCategory, SourceItem, SourceType


class ReviewWorksheetError(RuntimeError):
    pass


def import_review_worksheet(input_path: Path, output: Path) -> int:
    cases = _load_resolved_rows(input_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = "\n".join(json.dumps(case, ensure_ascii=False) for case in cases)
    output.write_text(f"{serialized}\n" if serialized else "", encoding="utf-8")
    return len(cases)


def _load_resolved_rows(path: Path) -> list[dict[str, object]]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as error:
        raise ReviewWorksheetError(f"Could not read worksheet: {error}") from error

    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REVIEW_COLUMNS:
            raise ReviewWorksheetError(
                "Invalid worksheet headers; expected: " + ", ".join(REVIEW_COLUMNS)
            )

        cases: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            cases.append(_case_from_row(row, line_number, seen_ids))
    return cases


def _case_from_row(
    row: dict[str, str | None],
    line_number: int,
    seen_ids: set[str],
) -> dict[str, object]:
    def text(column: str) -> str:
        return (row.get(column) or "").strip()

    external_id = text("external_id")
    if not external_id:
        raise _line_error(line_number, "external_id must not be blank")
    if external_id in seen_ids:
        raise _line_error(line_number, f"duplicate external_id: {external_id}")
    seen_ids.add(external_id)

    if text("review_status").lower() != "resolved":
        raise _line_error(line_number, "review_status must be resolved")
    if not text("reviewer"):
        raise _line_error(line_number, "reviewer must not be blank")
    if not text("rationale"):
        raise _line_error(line_number, "rationale must not be blank")
    _validate_reviewed_at(text("reviewed_at"), line_number)

    expected_pain = _parse_bool(text("expected_pain"), line_number)
    categories = _parse_categories(text("expected_categories"), line_number)
    expected_cluster = text("expected_cluster") or None

    if expected_pain:
        if not categories:
            raise _line_error(
                line_number,
                "positive pain cases require at least one expected category",
            )
        if expected_cluster is None:
            raise _line_error(
                line_number,
                "positive pain cases require an expected cluster",
            )
    elif categories or expected_cluster is not None:
        raise _line_error(
            line_number,
            "negative pain cases must not define categories or a cluster",
        )

    try:
        item = SourceItem(
            external_id=external_id,
            source_type=SourceType(text("source_type")),
            title=text("title"),
            body=row.get("body") or "",
            subreddit=text("community") or None,
            canonical_url=text("canonical_url"),
        )
    except (ValueError, ValidationError) as error:
        raise _line_error(line_number, f"invalid source item: {error}") from error

    return {
        "item": {
            "external_id": item.external_id,
            "source_type": item.source_type.value,
            "title": item.title,
            "body": item.body,
            "subreddit": item.subreddit,
            "canonical_url": str(item.canonical_url),
        },
        "expected_pain": expected_pain,
        "expected_categories": [category.value for category in categories],
        "expected_cluster": expected_cluster,
    }


def _parse_bool(value: str, line_number: int) -> bool:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise _line_error(line_number, "expected_pain must be true or false")


def _parse_categories(value: str, line_number: int) -> tuple[PainCategory, ...]:
    if not value:
        return ()
    raw_categories = [
        part.strip()
        for part in value.replace(";", ",").split(",")
        if part.strip()
    ]
    categories: list[PainCategory] = []
    for raw_category in raw_categories:
        try:
            category = PainCategory(raw_category)
        except ValueError as error:
            raise _line_error(
                line_number,
                f"unknown expected category: {raw_category}",
            ) from error
        if category not in categories:
            categories.append(category)
    return tuple(categories)


def _validate_reviewed_at(value: str, line_number: int) -> None:
    if not value:
        raise _line_error(line_number, "reviewed_at must not be blank")
    try:
        reviewed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _line_error(line_number, "reviewed_at must be ISO 8601") from error
    if reviewed_at.tzinfo is None:
        raise _line_error(line_number, "reviewed_at must include a timezone")


def _line_error(line_number: int, message: str) -> ReviewWorksheetError:
    return ReviewWorksheetError(f"Invalid review worksheet line {line_number}: {message}")
