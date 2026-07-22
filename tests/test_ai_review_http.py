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


def _config(path: Path, *, local: bool = False) -> None:
    profile = {
        "endpoint": (
            "http://127.0.0.1:11434/v1/chat/completions"
            if local
            else "https://example.com/v1/chat/completions"
        ),
        "model": "review-model",
        "api_key_env": None if local else "REVIEW_API_KEY",
        "system_prompt": "Review independently.",
        "temperature": 0,
        "timeout_seconds": 5,
        "retries": 0,
        "reasoning_effort": "none" if local else None,
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


def test_loopback_http_requires_no_api_key_and_disables_reasoning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    output = tmp_path / "reviews"
    captured: list[Any] = []
    _packet(packet)
    _config(config, local=True)

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        captured.append(request)
        return _Response(_completion())

    monkeypatch.setattr("painfinder.ai_review_http.urllib.request.urlopen", fake_urlopen)

    run_http_ai_reviews(packet, config, output_directory=output)

    assert len(captured) == 3
    payload = json.loads(captured[0].data.decode("utf-8"))
    assert payload["reasoning_effort"] == "none"
    assert payload["response_format"]["type"] == "json_schema"
    assert "Authorization" not in dict(captured[0].header_items())


def test_runner_accepts_utf8_bom_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    output = tmp_path / "reviews"
    _packet(packet)
    _config(config, local=True)
    config.write_text(config.read_text(encoding="utf-8"), encoding="utf-8-sig")
    monkeypatch.setattr(
        "painfinder.ai_review_http.urllib.request.urlopen",
        lambda request, timeout: _Response(_completion()),
    )

    paths = run_http_ai_reviews(packet, config, output_directory=output)

    assert len(paths) == 3
    assert all(path.exists() for path in paths)


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


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.com/v1/chat/completions",
        "http://192.168.1.20:11434/v1/chat/completions",
    ],
)
def test_config_rejects_non_loopback_http(tmp_path: Path, endpoint: str) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    _packet(packet)
    profile = {
        "name": "a",
        "endpoint": endpoint,
        "model": "x",
        "system_prompt": "Review.",
    }
    config.write_text(json.dumps({"reviewers": [profile, profile, profile]}), encoding="utf-8")

    with pytest.raises(AIReviewRunnerError, match="Invalid reviewer configuration"):
        run_http_ai_reviews(packet, config, output_directory=tmp_path / "reviews")


def test_remote_https_requires_api_key_setting(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    config = tmp_path / "config.json"
    _packet(packet)
    profile = {
        "name": "remote",
        "endpoint": "https://example.com/v1/chat/completions",
        "model": "x",
        "system_prompt": "Review.",
    }
    config.write_text(json.dumps({"reviewers": [profile, profile, profile]}), encoding="utf-8")

    with pytest.raises(AIReviewRunnerError, match="requires api_key_env"):
        run_http_ai_reviews(packet, config, output_directory=tmp_path / "reviews")
