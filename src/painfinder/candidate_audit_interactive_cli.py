from __future__ import annotations

import argparse
from pathlib import Path

from painfinder.candidate_audit_interactive import review_pending_rows
from painfinder.candidate_audit_review import summarize_review_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactively classify pending candidate audit review rows."
    )
    parser.add_argument("--worksheet", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        rows = review_pending_rows(arguments.worksheet)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    summary = summarize_review_rows(rows)
    print(
        f"PASS: rows={summary.row_count}, completed={summary.completed_count}, "
        f"pending={summary.pending_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
