from __future__ import annotations

import argparse
import json
import urllib.parse
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ValidationError

from painfinder.ai_review_http import ReviewerProfile
from painfinder.benchmark import BenchmarkFormatError, load_benchmark
from painfinder.calibration_runner import (
    CalibrationMetrics,
    run_calibration,
    write_calibration_metrics,
)
from painfinder.pain_assessment import PainAssessor
from painfinder.pain_assessment_http import HTTPPainAssessor
from painfinder.pain_verification import PainVerifier
from painfinder.pain_verification_http import HTTPPainVerifier


class CalibrationRunnerError(RuntimeError):
    pass


class CalibrationHTTPConfig(BaseModel):
    assessor: ReviewerProfile
    verifier: ReviewerProfile


AssessorFactory = Callable[[ReviewerProfile], PainAssessor]
VerifierFactory = Callable[[ReviewerProfile], PainVerifier]


def load_calibration_http_config(path: Path) -> CalibrationHTTPConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        config = CalibrationHTTPConfig.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise CalibrationRunnerError(f"Invalid calibration configuration: {error}") from error

    for role, profile in (("assessor", config.assessor), ("verifier", config.verifier)):
        hostname = urllib.parse.urlparse(profile.endpoint).hostname
        is_loopback = hostname in {"localhost", "127.0.0.1", "::1"}
        if not is_loopback and profile.api_key_env is None:
            raise CalibrationRunnerError(
                f"Calibration {role} requires api_key_env for a non-loopback endpoint"
            )
    return config


def run_http_calibration(
    corpus: Path,
    config_path: Path,
    *,
    attempts_output: Path,
    metrics_output: Path,
    only_id: str | None = None,
    assessor_factory: AssessorFactory = HTTPPainAssessor,
    verifier_factory: VerifierFactory = HTTPPainVerifier,
) -> CalibrationMetrics:
    try:
        cases = load_benchmark(corpus)
    except BenchmarkFormatError as error:
        raise CalibrationRunnerError(f"Invalid calibration corpus: {error}") from error

    if only_id is not None:
        cases = [case for case in cases if case.item.external_id == only_id]
        if not cases:
            raise CalibrationRunnerError(f"Calibration case not found: {only_id}")

    config = load_calibration_http_config(config_path)
    metrics = run_calibration(
        cases,
        assessor_factory(config.assessor),
        verifier_factory(config.verifier),
        output_path=attempts_output,
    )
    write_calibration_metrics(metrics, metrics_output)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run resumable assessor/verifier calibration over a reviewed corpus."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--only-id",
        help="Run exactly one corpus case by external ID for transport smoke testing.",
    )
    parser.add_argument(
        "--attempts-output",
        type=Path,
        default=Path("output/calibration-attempts.jsonl"),
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("output/calibration-metrics.json"),
    )
    arguments = parser.parse_args()

    try:
        metrics = run_http_calibration(
            arguments.corpus,
            arguments.config,
            attempts_output=arguments.attempts_output,
            metrics_output=arguments.metrics_output,
            only_id=arguments.only_id,
        )
    except CalibrationRunnerError as error:
        print(f"ERROR: {error}")
        return 2

    print(
        "PASS: "
        f"cases={metrics.case_count}, completed={metrics.completed_count}, "
        f"errors={metrics.error_count}, attempted={metrics.attempted_count}, "
        f"resumed={metrics.resumed_count}, precision={metrics.precision:.3f}, "
        f"recall={metrics.recall:.3f}, accuracy={metrics.accuracy:.3f}"
    )
    print(f"Attempts: {arguments.attempts_output}")
    print(f"Metrics: {arguments.metrics_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
