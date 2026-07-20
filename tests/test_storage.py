from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from painfinder.domain import PainCategory, PainSignal, SourceItem, SourceType
from painfinder.opportunities import OpportunityCluster
from painfinder.storage import SCHEMA_VERSION, SQLiteResearchRepository


def _item(external_id: str, body: str) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.POST,
        title="Invoice workflow",
        body=body,
        subreddit="smallbusiness",
        canonical_url=f"https://example.com/{external_id}",
    )


def _signal(external_id: str) -> PainSignal:
    return PainSignal(
        source_external_id=external_id,
        excerpt="manual invoice reconciliation",
        category=PainCategory.MANUAL_WORK,
        confidence=0.8,
        reasons=["manual workflow"],
    )


def _cluster(*source_ids: str) -> OpportunityCluster:
    return OpportunityCluster(
        key="invoice-workflow",
        label="Invoice Workflow",
        source_ids=tuple(source_ids),
        evidence_count=len(source_ids),
        independent_communities=1,
        average_confidence=0.8,
        score=72.0,
        categories=("manual_work",),
        sample_excerpts=("manual invoice reconciliation",),
    )


def test_run_and_evidence_round_trip(tmp_path: Path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "research.db")
    repository.initialize()
    run = repository.create_run("Invoice research")
    items = [_item("one", "Manual invoice work"), _item("two", "Manual invoice work two")]

    assert repository.save_source_items(run.run_id, items) == 2
    assert repository.save_pain_signals(run.run_id, [_signal("one")]) == 1
    assert repository.save_clusters(run.run_id, [_cluster("one", "two")]) == 1

    loaded_run = repository.get_run(run.run_id)
    assert loaded_run is not None
    assert loaded_run.name == "Invoice research"
    assert repository.list_source_items(run.run_id) == sorted(
        items,
        key=lambda item: item.external_id,
    )
    assert repository.list_pain_signals(run.run_id) == [_signal("one")]
    assert repository.list_clusters(run.run_id) == [_cluster("one", "two")]


def test_repeated_import_is_idempotent_by_id_and_content_hash(tmp_path: Path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "research.db")
    repository.initialize()
    run = repository.create_run("Deduplication")
    first = _item("one", "Same evidence")
    duplicate_id = _item("one", "Different evidence")
    duplicate_content = _item("two", "Same evidence")

    assert repository.save_source_items(run.run_id, [first]) == 1
    assert repository.save_source_items(
        run.run_id,
        [first, duplicate_id, duplicate_content],
    ) == 0
    assert repository.list_source_items(run.run_id) == [first]


def test_decision_audit_trail_and_export(tmp_path: Path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "research.db")
    repository.initialize()
    run = repository.create_run("Review")
    repository.save_source_items(run.run_id, [_item("one", "Manual invoice work")])
    repository.save_clusters(run.run_id, [_cluster("one")])
    decision = repository.record_decision(
        run.run_id,
        "invoice-workflow",
        "accept",
        previous_value=None,
        new_value="accepted",
    )

    assert repository.list_decisions(run.run_id) == [decision]

    output = repository.export_run(run.run_id, tmp_path / "run.zip")
    with zipfile.ZipFile(output) as archive:
        payload = json.loads(archive.read("run.json"))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["run"]["run_id"] == run.run_id
    assert payload["source_items"][0]["external_id"] == "one"
    assert payload["clusters"][0]["key"] == "invoice-workflow"
    assert payload["decisions"][0]["action"] == "accept"


def test_schema_version_one_is_migrated_without_data_loss(
    tmp_path: Path,
) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    run = repository.create_run("Legacy run")

    index_names = {
        "idx_source_items_run_collected_at",
        "idx_pain_signals_run_category",
        "idx_opportunity_clusters_run_score",
        "idx_analyst_decisions_run_created_at",
    }

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE schema_version SET version = 1")
        for index_name in index_names:
            connection.execute(f"DROP INDEX {index_name}")

    repository.initialize()

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ).fetchone()
        migrated_indexes = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            ).fetchall()
        }

    assert version == (SCHEMA_VERSION,)
    assert index_names <= migrated_indexes
    assert repository.get_run(run.run_id) == run


def test_schema_version_mismatch_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version(version) VALUES (999)")

    repository = SQLiteResearchRepository(database)
    with pytest.raises(RuntimeError, match="Unsupported database schema version"):
        repository.initialize()


def test_blank_run_name_and_unknown_run_are_rejected(tmp_path: Path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "research.db")
    repository.initialize()

    with pytest.raises(ValueError, match="must not be blank"):
        repository.create_run("   ")
    with pytest.raises(KeyError, match="Unknown run"):
        repository.set_run_status("missing", "completed")
    with pytest.raises(KeyError, match="Unknown run"):
        repository.export_run("missing", tmp_path / "missing.zip")
