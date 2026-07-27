from __future__ import annotations

import argparse
from pathlib import Path

from painfinder.benchmark import BenchmarkFormatError, load_benchmark
from painfinder.calibration_runner import load_latest_records
from painfinder.policy_grid import analyze_policy_grid, write_policy_grid_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate separate pain and evidence confidence thresholds without model calls."
        )
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("output/policy-compound-grid.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("output/policy-compound-grid.md"),
    )
    arguments = parser.parse_args()

    try:
        cases = load_benchmark(arguments.corpus)
        records = load_latest_records(arguments.attempts)
    except (BenchmarkFormatError, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    report = analyze_policy_grid(cases, records)
    write_policy_grid_report(
        report,
        json_output=arguments.json_output,
        markdown_output=arguments.markdown_output,
    )
    print(
        "PASS: "
        f"cases={report.case_count}, replayable={report.replayable_count}, "
        f"skipped={report.skipped_count}, rows={len(report.rows)}, "
        f"pareto={len(report.pareto_rows)}"
    )
    print(f"JSON: {arguments.json_output}")
    print(f"Markdown: {arguments.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
