from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from painfinder.storage import SQLiteResearchRepository, StoredRun


@dataclass(frozen=True)
class RunSummary:
    run: StoredRun
    source_items: int
    pain_signals: int
    clusters: int
    decisions: int


class SQLiteRunCatalog:
    """Read-only run discovery and summary access for the local SQLite store."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.repository = SQLiteResearchRepository(database_path)

    def initialize(self) -> None:
        self.repository.initialize()

    def list_runs(self) -> list[StoredRun]:
        self.initialize()
        connection = sqlite3.connect(self.database_path)
        try:
            rows = connection.execute(
                """
                SELECT run_id, name, created_at, status
                FROM research_runs
                ORDER BY created_at DESC, run_id
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            StoredRun(
                run_id=str(row[0]),
                name=str(row[1]),
                created_at=datetime.fromisoformat(str(row[2])),
                status=str(row[3]),
            )
            for row in rows
        ]

    def get_summary(self, run_id: str) -> RunSummary:
        self.initialize()
        run = self.repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Unknown run: {run_id}")
        return RunSummary(
            run=run,
            source_items=len(self.repository.list_source_items(run_id)),
            pain_signals=len(self.repository.list_pain_signals(run_id)),
            clusters=len(self.repository.list_clusters(run_id)),
            decisions=len(self.repository.list_decisions(run_id)),
        )
