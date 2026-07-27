from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from painfinder.ai_review_http import ReviewerProfile
from painfinder.benchmark import load_benchmark
from painfinder.calibration_runner import (
    run_calibration,
    write_calibration_metrics,
)
from painfinder.pain_assessment_http import HTTPPainAssessor
from painfinder.pain_policy import PainPolicy
from painfinder.pain_verification_http import HTTPPainVerifier


CALIBRATION_CORPUS_NAME = "reddit-expanded-calibration-v1.jsonl"


class CalibrationCLIError(RuntimeError):
    pass


class CalibrationHTTPConfig(BaseModel):
    assessor: ReviewerProfile
    verifier: ReviewerProfile
    policy: PainPolicy = Field(default_factory=PainPolicy)


def load_calibration_config(path: Path) -> CalibrationHTTPConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return CalibrationHTTPConfig.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise CalibrationCLIError(
            f"Invalid calibration configuration: {error}"
        ) from error


def run_http_calibration(
    *,
    corpus_path: Path,
    config_path: Path,
    attempts_path: Path,
    metrics_path: Path,
) -> None:
    _require_calibration_corpus(corpus_path)
    config = load_calibration_config(config_path)
    cases = load_benchmark(corpus_path)
    if not cases:
        raise CalibrationCLIError("Calibration corpus is empty")

    metrics = run_calibration(
        cases,
        HTTPPainAssessor(config.assessor),
        HTTPPainVerifier(config.verifier),
        output_path=attempts_path,
        policy=config.policy,
    )
    write_calibration_metrics(metrics, metrics_path)


def _require_calibration_corpus(path: Path) -> None:
    if path.name != CALIBRATION_CORPUS_NAME:
        raise CalibrationCLIError(
            "This command is restricted to the frozen 140-case calibration "
            f"corpus: {CALIBRATION_CORPUS_NAME}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the resumable structured assessor/verifier pipeline against "
            "the frozen 140-case calibration corpus."
        )
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks") / CALIBRATION_CORPUS_NAME,
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--attempts",
        type=Path,
        default=Path("output") / "calibration-attempts.jsonl",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=Path("output") / "calibration-metrics.json",
    )
    arguments = parser.parse_args()

    try:
        run_http_calibration(
            corpus_path=arguments.corpus,
            config_path=arguments.config,
            attempts_path=arguments.attempts,
            metrics_path=arguments.metrics,
        )
    except (CalibrationCLIError, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    print(f"PASS: calibration attempts written to {arguments.attempts}")
    print(f"Metrics: {arguments.metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
