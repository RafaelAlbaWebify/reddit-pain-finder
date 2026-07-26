from __future__ import annotations

import json
from pathlib import Path

import pytest

from painfinder.calibration_cli import (
    CALIBRATION_CORPUS_NAME,
    CalibrationCLIError,
    load_calibration_config,
    run_http_calibration,
)
from painfinder.calibration_runner import CalibrationMetrics


def _config(path: Path) -> None:
    profile = {
        "name": "local",
        "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
        "model": "test-model",
        "system_prompt": "Return structured output.",
        "temperature": 0,
        "timeout_seconds": 10,
        "retries": 0,
        "reasoning_effort": "none",
    }
    path.write_text(
        json.dumps(
            {
                "assessor": profile,
                "verifier": {**profile, "name": "verifier"},
                "policy": {
                    "minimum_pain_confidence": 0.7,
                    "minimum_assessor_evidence_confidence": 0.7,
                    "minimum_verification_confidence": 0.7,
                    "minimum_verifier_evidence_confidence": 0.7,
                },
            }
        ),
        encoding="utf-8",
    )


def test_config_loads_loopback_profiles_and_policy(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _config(path)

    config = load_calibration_config(path)

    assert config.assessor.name == "local"
    assert config.verifier.name == "verifier"
    assert config.policy.minimum_pain_confidence == 0.7


def test_config_accepts_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _config(path)
    path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")

    config = load_calibration_config(path)

    assert config.assessor.model == "test-model"


def test_command_refuses_any_non_calibration_corpus(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    _config(config)

    with pytest.raises(CalibrationCLIError, match="restricted"):
        run_http_calibration(
            corpus_path=tmp_path / "sealed-validation.jsonl",
            config_path=config,
            attempts_path=tmp_path / "attempts.jsonl",
            metrics_path=tmp_path / "metrics.json",
        )


def test_command_wires_runner_and_writes_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "config.json"
    corpus = tmp_path / CALIBRATION_CORPUS_NAME
    attempts = tmp_path / "attempts.jsonl"
    metrics_path = tmp_path / "metrics.json"
    _config(config)
    corpus.write_text("{}\n", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "painfinder.calibration_cli.load_benchmark",
        lambda path: [object()],
    )

    def fake_run_calibration(
        cases: list[object],
        assessor: object,
        verifier: object,
        *,
        output_path: Path,
        policy: object,
    ) -> CalibrationMetrics:
        captured["cases"] = cases
        captured["assessor"] = assessor
        captured["verifier"] = verifier
        captured["output_path"] = output_path
        captured["policy"] = policy
        return CalibrationMetrics(
            case_count=1,
            completed_count=1,
            error_count=0,
            accepted_count=0,
            rejected_count=1,
            review_count=0,
            true_positive=0,
            false_positive=0,
            true_negative=1,
            false_negative=0,
            precision=0.0,
            recall=0.0,
            accuracy=1.0,
            decision_counts={"reject": 1},
            error_ids=(),
        )

    monkeypatch.setattr(
        "painfinder.calibration_cli.run_calibration",
        fake_run_calibration,
    )

    run_http_calibration(
        corpus_path=corpus,
        config_path=config,
        attempts_path=attempts,
        metrics_path=metrics_path,
    )

    assert captured["output_path"] == attempts
    assert metrics_path.exists()
    assert json.loads(metrics_path.read_text(encoding="utf-8"))["accuracy"] == 1.0
