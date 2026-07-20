from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.domain import SourceItem, SourceType
from painfinder.storage import SQLiteResearchRepository


def test_runs_list_and_show_report_persisted_counts(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    run = repository.create_run("Inspection run", status="completed")
    repository.save_source_items(
        run.run_id,
        [
            SourceItem(
                external_id="one",
                source_type=SourceType.POST,
                title="Invoice workflow",
                body="We manually copy invoices into a spreadsheet.",
                canonical_url="https://example.com/one",
            )
        ],
    )

    runner = CliRunner()
    listed = runner.invoke(app, ["runs", "list", "--database", str(database)])
    shown = runner.invoke(
        app,
        [
            "runs",
            "show",
            "--run-id",
            run.run_id,
            "--database",
            str(database),
        ],
    )

    assert listed.exit_code == 0
    assert run.run_id in listed.stdout
    assert "Inspection run" in listed.stdout
    assert shown.exit_code == 0
    assert "Source items: 1" in shown.stdout
    assert "Pain signals: 0" in shown.stdout
    assert "Clusters: 0" in shown.stdout
    assert "Decisions: 0" in shown.stdout


def test_runs_list_handles_empty_database(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["runs", "list", "--database", str(tmp_path / "empty.db")],
    )

    assert result.exit_code == 0
    assert "No research runs found." in result.stdout


def test_runs_show_returns_concise_unknown_run_error(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "runs",
            "show",
            "--run-id",
            "missing",
            "--database",
            str(tmp_path / "research.db"),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Unknown run: missing" in result.stdout
