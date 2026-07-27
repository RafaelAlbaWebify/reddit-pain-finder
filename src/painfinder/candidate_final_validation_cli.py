from __future__ import annotations

import argparse
from pathlib import Path

from painfinder.benchmark import BenchmarkFormatError, load_benchmark
from painfinder.calibration_runner import load_latest_records
from painfinder.candidate_audit_review import load_review_rows
from painfinder.candidate_final_validation import (
    build_candidate_final_validation,
    write_candidate_final_validation,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the final candidate detector against the reviewed error baseline."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("output/candidate-final-validation.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("output/candidate-final-validation.md"),
    )
    arguments = parser.parse_args()

    try:
        cases = load_benchmark(arguments.corpus)
        records = load_latest_records(arguments.attempts)
        review_rows = load_review_rows(arguments.review)
    except (BenchmarkFormatError, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    validation = build_candidate_final_validation(cases, records, review_rows)
    write_candidate_final_validation(
        validation,
        json_output=arguments.json_output,
        markdown_output=arguments.markdown_output,
    )
    status = "PASS" if validation.passed else "FAIL"
    print(
        f"{status}: cases={validation.case_count}, "
        f"recovered={len(validation.recovered_detector_gap_ids)}, "
        f"remaining={len(validation.remaining_detector_gap_ids)}, "
        f"new_false_positives={len(validation.new_false_positive_ids)}"
    )
    print(f"JSON: {arguments.json_output}")
    print(f"Markdown: {arguments.markdown_output}")
    return 0 if validation.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
