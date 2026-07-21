from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.domain import SourceItem
from painfinder.storage import SQLiteResearchRepository


def _item(external_id: str, source_type: str, community: str, title: str, body: str) -> SourceItem:
    return SourceItem.model_validate(
        {
            "external_id": external_id,
            "source_type": source_type,
            "title": title,
            "body": body,
            "subreddit": community,
            "canonical_url": f"https://example.com/{external_id}",
        }
    )


def _database(tmp_path: Path) -> tuple[Path, str]:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    run = repository.create_run("Sampling test", status="completed")
    repository.save_source_items(
        run.run_id,
        [
            _item("a-post", "post", "alpha", "Manual invoice work", "We copy invoice totals into spreadsheets every week."),
            _item("a-comment", "comment", "alpha", "CRM import problem", "The CRM import fails during large uploads."),
            _item("b-post", "post", "beta", "Support queue", "Customers wait days for support responses."),
            _item("b-comment", "comment", "beta", "Manual invoice work follow-up", "We copy invoice totals into spreadsheets every single week."),
            _item("c-post", "post", "gamma", "Neutral planning", "We discussed next quarter priorities and staffing."),
        ],
    )
    return database, run.run_id


def test_prepare_blind_review_balances_and_writes_identical_packets(tmp_path: Path) -> None:
    database, run_id = _database(tmp_path)
    reviewer_a = tmp_path / "reviewer-a.csv"
    reviewer_b = tmp_path / "reviewer-b.csv"
    manifest = tmp_path / "manifest.json"
    result = CliRunner().invoke(
        app,
        [
            "benchmark", "prepare-blind-review", "--run-id", run_id,
            "--sample-size", "4", "--database", str(database),
            "--reviewer-a-output", str(reviewer_a),
            "--reviewer-b-output", str(reviewer_b),
            "--manifest-output", str(manifest),
            "--near-duplicate-threshold", "0.75",
        ],
    )
    assert result.exit_code == 0
    assert reviewer_a.read_bytes() == reviewer_b.read_bytes()
    with reviewer_a.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert {row["community"] for row in rows} == {"alpha", "beta", "gamma"}
    assert {row["source_type"] for row in rows} == {"post", "comment"}
    assert all(row["review_status"] == "unreviewed" for row in rows)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["selected_count"] == 4
    assert payload["excluded_near_duplicates"] == 1


def test_prepare_blind_review_is_deterministic(tmp_path: Path) -> None:
    database, run_id = _database(tmp_path)
    outputs = [tmp_path / "first.csv", tmp_path / "second.csv"]
    for output in outputs:
        result = CliRunner().invoke(
            app,
            [
                "benchmark", "prepare-blind-review", "--run-id", run_id,
                "--sample-size", "3", "--database", str(database),
                "--reviewer-a-output", str(output),
                "--reviewer-b-output", str(tmp_path / f"copy-{output.name}"),
                "--manifest-output", str(tmp_path / f"{output.stem}.json"),
            ],
        )
        assert result.exit_code == 0
    assert outputs[0].read_bytes() == outputs[1].read_bytes()


def test_prepare_blind_review_rejects_unknown_run(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    result = CliRunner().invoke(
        app,
        ["benchmark", "prepare-blind-review", "--run-id", "missing", "--database", str(database)],
    )
    assert result.exit_code == 2
    assert "Unknown run" in result.stdout
