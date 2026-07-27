from __future__ import annotations

import argparse
from pathlib import Path

from painfinder.candidate_audit_review import (
    build_review_template,
    load_audit_rows,
    load_review_rows,
    summarize_review_rows,
    validate_review_rows,
    write_review_rows,
    write_review_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or validate a structured candidate audit review worksheet."
    )
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--worksheet-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--review-input", type=Path)
    arguments = parser.parse_args()

    try:
        audit_rows = load_audit_rows(arguments.audit)
        if arguments.review_input is None:
            review_rows = build_review_template(audit_rows)
            write_review_rows(review_rows, arguments.worksheet_output)
        else:
            review_rows = load_review_rows(arguments.review_input)
            validate_review_rows(audit_rows, review_rows)
            if arguments.review_input != arguments.worksheet_output:
                write_review_rows(review_rows, arguments.worksheet_output)

        summary = summarize_review_rows(review_rows)
        write_review_summary(summary, arguments.summary_output)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    print(
        f"PASS: rows={summary.row_count}, completed={summary.completed_count}, "
        f"pending={summary.pending_count}"
    )
    print(f"Worksheet: {arguments.worksheet_output}")
    print(f"Summary: {arguments.summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
