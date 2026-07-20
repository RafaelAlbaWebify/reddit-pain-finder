from __future__ import annotations

import json
import sqlite3
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import HttpUrl

from painfinder.domain import PainCategory, PainSignal, SourceItem, SourceType
from painfinder.opportunities import OpportunityCluster

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StoredRun:
    run_id: str
    name: str
    created_at: datetime
    status: str


@dataclass(frozen=True)
class AnalystDecision:
    decision_id: str
    run_id: str
    cluster_key: str
    action: str
    previous_value: str | None
    new_value: str | None
    created_at: datetime


class SQLiteResearchRepository:
    """Durable local storage for research runs and derived evidence."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_items (
                    run_id TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    subreddit TEXT,
                    canonical_url TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    PRIMARY KEY (run_id, external_id),
                    UNIQUE (run_id, content_hash),
                    FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS pain_signals (
                    run_id TEXT NOT NULL,
                    source_external_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    PRIMARY KEY (
                        run_id,
                        source_external_id,
                        category,
                        excerpt
                    ),
                    FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS opportunity_clusters (
                    run_id TEXT NOT NULL,
                    cluster_key TEXT NOT NULL,
                    label TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    independent_communities INTEGER NOT NULL,
                    average_confidence REAL NOT NULL,
                    score REAL NOT NULL,
                    categories_json TEXT NOT NULL,
                    sample_excerpts_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, cluster_key),
                    FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analyst_decisions (
                    decision_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    cluster_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    previous_value TEXT,
                    new_value TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
                        ON DELETE CASCADE
                );
                """
            )
            version = connection.execute(
                "SELECT version FROM schema_version LIMIT 1"
            ).fetchone()
            if version is None:
                connection.execute(
                    "INSERT INTO schema_version(version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            elif int(version[0]) != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported database schema version {version[0]}; "
                    f"expected {SCHEMA_VERSION}"
                )

    def create_run(self, name: str, *, status: str = "created") -> StoredRun:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Run name must not be blank")
        run = StoredRun(
            run_id=str(uuid.uuid4()),
            name=clean_name,
            created_at=datetime.now(UTC),
            status=status,
        )
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO research_runs(run_id, name, created_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.name,
                    run.created_at.isoformat(),
                    run.status,
                ),
            )
        return run

    def get_run(self, run_id: str) -> StoredRun | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT run_id, name, created_at, status
                FROM research_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredRun(
            run_id=str(row[0]),
            name=str(row[1]),
            created_at=datetime.fromisoformat(str(row[2])),
            status=str(row[3]),
        )

    def set_run_status(self, run_id: str, status: str) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE research_runs SET status = ? WHERE run_id = ?",
                (status, run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown run: {run_id}")

    def save_source_items(self, run_id: str, items: list[SourceItem]) -> int:
        inserted = 0
        with self._connection() as connection:
            for item in items:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO source_items(
                        run_id,
                        external_id,
                        source_type,
                        title,
                        body,
                        subreddit,
                        canonical_url,
                        collected_at,
                        content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        item.external_id,
                        item.source_type.value,
                        item.title,
                        item.body,
                        item.subreddit,
                        str(item.canonical_url),
                        item.collected_at.isoformat(),
                        item.content_hash,
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def list_source_items(self, run_id: str) -> list[SourceItem]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT external_id, source_type, title, body, subreddit,
                       canonical_url, collected_at
                FROM source_items
                WHERE run_id = ?
                ORDER BY external_id
                """,
                (run_id,),
            ).fetchall()
        return [
            SourceItem(
                external_id=str(row[0]),
                source_type=SourceType(str(row[1])),
                title=str(row[2]),
                body=str(row[3]),
                subreddit=None if row[4] is None else str(row[4]),
                canonical_url=HttpUrl(str(row[5])),
                collected_at=datetime.fromisoformat(str(row[6])),
            )
            for row in rows
        ]

    def save_pain_signals(self, run_id: str, signals: list[PainSignal]) -> int:
        inserted = 0
        with self._connection() as connection:
            for signal in signals:
                cursor = connection.execute(
                    """
                    INSERT OR REPLACE INTO pain_signals(
                        run_id,
                        source_external_id,
                        category,
                        excerpt,
                        confidence,
                        reasons_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        signal.source_external_id,
                        signal.category.value,
                        signal.excerpt,
                        signal.confidence,
                        json.dumps(signal.reasons),
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def list_pain_signals(self, run_id: str) -> list[PainSignal]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT source_external_id, excerpt, category, confidence,
                       reasons_json
                FROM pain_signals
                WHERE run_id = ?
                ORDER BY source_external_id, category, excerpt
                """,
                (run_id,),
            ).fetchall()
        return [
            PainSignal(
                source_external_id=str(row[0]),
                excerpt=str(row[1]),
                category=PainCategory(str(row[2])),
                confidence=float(row[3]),
                reasons=list(json.loads(str(row[4]))),
            )
            for row in rows
        ]

    def save_clusters(
        self,
        run_id: str,
        clusters: list[OpportunityCluster],
    ) -> int:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM opportunity_clusters WHERE run_id = ?",
                (run_id,),
            )
            for cluster in clusters:
                connection.execute(
                    """
                    INSERT INTO opportunity_clusters(
                        run_id,
                        cluster_key,
                        label,
                        source_ids_json,
                        evidence_count,
                        independent_communities,
                        average_confidence,
                        score,
                        categories_json,
                        sample_excerpts_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        cluster.key,
                        cluster.label,
                        json.dumps(cluster.source_ids),
                        cluster.evidence_count,
                        cluster.independent_communities,
                        cluster.average_confidence,
                        cluster.score,
                        json.dumps(cluster.categories),
                        json.dumps(cluster.sample_excerpts),
                    ),
                )
        return len(clusters)

    def list_clusters(self, run_id: str) -> list[OpportunityCluster]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT cluster_key, label, source_ids_json, evidence_count,
                       independent_communities, average_confidence, score,
                       categories_json, sample_excerpts_json
                FROM opportunity_clusters
                WHERE run_id = ?
                ORDER BY score DESC, label
                """,
                (run_id,),
            ).fetchall()
        return [
            OpportunityCluster(
                key=str(row[0]),
                label=str(row[1]),
                source_ids=tuple(json.loads(str(row[2]))),
                evidence_count=int(row[3]),
                independent_communities=int(row[4]),
                average_confidence=float(row[5]),
                score=float(row[6]),
                categories=tuple(json.loads(str(row[7]))),
                sample_excerpts=tuple(json.loads(str(row[8]))),
            )
            for row in rows
        ]

    def record_decision(
        self,
        run_id: str,
        cluster_key: str,
        action: str,
        *,
        previous_value: str | None = None,
        new_value: str | None = None,
    ) -> AnalystDecision:
        decision = AnalystDecision(
            decision_id=str(uuid.uuid4()),
            run_id=run_id,
            cluster_key=cluster_key,
            action=action,
            previous_value=previous_value,
            new_value=new_value,
            created_at=datetime.now(UTC),
        )
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO analyst_decisions(
                    decision_id, run_id, cluster_key, action,
                    previous_value, new_value, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.run_id,
                    decision.cluster_key,
                    decision.action,
                    decision.previous_value,
                    decision.new_value,
                    decision.created_at.isoformat(),
                ),
            )
        return decision

    def list_decisions(self, run_id: str) -> list[AnalystDecision]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT decision_id, run_id, cluster_key, action,
                       previous_value, new_value, created_at
                FROM analyst_decisions
                WHERE run_id = ?
                ORDER BY created_at, decision_id
                """,
                (run_id,),
            ).fetchall()
        return [
            AnalystDecision(
                decision_id=str(row[0]),
                run_id=str(row[1]),
                cluster_key=str(row[2]),
                action=str(row[3]),
                previous_value=None if row[4] is None else str(row[4]),
                new_value=None if row[5] is None else str(row[5]),
                created_at=datetime.fromisoformat(str(row[6])),
            )
            for row in rows
        ]

    def export_run(self, run_id: str, output: Path) -> Path:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(f"Unknown run: {run_id}")

        payload = {
            "schema_version": SCHEMA_VERSION,
            "run": {
                "run_id": run.run_id,
                "name": run.name,
                "created_at": run.created_at.isoformat(),
                "status": run.status,
            },
            "source_items": [
                item.model_dump(mode="json")
                for item in self.list_source_items(run_id)
            ],
            "pain_signals": [
                signal.model_dump(mode="json")
                for signal in self.list_pain_signals(run_id)
            ],
            "clusters": [
                {
                    "key": cluster.key,
                    "label": cluster.label,
                    "source_ids": cluster.source_ids,
                    "evidence_count": cluster.evidence_count,
                    "independent_communities": cluster.independent_communities,
                    "average_confidence": cluster.average_confidence,
                    "score": cluster.score,
                    "categories": cluster.categories,
                    "sample_excerpts": cluster.sample_excerpts,
                }
                for cluster in self.list_clusters(run_id)
            ],
            "decisions": [
                {
                    "decision_id": decision.decision_id,
                    "run_id": decision.run_id,
                    "cluster_key": decision.cluster_key,
                    "action": decision.action,
                    "previous_value": decision.previous_value,
                    "new_value": decision.new_value,
                    "created_at": decision.created_at.isoformat(),
                }
                for decision in self.list_decisions(run_id)
            ],
        }

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("run.json", json.dumps(payload, indent=2))
        return output

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()
