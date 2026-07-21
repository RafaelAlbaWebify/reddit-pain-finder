from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import painfinder.benchmark_sampling as benchmark_sampling
from painfinder.cli import app
from painfinder.domain import SourceItem
from painfinder.storage import SQLiteResearchRepository


def _item(external_id: str, title: str, body: str) -> SourceItem:
    return SourceItem.model_validate(
        {
            "external_id": external_id,
            "source_type": "post",
            "title": title,
            "body": body,
            "subreddit": "testing",
            "canonical_url": f"https://example.com/{external_id}",
        }
    )


def test_multi_run_packet_id_collision_fails_without_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    first = repository.create_run("First", status="completed")
    second = repository.create_run("Second", status="completed")
    repository.save_source_items(first.run_id, [_item("one", "First", "First body")])
    repository.save_source_items(second.run_id, [_item("two", "Second", "Second body")])
    monkeypatch.setattr(
        benchmark_sampling,
        "_multi_run_packet_id",
        lambda run_id, external_id: "sample-collision",
    )
    reviewer_a = tmp_path / "reviewer-a.csv"
    reviewer_b = tmp_path / "reviewer-b.csv"
    manifest = tmp_path / "manifest.json"

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "prepare-blind-review",
            "--run-id",
            first.run_id,
            "--run-id",
            second.run_id,
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
    assert "Composite packet ID collision" in result.stdout
    assert not reviewer_a.exists()
    assert not reviewer_b.exists()
    assert not manifest.exists()
