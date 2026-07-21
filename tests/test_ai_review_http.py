from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from painfinder.ai_review_http import AIReviewRunnerError, run_http_ai_reviews
from painfinder.benchmark_review import REVIEW_COLUMNS


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _packet(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "external_id": "item-1",
                "source_type": "post",
                "title": "Workflow",
                "body": "We manually update a spreadsheet every week.",
                "community": "smallbusiness",
                "canonical_url": "https://example.com/item-1",
                "expected_pain": "",
                "expected_categories": "",
                "expected_cluster": "",
                "review_status": "unreviewed",
                "reviewer": "",
                "reviewed_at": "",
                "rationale": "",
            }
        )


def _config(path: Path) -> None:
    profile = {
        "endpoint": "https://example.com/v1/chat/completions",
        "model": "review-model",
        "api_key_env": "REVIEW_API_KEY",
        "system_prompt": "Review independently.",
        "temperature": 0,
        "timeout_seconds": 5,
        "retries": 0,
    }
    path.write_text(
        json.dumps(
            {
                "reviewers": [
                    {**profile, "name": "a"},
                    {**profile, "name": "b"},
                    {**profile, "name": "c"},
                ]
            }
        ),
        encoding="utf-8",
    )


def _completion(external_id: str = "item-1") -> dict[str, Any]:
    decision = {
        "external_id": external_id,
        "expected_pain": True,
        "expected_categories": ["manual_work"],
        "expected_cluster": "manual-work",
        "confidence": 0.95,
        "rationale": "Repeated manual work is explicit.",
    }
    return {"choices": [{"message": {"content": json.dumps(decision)}}]}


def test_runner_writes_three_valid_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    output = tmp_path / "reviews"
    _packet(packet)
    _config(config)
    monkeypatch.setenv("REVIEW_API_KEY", "secret")
    monkeypatch.setattr(
        "painfinder.ai_review_http.urllib.request.urlopen",
        lambda request, timeout: _Response(_completion()),
    )

    paths = run_http_ai_reviews(packet, config, output_directory=output)

    assert len(paths) == 3
    for path in paths:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert rows[0]["external_id"] == "item-1"
        assert rows[0]["expected_categories"] == ["manual_work"]


def test_runner_requires_environment_key(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    _packet(packet)
    _config(config)

    with pytest.raises(AIReviewRunnerError, match="requires environment variable"):
        run_http_ai_reviews(packet, config, output_directory=tmp_path / "reviews")


def test_runner_rejects_wrong_evidence_id_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    output = tmp_path / "reviews"
    _packet(packet)
    _config(config)
    monkeypatch.setenv("REVIEW_API_KEY", "secret")
    monkeypatch.setattr(
        "painfinder.ai_review_http.urllib.request.urlopen",
        lambda request, timeout: _Response(_completion("wrong")),
    )

    with pytest.raises(AIReviewRunnerError, match="expected 'item-1'"):
        run_http_ai_reviews(packet, config, output_directory=output)

    assert not list(output.glob("reviewer-*.jsonl"))
    assert not list(output.glob("*.tmp"))


def test_config_requires_exactly_three_https_profiles(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    _packet(packet)
    config.write_text(
        json.dumps(
            {
                "reviewers": [
                    {
                        "name": "a",
                        "endpoint": "http://example.com",
                        "model": "x",
                        "api_key_env": "KEY",
                        "system_prompt": "Review.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(AIReviewRunnerError, match="Invalid reviewer configuration"):
        run_http_ai_reviews(packet, config, output_directory=tmp_path / "reviews")
