from __future__ import annotations

import csv
from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.domain import SourceItem, SourceType
from painfinder.storage import SQLiteResearchRepository


def _item(external_id: str, *, community: str | None) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.POST,
        title=f"Workflow {external_id}",
        body=f"Evidence body for {external_id}",
        subreddit=community,
        canonical_url=f"https://example.com/{external_id}",
    )


def test_prepare_review_exports_unlabeled_persisted_evidence(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    run = repository.create_run("Review candidates", status="completed")
    repository.save_source_items(
        run.run_id,
        [
            _item("two", community=None),
            _item("one", community="smallbusiness"),
        ],
    )

    output = tmp_path / "nested" / "worksheet.csv"
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-review",
            "--run-id",
            run.run_id,
            "--database",
            str(database),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "PASS: prepared 2 evidence item(s)" in result.stdout
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["external_id"] for row in rows] == ["one", "two"]
    assert rows[0]["community"] == "smallbusiness"
    assert rows[1]["community"] == ""
    assert rows[0]["canonical_url"] == "https://example.com/one"
    for row in rows:
        assert row["expected_pain"] == ""
        assert row["expected_categories"] == ""
        assert row["expected_cluster"] == ""
        assert row["review_status"] == "unreviewed"
        assert row["reviewer"] == ""
        assert row["reviewed_at"] == ""
        assert row["rationale"] == ""


def test_prepare_review_unknown_run_returns_concise_error(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-review",
            "--run-id",
            "missing",
            "--database",
            str(database),
            "--output",
            str(tmp_path / "worksheet.csv"),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Unknown run: missing" in result.stdout
