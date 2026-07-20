from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from painfinder.domain import PainSignal, SourceItem
from painfinder.opportunities import OpportunityCluster
from painfinder.storage import SCHEMA_VERSION, SQLiteResearchRepository, StoredRun


class RunPackageError(RuntimeError):
    pass


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
        source_items = [SourceItem.model_validate(item) for item in _list(payload, "source_items")]
        pain_signals = [PainSignal.model_validate(item) for item in _list(payload, "pain_signals")]
        clusters = [_cluster_from_mapping(item) for item in _list(payload, "clusters")]
    except (ValidationError, TypeError, ValueError, KeyError) as error:
        raise RunPackageError(f"Invalid run package content: {error}") from error

    repository.initialize()
    run = repository.create_run(name, status="restoring")
    repository.save_source_items(run.run_id, source_items)
    repository.save_pain_signals(run.run_id, pain_signals)
    repository.save_clusters(run.run_id, clusters)

    for raw_decision in _list(payload, "decisions"):
        decision = _ensure_mapping(raw_decision, "decision")
        repository.record_decision(
            run.run_id,
            _required_text(decision, "cluster_key"),
            _required_text(decision, "action"),
            previous_value=_optional_text(decision.get("previous_value")),
            new_value=_optional_text(decision.get("new_value")),
        )

    repository.set_run_status(run.run_id, status)
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
    value = str(payload[key]).strip()
    if not value:
        raise RunPackageError(f"Invalid run package: {key} must not be blank")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
