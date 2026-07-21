from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.human_approval import APPROVAL_COLUMNS


def _row(external_id: str, decision: str) -> dict[str, str]:
    return {
        "external_id": external_id,
        "source_type": "post",
        "title": "Manual invoice entry",
        "body": "We copy invoice totals by hand every Friday.",
        "community": "smallbusiness",
        "canonical_url": f"https://example.com/{external_id}",
        "expected_pain": "true",
        "expected_categories": "manual_work",
        "expected_cluster": "invoice-entry",
        "review_status": "provisional",
        "reviewer": "ai_consensus",
        "reviewed_at": "",
        "rationale": "AI consensus rationale",
        "agreement": "majority",
        "mean_confidence": "0.900",
        "escalation_reasons": "reviewer_disagreement",
        "reviewer_decisions": "[]",
        "human_decision": decision,
        "human_reviewer": "rafael",
        "human_reviewed_at": "2026-07-21T12:00:00+02:00",
        "human_rationale": "I checked the source evidence and approve this label.",
    }


def _queue(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=APPROVAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _invoke(tmp_path: Path, queue: Path):
    worksheet = tmp_path / "resolved.csv"
    corpus = tmp_path / "gold.jsonl"
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "promote-human-approvals",
            "--approval-queue",
            str(queue),
            "--resolved-worksheet-output",
            str(worksheet),
            "--gold-corpus-output",
            str(corpus),
        ],
    )
    return result, worksheet, corpus


def test_only_explicitly_approved_rows_enter_gold(tmp_path: Path) -> None:
    queue = tmp_path / "queue.csv"
    _queue(queue, [_row("approved", "approve"), _row("excluded", "exclude")])

    result, worksheet, corpus = _invoke(tmp_path, queue)

    assert result.exit_code == 0
    assert "promoted 1" in result.stdout
    assert "excluded=1" in result.stdout
    cases = [
        json.loads(line)
        for line in corpus.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [case["item"]["external_id"] for case in cases] == ["approved"]
    with worksheet.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["review_status"] == "resolved"
    assert rows[0]["reviewer"] == "rafael"


def test_ai_only_row_cannot_enter_gold(tmp_path: Path) -> None:
    queue = tmp_path / "queue.csv"
    row = _row("one", "")
    row["human_reviewer"] = ""
    row["human_reviewed_at"] = ""
    row["human_rationale"] = ""
    _queue(queue, [row])

    result, worksheet, corpus = _invoke(tmp_path, queue)

    assert result.exit_code == 2
    assert "human_decision" in result.stdout
    assert not worksheet.exists()
    assert not corpus.exists()


def test_invalid_human_metadata_cannot_enter_gold(tmp_path: Path) -> None:
    queue = tmp_path / "queue.csv"
    row = _row("one", "approve")
    row["human_reviewed_at"] = "not-a-date"
    _queue(queue, [row])

    result, worksheet, corpus = _invoke(tmp_path, queue)

    assert result.exit_code == 2
    assert "ISO 8601" in result.stdout
    assert not worksheet.exists()
    assert not corpus.exists()


def test_no_approved_rows_is_rejected(tmp_path: Path) -> None:
    queue = tmp_path / "queue.csv"
    _queue(queue, [_row("excluded", "exclude")])

    result, worksheet, corpus = _invoke(tmp_path, queue)

    assert result.exit_code == 2
    assert "No human-approved rows" in result.stdout
    assert not worksheet.exists()
    assert not corpus.exists()
