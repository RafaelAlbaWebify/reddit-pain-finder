from __future__ import annotations

import argparse
from pathlib import Path

from painfinder.benchmark import BenchmarkFormatError, load_benchmark
from painfinder.calibration_runner import load_latest_records
from painfinder.candidate_audit import (
    build_candidate_error_audit,
    write_candidate_error_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export full candidate false-negative and false-positive audit records."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument(
        "--jsonl-output",
        type=Path,
        default=Path("output/candidate-error-audit.jsonl"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("output/candidate-error-audit.md"),
    )
    arguments = parser.parse_args()

    try:
        cases = load_benchmark(arguments.corpus)
        records = load_latest_records(arguments.attempts)
    except (BenchmarkFormatError, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    rows = build_candidate_error_audit(cases, records)
    write_candidate_error_audit(
        rows,
        jsonl_output=arguments.jsonl_output,
        markdown_output=arguments.markdown_output,
    )
    false_negatives = sum(row.error_type == "false_negative" for row in rows)
    false_positives = sum(row.error_type == "false_positive" for row in rows)
    print(
        f"PASS: rows={len(rows)}, false_negatives={false_negatives}, "
        f"false_positives={false_positives}"
    )
    print(f"JSONL: {arguments.jsonl_output}")
    print(f"Markdown: {arguments.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
