from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.domain import SourceItem
from painfinder.storage import SQLiteResearchRepository


def _item(
    external_id: str,
    source_type: str,
    community: str,
    title: str,
    body: str,
) -> SourceItem:
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
            _item(
                "a-post",
                "post",
                "alpha",
                "Manual invoice work",
                "We copy invoice totals into spreadsheets every week.",
            ),
            _item(
                "a-comment",
                "comment",
                "alpha",
                "CRM import problem",
                "The CRM import fails during large uploads.",
            ),
            _item(
                "b-post",
                "post",
                "beta",
                "Support queue",
                "Customers wait days for support responses.",
            ),
            _item(
                "b-comment",
                "comment",
                "beta",
                "Manual invoice work",
                "We copy invoice totals into spreadsheets every single week.",
            ),
            _item(
                "c-post",
                "post",
                "gamma",
                "Neutral planning",
                "We discussed next quarter priorities and staffing.",
            ),
        ],
    )
    return database, run.run_id


def _outputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    return (
        tmp_path / "reviewer-a.csv",
        tmp_path / "reviewer-b.csv",
        tmp_path / "manifest.json",
    )


def test_prepare_blind_review_balances_and_writes_identical_packets(tmp_path: Path) -> None:
    database, run_id = _database(tmp_path)
    reviewer_a, reviewer_b, manifest = _outputs(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-blind-review",
            "--run-id",
            run_id,
            "--sample-size",
            "4",
            "--database",
            str(database),
            "--reviewer-a-output",
            str(reviewer_a),
            "--reviewer-b-output",
            str(reviewer_b),
            "--manifest-output",
            str(manifest),
            "--near-duplicate-threshold",
            "0.75",
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
    assert {row["external_id"] for row in rows} <= {
        "a-post",
        "a-comment",
        "b-post",
        "b-comment",
        "c-post",
    }
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["selected_count"] == 4
    assert payload["excluded_near_duplicates"] == 1


def test_prepare_blind_review_is_deterministic(tmp_path: Path) -> None:
    database, run_id = _database(tmp_path)
    outputs = [tmp_path / "first.csv", tmp_path / "second.csv"]
    for output in outputs:
        result = CliRunner().invoke(
            app,
            [
                "benchmark",
                "prepare-blind-review",
                "--run-id",
                run_id,
                "--sample-size",
                "3",
                "--database",
                str(database),
                "--reviewer-a-output",
                str(output),
                "--reviewer-b-output",
                str(tmp_path / f"copy-{output.name}"),
                "--manifest-output",
                str(tmp_path / f"{output.stem}.json"),
            ],
        )
        assert result.exit_code == 0
    assert outputs[0].read_bytes() == outputs[1].read_bytes()


def test_multi_run_sampling_preserves_provenance_and_distinct_ids(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    first = repository.create_run("First", status="completed")
    second = repository.create_run("Second", status="completed")
    repository.save_source_items(
        first.run_id,
        [_item("shared", "post", "alpha", "Invoice pain", "Manual invoice entry takes hours.")],
    )
    repository.save_source_items(
        second.run_id,
        [_item("shared", "comment", "beta", "CRM pain", "CRM imports fail every morning.")],
    )
    reviewer_a, reviewer_b, manifest = _outputs(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-blind-review",
            "--run-id",
            first.run_id,
            "--run-id",
            second.run_id,
            "--sample-size",
            "2",
            "--database",
            str(database),
            "--reviewer-a-output",
            str(reviewer_a),
            "--reviewer-b-output",
            str(reviewer_b),
            "--manifest-output",
            str(manifest),
        ],
    )
    assert result.exit_code == 0
    with reviewer_a.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    packet_ids = {row["external_id"] for row in rows}
    assert len(packet_ids) == 2
    assert all(packet_id.startswith("sample-") for packet_id in packet_ids)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["run_ids"] == [first.run_id, second.run_id]
    assert {entry["run_id"] for entry in payload["selected_items"]} == {
        first.run_id,
        second.run_id,
    }
    assert {entry["external_id"] for entry in payload["selected_items"]} == {"shared"}


def test_multi_run_sampling_deduplicates_exact_content_across_runs(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    first = repository.create_run("First", status="completed")
    second = repository.create_run("Second", status="completed")
    duplicate = _item("one", "post", "alpha", "Same title", "Exactly the same body.")
    repository.save_source_items(first.run_id, [duplicate])
    repository.save_source_items(
        second.run_id,
        [_item("two", "comment", "beta", "Same title", "Exactly the same body.")],
    )
    reviewer_a, reviewer_b, manifest = _outputs(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-blind-review",
            "--run-id",
            first.run_id,
            "--run-id",
            second.run_id,
            "--sample-size",
            "2",
            "--database",
            str(database),
            "--reviewer-a-output",
            str(reviewer_a),
            "--reviewer-b-output",
            str(reviewer_b),
            "--manifest-output",
            str(manifest),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["selected_count"] == 1
    assert payload["excluded_exact_duplicates"] == 1


def test_prepare_blind_review_rejects_unknown_run_without_outputs(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    reviewer_a, reviewer_b, manifest = _outputs(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-blind-review",
            "--run-id",
            "missing",
            "--database",
            str(database),
            "--reviewer-a-output",
            str(reviewer_a),
            "--reviewer-b-output",
            str(reviewer_b),
            "--manifest-output",
            str(manifest),
        ],
    )
    assert result.exit_code == 2
    assert "Unknown run" in result.stdout
    assert not reviewer_a.exists()
    assert not reviewer_b.exists()
    assert not manifest.exists()


def test_prepare_blind_review_rejects_incomplete_run_without_outputs(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    run = repository.create_run("Incomplete", status="created")
    repository.save_source_items(
        run.run_id,
        [_item("item", "post", "alpha", "Title", "Body with useful evidence.")],
    )
    reviewer_a, reviewer_b, manifest = _outputs(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-blind-review",
            "--run-id",
            run.run_id,
            "--database",
            str(database),
            "--reviewer-a-output",
            str(reviewer_a),
            "--reviewer-b-output",
            str(reviewer_b),
            "--manifest-output",
            str(manifest),
        ],
    )
    assert result.exit_code == 2
    assert "Run is not completed" in result.stdout
    assert not reviewer_a.exists()
    assert not reviewer_b.exists()
    assert not manifest.exists()
