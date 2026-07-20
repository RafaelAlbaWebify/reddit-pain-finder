from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.run_catalog import SQLiteRunCatalog
from painfinder.storage import SCHEMA_VERSION, SQLiteResearchRepository

FIXTURE = Path(__file__).parent / "fixtures" / "imported_evidence.jsonl"


def test_discover_store_export_and_restore_run(tmp_path: Path) -> None:
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
    clusters = repository.list_clusters(run_id)
    assert clusters
    original_decision = repository.record_decision(
        run_id,
        clusters[0].key,
        "accept",
        previous_value="unreviewed",
        new_value="accepted",
    )

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

    restored_database = tmp_path / "restored.db"
    restore = CliRunner().invoke(
        app,
        [
            "restore-run",
            "--package",
            str(archive),
            "--database",
            str(restored_database),
        ],
    )

    assert restore.exit_code == 0
    restored_match = re.search(r"restored run ([0-9a-f-]+)", restore.stdout)
    assert restored_match is not None
    restored_run_id = restored_match.group(1)
    assert restored_run_id != run_id

    restored = SQLiteResearchRepository(restored_database)
    restored.initialize()
    restored_run = restored.get_run(restored_run_id)
    assert restored_run is not None
    assert restored_run.name == "Stored discovery"
    assert restored_run.status == "completed"
    assert len(restored.list_source_items(restored_run_id)) == 3
    assert restored.list_pain_signals(restored_run_id)
    assert restored.list_clusters(restored_run_id)
    restored_decisions = restored.list_decisions(restored_run_id)
    assert len(restored_decisions) == 1
    assert restored_decisions[0].action == "accept"
    assert restored_decisions[0].created_at == original_decision.created_at


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


def test_restore_invalid_package_returns_concise_error(tmp_path: Path) -> None:
    package = tmp_path / "bad.zip"
    package.write_text("not a zip", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "restore-run",
            "--package",
            str(package),
            "--database",
            str(tmp_path / "research.db"),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Invalid run package" in result.stdout


def test_malformed_decision_is_rejected_before_run_creation(tmp_path: Path) -> None:
    package = tmp_path / "bad-decision.zip"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": "source-run",
            "name": "Bad decision package",
            "created_at": "2026-07-20T00:00:00+00:00",
            "status": "completed",
        },
        "source_items": [],
        "pain_signals": [],
        "clusters": [],
        "decisions": [
            {
                "decision_id": "decision-one",
                "run_id": "source-run",
                "cluster_key": "missing-cluster",
                "action": "accept",
                "previous_value": "unreviewed",
                "new_value": "accepted",
                "created_at": "not-a-date",
            }
        ],
    }
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("run.json", json.dumps(payload))

    database = tmp_path / "restored.db"
    result = CliRunner().invoke(
        app,
        [
            "restore-run",
            "--package",
            str(package),
            "--database",
            str(database),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Invalid run package content" in result.stdout
    assert SQLiteRunCatalog(database).list_runs() == []
