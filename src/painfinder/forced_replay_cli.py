from __future__ import annotations

import argparse
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from painfinder.benchmark import BenchmarkFormatError, load_benchmark
from painfinder.calibration_http_runner import run_http_calibration
from painfinder.calibration_runner import (
    CalibrationMetrics,
    CalibrationRecord,
    evaluate_calibration,
    load_latest_records,
    write_calibration_metrics,
)


class ReplayRunner(Protocol):
    def __call__(
        self,
        corpus: Path,
        config_path: Path,
        *,
        attempts_output: Path,
        metrics_output: Path,
        only_id: str | None = None,
    ) -> CalibrationMetrics:
        ...


class ForcedReplayError(RuntimeError):
    pass


def force_replay_selected(
    corpus: Path,
    config: Path,
    *,
    attempts_output: Path,
    metrics_output: Path,
    external_ids: Sequence[str],
    replay_runner: ReplayRunner = run_http_calibration,
) -> CalibrationMetrics:
    selected_ids = tuple(dict.fromkeys(value.strip() for value in external_ids if value.strip()))
    if not selected_ids:
        raise ForcedReplayError("At least one non-empty --id is required")

    try:
        cases = load_benchmark(corpus)
    except BenchmarkFormatError as error:
        raise ForcedReplayError(f"Invalid calibration corpus: {error}") from error

    known_ids = {case.item.external_id for case in cases}
    unknown_ids = tuple(value for value in selected_ids if value not in known_ids)
    if unknown_ids:
        raise ForcedReplayError(
            "Calibration case not found: " + ", ".join(sorted(unknown_ids))
        )

    attempts_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="painfinder-forced-replay-") as directory:
        temporary_root = Path(directory)
        for index, external_id in enumerate(selected_ids):
            temporary_attempts = temporary_root / f"attempt-{index}.jsonl"
            temporary_metrics = temporary_root / f"metrics-{index}.json"
            replay_runner(
                corpus,
                config,
                attempts_output=temporary_attempts,
                metrics_output=temporary_metrics,
                only_id=external_id,
            )
            record = load_latest_records(temporary_attempts).get(external_id)
            if record is None:
                raise ForcedReplayError(
                    f"Forced replay produced no record for: {external_id}"
                )
            _append_record_atomically(attempts_output, record)

    latest = load_latest_records(attempts_output)
    metrics = evaluate_calibration(
        cases,
        latest,
        attempted_count=len(selected_ids),
        resumed_count=len(cases) - len(selected_ids),
    )
    write_calibration_metrics(metrics, metrics_output)
    return metrics


def _append_record_atomically(path: Path, record: CalibrationRecord) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    temporary_path = path.with_name(f".{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(existing)
            handle.write(record.model_dump_json())
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Force selected successful calibration IDs through the current pipeline while "
            "preserving append-only attempt history."
        )
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--id",
        dest="external_ids",
        action="append",
        required=True,
        help="External corpus ID to replay. Repeat for multiple IDs.",
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
        metrics = force_replay_selected(
            arguments.corpus,
            arguments.config,
            attempts_output=arguments.attempts_output,
            metrics_output=arguments.metrics_output,
            external_ids=arguments.external_ids,
        )
    except (ForcedReplayError, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    status = "DONE_WITH_ERRORS" if metrics.error_count else "PASS"
    print(
        f"{status}: cases={metrics.case_count}, completed={metrics.completed_count}, "
        f"errors={metrics.error_count}, forced={metrics.attempted_count}, "
        f"resumed={metrics.resumed_count}, precision={metrics.precision:.3f}, "
        f"recall={metrics.recall:.3f}, accuracy={metrics.accuracy:.3f}"
    )
    print(f"Attempts: {arguments.attempts_output}")
    print(f"Metrics: {arguments.metrics_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
