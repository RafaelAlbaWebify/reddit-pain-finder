from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.cli import app


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _resolved_row(
    external_id: str,
    *,
    expected_pain: str,
    categories: str = "",
    cluster: str = "",
) -> dict[str, str]:
    return {
        "external_id": external_id,
        "source_type": "post",
        "title": f"Workflow {external_id}",
        "body": f"Evidence for {external_id}",
        "community": "smallbusiness",
        "canonical_url": f"https://example.com/{external_id}",
        "expected_pain": expected_pain,
        "expected_categories": categories,
        "expected_cluster": cluster,
        "review_status": "resolved",
        "reviewer": "reviewer-one",
        "reviewed_at": "2026-07-20T18:00:00+02:00",
        "rationale": "Reviewed against the documented protocol.",
    }


def test_import_review_emits_valid_resolved_jsonl(tmp_path: Path) -> None:
    worksheet = tmp_path / "worksheet.csv"
    output = tmp_path / "nested" / "corpus.jsonl"
    _write_rows(
        worksheet,
        [
            _resolved_row(
                "pain-one",
                expected_pain="true",
                categories="manual_work; workaround",
                cluster="invoice-workflow",
            ),
            _resolved_row("neutral-one", expected_pain="false"),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "import-review",
            "--worksheet",
            str(worksheet),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "PASS: imported 2 resolved benchmark case(s)" in result.stdout
    payloads = [json.loads(line) for line in output.read_text().splitlines()]
    assert payloads[0]["expected_pain"] is True
    assert payloads[0]["expected_categories"] == ["manual_work", "workaround"]
    assert payloads[0]["expected_cluster"] == "invoice-workflow"
    assert payloads[1]["expected_pain"] is False
    assert payloads[1]["expected_categories"] == []
    assert payloads[1]["expected_cluster"] is None


def test_import_review_rejects_incomplete_rows_without_output(tmp_path: Path) -> None:
    worksheet = tmp_path / "worksheet.csv"
    output = tmp_path / "corpus.jsonl"
    _write_rows(
        worksheet,
        [
            {
                **_resolved_row(
                    "pain-one",
                    expected_pain="true",
                    categories="manual_work",
                    cluster="invoice-workflow",
                ),
                "review_status": "unreviewed",
            }
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "import-review",
            "--worksheet",
            str(worksheet),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Invalid review worksheet line 2" in result.stdout
    assert "review_status must be resolved" in result.stdout
    assert not output.exists()


def test_import_review_rejects_contradictory_negative_label(tmp_path: Path) -> None:
    worksheet = tmp_path / "worksheet.csv"
    output = tmp_path / "corpus.jsonl"
    _write_rows(
        worksheet,
        [
            _resolved_row(
                "neutral-one",
                expected_pain="false",
                categories="manual_work",
            )
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "import-review",
            "--worksheet",
            str(worksheet),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 2
    assert "negative pain cases must not define categories or a cluster" in result.stdout
    assert not output.exists()
