from __future__ import annotations

import json
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from painfinder.domain import PainSignal, SourceItem
from painfinder.opportunities import OpportunityCluster
from painfinder.storage import SCHEMA_VERSION, SQLiteResearchRepository, StoredRun


class RunPackageError(RuntimeError):
    pass


@dataclass(frozen=True)
class _DecisionPayload:
    cluster_key: str
    action: str
    previous_value: str | None
    new_value: str | None
    created_at: datetime


def restore_run_package(
    repository: SQLiteResearchRepository,
    package: Path,
) -> StoredRun:
    """Restore one exported run as a new local run with a fresh identifier."""
    try:
        with zipfile.ZipFile(package) as archive:
            payload = json.loads(archive.read("run.json"))
    except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise RunPackageError(f"Invalid run package: {error}") from error

    if not isinstance(payload, dict):
        raise RunPackageError("Invalid run package: run.json must contain an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise RunPackageError(
            "Unsupported run package schema version: "
            f"{payload.get('schema_version')!r}"
        )

    run_payload = _mapping(payload, "run")
    name = _required_text(run_payload, "name")
    status = _required_text(run_payload, "status")

    try:
        source_items = [
            SourceItem.model_validate(item) for item in _list(payload, "source_items")
        ]
        pain_signals = [
            PainSignal.model_validate(item) for item in _list(payload, "pain_signals")
        ]
        clusters = [
            _cluster_from_mapping(item) for item in _list(payload, "clusters")
        ]
        decisions = [
            _decision_from_mapping(item) for item in _list(payload, "decisions")
        ]
    except (ValidationError, TypeError, ValueError, KeyError) as error:
        raise RunPackageError(f"Invalid run package content: {error}") from error

    repository.initialize()
    run = repository.create_run(name, status="restoring")
    try:
        repository.save_source_items(run.run_id, source_items)
        repository.save_pain_signals(run.run_id, pain_signals)
        repository.save_clusters(run.run_id, clusters)

        for decision_payload in decisions:
            restored_decision = repository.record_decision(
                run.run_id,
                decision_payload.cluster_key,
                decision_payload.action,
                previous_value=decision_payload.previous_value,
                new_value=decision_payload.new_value,
            )
            _set_decision_timestamp(
                repository.database_path,
                restored_decision.decision_id,
                decision_payload.created_at,
            )

        repository.set_run_status(run.run_id, status)
    except sqlite3.Error as error:
        _delete_run(repository.database_path, run.run_id)
        raise RunPackageError(f"Could not restore run package: {error}") from error

    restored = repository.get_run(run.run_id)
    if restored is None:
        raise RuntimeError("Restored run could not be reloaded")
    return restored


def _cluster_from_mapping(value: Any) -> OpportunityCluster:
    payload = _ensure_mapping(value, "cluster")
    return OpportunityCluster(
        key=_required_text(payload, "key"),
        label=_required_text(payload, "label"),
        source_ids=tuple(str(item) for item in _list(payload, "source_ids")),
        evidence_count=int(payload["evidence_count"]),
        independent_communities=int(payload["independent_communities"]),
        average_confidence=float(payload["average_confidence"]),
        score=float(payload["score"]),
        categories=tuple(str(item) for item in _list(payload, "categories")),
        sample_excerpts=tuple(
            str(item) for item in _list(payload, "sample_excerpts")
        ),
    )


def _decision_from_mapping(value: Any) -> _DecisionPayload:
    payload = _ensure_mapping(value, "decision")
    created_at = datetime.fromisoformat(_required_text(payload, "created_at"))
    return _DecisionPayload(
        cluster_key=_required_text(payload, "cluster_key"),
        action=_required_text(payload, "action"),
        previous_value=_optional_text(payload.get("previous_value")),
        new_value=_optional_text(payload.get("new_value")),
        created_at=created_at,
    )


def _set_decision_timestamp(
    database_path: Path,
    decision_id: str,
    created_at: datetime,
) -> None:
    connection = sqlite3.connect(database_path)
    try:
        with connection:
            cursor = connection.execute(
                "UPDATE analyst_decisions SET created_at = ? WHERE decision_id = ?",
                (created_at.isoformat(), decision_id),
            )
            if cursor.rowcount != 1:
                raise sqlite3.IntegrityError(
                    f"Decision could not be updated: {decision_id}"
                )
    finally:
        connection.close()


def _delete_run(database_path: Path, run_id: str) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.execute("DELETE FROM research_runs WHERE run_id = ?", (run_id,))
    finally:
        connection.close()


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return _ensure_mapping(payload.get(key), key)


def _ensure_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RunPackageError(f"Invalid run package: {label} must be an object")
    return value


def _list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise RunPackageError(f"Invalid run package: {key} must be a list")
    return value


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RunPackageError(f"Invalid run package: {key} must be non-blank text")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RunPackageError(
            "Invalid run package: optional decision values must be text or null"
        )
    return value if value else None
