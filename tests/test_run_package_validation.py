from __future__ import annotations

import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.run_catalog import SQLiteRunCatalog
from painfinder.storage import SCHEMA_VERSION


def test_restore_rejects_null_run_name_before_creation(tmp_path: Path) -> None:
    package = tmp_path / "null-name.zip"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": "source-run",
            "name": None,
            "created_at": "2026-07-20T00:00:00+00:00",
            "status": "completed",
        },
        "source_items": [],
        "pain_signals": [],
        "clusters": [],
        "decisions": [],
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
    assert "name must be non-blank text" in result.stdout
    assert SQLiteRunCatalog(database).list_runs() == []


def test_restore_rejects_non_text_decision_values(tmp_path: Path) -> None:
    package = tmp_path / "numeric-decision.zip"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": "source-run",
            "name": "Numeric decision",
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
                "cluster_key": "cluster-one",
                "action": "accept",
                "previous_value": 1,
                "new_value": "accepted",
                "created_at": "2026-07-20T00:00:00+00:00",
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
    assert "optional decision values must be text or null" in result.stdout
    assert SQLiteRunCatalog(database).list_runs() == []
