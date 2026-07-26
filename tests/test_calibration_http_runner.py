from __future__ import annotations

import json
from pathlib import Path

import pytest

from painfinder.ai_review_http import ReviewerProfile
from painfinder.calibration_http_runner import (
    CalibrationRunnerError,
    load_calibration_http_config,
    run_http_calibration,
)
from painfinder.pain_assessment import PainAssessment, PainAssessmentRequest
from painfinder.pain_verification import PainVerification, PainVerificationRequest


class _UnusedAssessor:
    def assess(self, request: PainAssessmentRequest) -> PainAssessment:
        raise AssertionError("neutral candidate miss must not call assessor")


class _UnusedVerifier:
    def verify(self, request: PainVerificationRequest) -> PainVerification:
        raise AssertionError("neutral candidate miss must not call verifier")


def _profile(
    name: str,
    endpoint: str = "http://127.0.0.1:11434/v1/chat/completions",
) -> dict[str, object]:
    return {
        "name": name,
        "endpoint": endpoint,
        "model": "mock-model",
        "system_prompt": f"Act as the {name}.",
        "temperature": 0.0,
        "timeout_seconds": 1.0,
        "retries": 0,
    }


def test_command_runs_without_live_http_for_candidate_miss(tmp_path: Path) -> None:
    corpus = tmp_path / "calibration.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "item": {
                    "external_id": "neutral-1",
                    "source_type": "post",
                    "title": "",
                    "body": "Thanks for sharing.",
                    "subreddit": "smallbusiness",
                    "canonical_url": "https://reddit.com/neutral-1",
                },
                "expected_pain": False,
                "expected_categories": [],
                "expected_cluster": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "calibration-config.json"
    config.write_text(
        json.dumps(
            {
                "assessor": _profile("assessor"),
                "verifier": _profile("verifier"),
            }
        ),
        encoding="utf-8",
    )
    attempts = tmp_path / "attempts.jsonl"
    metrics_path = tmp_path / "metrics.json"

    metrics = run_http_calibration(
        corpus,
        config,
        attempts_output=attempts,
        metrics_output=metrics_path,
        assessor_factory=lambda profile: _UnusedAssessor(),
        verifier_factory=lambda profile: _UnusedVerifier(),
    )

    assert metrics.case_count == 1
    assert metrics.true_negative == 1
    assert metrics.attempted_count == 1
    assert metrics.resumed_count == 0
    assert attempts.exists()
    assert json.loads(metrics_path.read_text(encoding="utf-8"))["accuracy"] == 1.0


def test_non_loopback_profiles_require_api_key_environment(tmp_path: Path) -> None:
    config = tmp_path / "calibration-config.json"
    config.write_text(
        json.dumps(
            {
                "assessor": _profile(
                    "assessor",
                    "https://api.example.com/v1/chat/completions",
                ),
                "verifier": _profile("verifier"),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CalibrationRunnerError, match="assessor requires api_key_env"):
        load_calibration_http_config(config)


def test_configuration_preserves_separate_role_profiles(tmp_path: Path) -> None:
    config = tmp_path / "calibration-config.json"
    config.write_text(
        json.dumps(
            {
                "assessor": _profile("assessor"),
                "verifier": _profile("verifier"),
            }
        ),
        encoding="utf-8",
    )

    loaded = load_calibration_http_config(config)

    assert isinstance(loaded.assessor, ReviewerProfile)
    assert loaded.assessor.name == "assessor"
    assert loaded.verifier.name == "verifier"
