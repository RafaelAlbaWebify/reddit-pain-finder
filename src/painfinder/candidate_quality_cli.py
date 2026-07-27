from __future__ import annotations

import argparse
from pathlib import Path

from painfinder.benchmark import BenchmarkFormatError, load_benchmark
from painfinder.calibration_runner import load_latest_records
from painfinder.candidate_quality_report import (
    analyze_candidate_quality,
    write_candidate_quality_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze candidate misses and the calibration decision funnel without model calls."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("output/candidate-quality-report.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("output/candidate-quality-report.md"),
    )
    parser.add_argument("--example-limit", type=int, default=20)
    arguments = parser.parse_args()

    if arguments.example_limit < 0:
        parser.error("--example-limit must be zero or greater")

    try:
        cases = load_benchmark(arguments.corpus)
        records = load_latest_records(arguments.attempts)
    except (BenchmarkFormatError, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    report = analyze_candidate_quality(
        cases,
        records,
        example_limit=arguments.example_limit,
    )
    write_candidate_quality_report(
        report,
        json_output=arguments.json_output,
        markdown_output=arguments.markdown_output,
    )
    print(
        "PASS: "
        f"cases={report.case_count}, expected_pain={report.expected_pain_count}, "
        f"candidate_detected={report.candidate_detected_count}, "
        f"candidate_misses={report.candidate_miss_count}, "
        f"candidate_precision={report.candidate_precision:.3f}, "
        f"candidate_recall={report.candidate_recall:.3f}"
    )
    print(f"JSON: {arguments.json_output}")
    print(f"Markdown: {arguments.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
