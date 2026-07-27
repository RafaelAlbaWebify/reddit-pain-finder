from __future__ import annotations

from pathlib import Path

import typer

from painfinder.candidate_audit_review import (
    build_review_template,
    load_audit_rows,
    load_review_rows,
    summarize_review_rows,
    validate_review_rows,
    write_review_rows,
    write_review_summary,
)

app = typer.Typer(add_completion=False)


@app.command()
def main(
    audit: Path = typer.Option(..., exists=True, dir_okay=False),
    worksheet_output: Path = typer.Option(..., dir_okay=False),
    summary_output: Path = typer.Option(..., dir_okay=False),
    review_input: Path | None = typer.Option(None, exists=True, dir_okay=False),
) -> None:
    audit_rows = load_audit_rows(audit)
    if review_input is None:
        review_rows = build_review_template(audit_rows)
        write_review_rows(review_rows, worksheet_output)
    else:
        review_rows = load_review_rows(review_input)
        validate_review_rows(audit_rows, review_rows)
        if review_input != worksheet_output:
            write_review_rows(review_rows, worksheet_output)

    summary = summarize_review_rows(review_rows)
    write_review_summary(summary, summary_output)
    typer.echo(
        "PASS: "
        f"rows={summary.row_count}, completed={summary.completed_count}, "
        f"pending={summary.pending_count}"
    )
    typer.echo(f"Worksheet: {worksheet_output}")
    typer.echo(f"Summary: {summary_output}")


if __name__ == "__main__":
    app()
