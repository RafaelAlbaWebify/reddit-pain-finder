from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from painfinder.benchmark import (
    BenchmarkFormatError,
    evaluate_benchmark,
    load_benchmark,
    write_benchmark_results,
)
from painfinder.benchmark_calibration import (
    CalibrationError,
    audit_corpus,
    compare_benchmark_results,
    compare_review_worksheets,
    write_corpus_audit,
)
from painfinder.benchmark_review import write_review_worksheet
from painfinder.benchmark_review_import import (
    ReviewWorksheetError,
    import_review_worksheet,
)
from painfinder.storage import SQLiteResearchRepository

benchmark_app = typer.Typer(no_args_is_help=True)


@benchmark_app.command("run")
def run_benchmark(
    corpus: Annotated[Path, typer.Option(exists=True, readable=True)],
    json_output: Annotated[Path, typer.Option()] = Path("output/benchmark-results.json"),
    html_output: Annotated[Path, typer.Option()] = Path("output/benchmark-results.html"),
) -> None:
    """Evaluate detector and clustering rules against a reviewed corpus."""
    try:
        cases = load_benchmark(corpus)
    except BenchmarkFormatError as error:
        typer.echo(f"ERROR: {error}")
        raise typer.Exit(code=2) from error

    result = evaluate_benchmark(cases)
    write_benchmark_results(
        result,
        json_output=json_output,
        html_output=html_output,
    )
    typer.echo(
        f"PASS: evaluated {result.case_count} case(s); "
        f"precision={result.precision:.3f}, recall={result.recall:.3f}, "
        f"cluster_pair_recall={result.cluster_pair_recall:.3f}"
    )
    typer.echo(f"JSON: {json_output}")
    typer.echo(f"HTML: {html_output}")


@benchmark_app.command("prepare-review")
def prepare_review(
    run_id: Annotated[str, typer.Option()],
    database: Annotated[Path, typer.Option(exists=True, readable=True)] = Path("data/research.db"),
    output: Annotated[Path, typer.Option()] = Path("output/benchmark-review-worksheet.csv"),
) -> None:
    """Export persisted evidence into an unlabeled human-review worksheet."""
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    try:
        item_count = write_review_worksheet(repository, run_id, output)
    except KeyError as error:
        typer.echo(f"ERROR: {error.args[0]}")
        raise typer.Exit(code=2) from error

    typer.echo(f"PASS: prepared {item_count} evidence item(s) for independent review")
    typer.echo(f"Worksheet: {output}")


@benchmark_app.command("import-review")
def import_review(
    worksheet: Annotated[Path, typer.Option(exists=True, readable=True)],
    output: Annotated[Path, typer.Option()] = Path("output/reviewed-benchmark-corpus.jsonl"),
) -> None:
    """Validate a resolved review worksheet and emit benchmark JSONL."""
    try:
        case_count = import_review_worksheet(worksheet, output)
    except ReviewWorksheetError as error:
        typer.echo(f"ERROR: {error}")
        raise typer.Exit(code=2) from error

    typer.echo(f"PASS: imported {case_count} resolved benchmark case(s)")
    typer.echo(f"Corpus: {output}")


@benchmark_app.command("audit-corpus")
def audit_reviewed_corpus(
    corpus: Annotated[Path, typer.Option(exists=True, readable=True)],
    json_output: Annotated[Path, typer.Option()] = Path("output/benchmark-corpus-audit.json"),
) -> None:
    """Check reviewed-corpus prerequisites before calibration."""
    try:
        audit = audit_corpus(corpus)
    except CalibrationError as error:
        typer.echo(f"ERROR: {error}")
        raise typer.Exit(code=2) from error
    write_corpus_audit(audit, json_output)
    if not audit.passed:
        failed = ", ".join(name for name, passed in audit.checks.items() if not passed)
        typer.echo(f"ERROR: corpus audit failed: {failed}")
        typer.echo(f"JSON: {json_output}")
        raise typer.Exit(code=2)
    typer.echo(
        f"PASS: corpus audit passed for {audit.case_count} case(s), "
        f"{len(audit.communities)} communities and {len(audit.categories)} categories"
    )
    typer.echo(f"JSON: {json_output}")


@benchmark_app.command("compare-reviews")
def compare_reviews(
    left: Annotated[Path, typer.Option(exists=True, readable=True)],
    right: Annotated[Path, typer.Option(exists=True, readable=True)],
    disagreements_output: Annotated[Path, typer.Option()] = Path(
        "output/benchmark-review-disagreements.csv"
    ),
    json_output: Annotated[Path, typer.Option()] = Path("output/benchmark-review-agreement.json"),
) -> None:
    """Compare two independent worksheets and produce a dispute queue."""
    try:
        summary = compare_review_worksheets(
            left,
            right,
            disagreements_output=disagreements_output,
            summary_output=json_output,
        )
    except CalibrationError as error:
        typer.echo(f"ERROR: {error}")
        raise typer.Exit(code=2) from error
    typer.echo(
        f"PASS: compared {summary['item_count']} item(s); "
        f"agreements={summary['agreement_count']}, "
        f"disagreements={summary['disagreement_count']}"
    )
    typer.echo(f"Disagreements: {disagreements_output}")
    typer.echo(f"JSON: {json_output}")


@benchmark_app.command("compare-results")
def compare_results(
    before: Annotated[Path, typer.Option(exists=True, readable=True)],
    after: Annotated[Path, typer.Option(exists=True, readable=True)],
    output: Annotated[Path, typer.Option()] = Path("output/benchmark-result-comparison.json"),
) -> None:
    """Record exact before/after benchmark metric and error-count deltas."""
    try:
        comparison = compare_benchmark_results(before, after, output)
    except (CalibrationError, KeyError, TypeError, ValueError) as error:
        typer.echo(f"ERROR: {error}")
        raise typer.Exit(code=2) from error
    typer.echo(f"PASS: compared benchmark results; same_case_count={comparison['same_case_count']}")
    typer.echo(f"JSON: {output}")
