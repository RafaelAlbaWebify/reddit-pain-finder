from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import HttpUrl, ValidationError

from painfinder.domain import SourceItem, SourceType

REQUIRED_FIELDS = {"external_id", "body", "canonical_url"}


class ImportFormatError(RuntimeError):
    pass


def import_source_items(path: Path) -> list[SourceItem]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _import_jsonl(path)
    if suffix == ".csv":
        return _import_csv(path)
    raise ImportFormatError("Supported import formats are .jsonl and .csv")


def deduplicate_items(items: list[SourceItem]) -> list[SourceItem]:
    seen_external_ids: set[str] = set()
    seen_hashes: set[str] = set()
    unique: list[SourceItem] = []

    for item in items:
        if item.external_id in seen_external_ids:
            continue
        if item.content_hash in seen_hashes:
            continue
        seen_external_ids.add(item.external_id)
        seen_hashes.add(item.content_hash)
        unique.append(item)

    return unique


def _import_jsonl(path: Path) -> list[SourceItem]:
    items: list[SourceItem] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise ImportFormatError(
                f"Invalid JSON on line {line_number}: {error.msg}"
            ) from error
        if not isinstance(payload, Mapping):
            raise ImportFormatError(
                f"Invalid source item at line {line_number}: expected a JSON object"
            )
        items.append(_source_item_from_mapping(payload, line_number=line_number))
    return items


def _import_csv(path: Path) -> list[SourceItem]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ImportFormatError("CSV file has no header")
        normalized_headers = {header.strip() for header in reader.fieldnames if header}
        missing = sorted(REQUIRED_FIELDS - normalized_headers)
        if missing:
            raise ImportFormatError(
                "CSV file is missing required header(s): " + ", ".join(missing)
            )
        return [
            _source_item_from_mapping(row, line_number=index)
            for index, row in enumerate(reader, start=2)
        ]


def _source_item_from_mapping(
    payload: Mapping[str, Any],
    *,
    line_number: int,
) -> SourceItem:
    try:
        source_type = SourceType(_required_text(payload, "source_type", default="post"))
        return SourceItem(
            external_id=_required_text(payload, "external_id"),
            source_type=source_type,
            title=_optional_text(payload.get("title")) or "",
            body=_required_text(payload, "body"),
            subreddit=_optional_text(payload.get("subreddit")),
            canonical_url=HttpUrl(_required_text(payload, "canonical_url")),
        )
    except (KeyError, ValueError, ValidationError) as error:
        raise ImportFormatError(
            f"Invalid source item at line {line_number}: {error}"
        ) from error


def _required_text(
    payload: Mapping[str, Any],
    key: str,
    *,
    default: str | None = None,
) -> str:
    value = payload.get(key, default)
    if value is None:
        raise KeyError(key)
    text = str(value).strip()
    if not text:
        raise ValueError(f"{key} must not be blank")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
