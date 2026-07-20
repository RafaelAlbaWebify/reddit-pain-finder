from __future__ import annotations

import re
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.storage import SQLiteResearchRepository

FIXTURE = Path(__file__).parent / "fixtures" / "imported_evidence.jsonl"


def test_discover_store_and_export_run(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    report = tmp_path / "report.html"
    result = CliRunner().invoke(
        app,
        [
            "discover-store",
            "--input",
            str(FIXTURE),
            "--name",
            "Stored discovery",
            "--database",
            str(database),
            "--output",
            str(report),
        ],
    )

    assert result.exit_code == 0
    assert database.exists()
    assert report.exists()
    match = re.search(r"stored run ([0-9a-f-]+)", result.stdout)
    assert match is not None
    run_id = match.group(1)

    repository = SQLiteResearchRepository(database)
    repository.initialize()
    run = repository.get_run(run_id)
    assert run is not None
    assert run.name == "Stored discovery"
    assert run.status == "completed"
    assert len(repository.list_source_items(run_id)) == 3
    assert repository.list_pain_signals(run_id)
    assert repository.list_clusters(run_id)

    archive = tmp_path / "run.zip"
    export = CliRunner().invoke(
        app,
        [
            "export-run",
            "--run-id",
            run_id,
            "--database",
            str(database),
            "--output",
            str(archive),
        ],
    )

    assert export.exit_code == 0
    assert archive.exists()
    with zipfile.ZipFile(archive) as package:
        assert package.namelist() == ["run.json"]


def test_export_unknown_run_returns_concise_error(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()

    result = CliRunner().invoke(
        app,
        [
            "export-run",
            "--run-id",
            "missing",
            "--database",
            str(database),
            "--output",
            str(tmp_path / "missing.zip"),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Unknown run: missing" in result.stdout
